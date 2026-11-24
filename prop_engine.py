"""Data-driven NBA player projections and model-generated parlay candidates."""
import math
import numpy as np
from bdl import player_game_stats_many, current_season_start, players_for_teams
from features import player_rows, rolling_projection, empirical_over_probability, as_float, minutes_projection

PROP_STATS = ["PTS", "REB", "AST", "3PM", "STL", "BLK"]

def american_prob(odds):
    """Backwards-compatible American-odds conversion helper."""
    try:
        value = float(odds)
        return (-value) / ((-value) + 100) if value < 0 else 100 / (value + 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return None

def _optional_opponent_context(team_id, season):
    try:
        rows = team_advanced_averages(int(team_id), int(season))
        stats = (rows[0].get("stats") or {}) if rows else {}
        return {"def_rating": as_float(stats.get("def_rating", stats.get("defensive_rating"))),
                "pace": as_float(stats.get("pace", stats.get("e_pace")))}
    except Exception:
        return {"def_rating": float("nan"), "pace": float("nan")}

def _injury_ids():
    try:
        rows = injuries()
        return {(x.get("player") or {}).get("id") for x in rows
                if str(x.get("status", "")).lower() in ("out", "doubtful")
                and (x.get("player") or {}).get("id") is not None}
    except Exception:
        return set()

def build_player_projection_board(games, max_players_per_team=4):
    """Fetch slate rosters and player logs in bulk; optional context never blocks the board."""
    season = current_season_start()
    unavailable = _injury_ids()
    teams = {}
    for game in games:
        for team, opponent in ((game.get("home_team") or {}, game.get("visitor_team") or {}),
                               (game.get("visitor_team") or {}, game.get("home_team") or {})):
            if team.get("id"):
                teams[int(team["id"])] = (team, opponent, game)
    try:
        roster = players_for_teams(list(teams))
        roster = [p for p in roster if p.get("id") and p.get("is_active") is not False
                  and p.get("id") not in unavailable]
        raw = player_game_stats_many([p["id"] for p in roster], season) if roster else []
    except Exception as exc:
        raise RuntimeError(f"Could not load team rosters/player game logs: {exc}") from exc
    by_player = {}
    for row in raw:
        pid = (row.get("player") or {}).get("id")
        if pid is not None:
            by_player.setdefault(int(pid), []).append(row)
    roster_by_team = {}
    for player in roster:
        team_id = (player.get("team") or {}).get("id") or player.get("team_id")
        if team_id is not None:
            roster_by_team.setdefault(int(team_id), []).append(player)
    board = []
    for team_id, (team, opponent, game) in teams.items():
        # Do not make one advanced-stats API call per opponent: the user plan is capped at 5 RPM.\n        # Core projections remain data-driven from player logs, minutes and role trend.\n        context = {}
        eligible = []
        for player in roster_by_team.get(team_id, []):
            logs = player_rows(by_player.get(int(player["id"]), []))
            if len(logs) < 5:
                continue
            mins = minutes_projection(logs)
            if mins is not None and mins >= 8:
                eligible.append((mins, player, logs))
        eligible.sort(key=lambda x: x[0], reverse=True)
        for mins, player, logs in eligible[:max_players_per_team]:
            recent_mins = [as_float(r.get("min")) for r in logs[:5]]
            recent_mins = [v for v in recent_mins if np.isfinite(v) and v > 0]
            prior_mins = [as_float(r.get("min")) for r in logs[5:15]]
            prior_mins = [v for v in prior_mins if np.isfinite(v) and v > 0]
            role_change = float(np.mean(recent_mins) - np.mean(prior_mins)) if recent_mins and prior_mins else 0.0
            for stat in PROP_STATS:
                proj = rolling_projection(logs, stat)
                if not proj or proj["n"] < 5:
                    continue
                values = [float(v) for v in proj["values"] if np.isfinite(v)]
                key = {"PTS":"pts","REB":"reb","AST":"ast","3PM":"fg3m","STL":"stl","BLK":"blk"}[stat]
                rates = []
                for row in logs[:10]:
                    value, played = as_float(row.get(key)), as_float(row.get("min"))
                    if np.isfinite(value) and np.isfinite(played) and played > 0:
                        rates.append(value / played)
                estimate = float(proj["projection"])
                if rates:
                    estimate = .55 * estimate + .45 * float(np.mean(rates)) * mins
                defense, pace = context.get("def_rating", float("nan")), context.get("pace", float("nan"))
                if np.isfinite(defense):
                    estimate *= 1 + float(np.clip((defense - 112) * .0015, -.035, .035))
                if np.isfinite(pace):
                    estimate *= 1 + float(np.clip((pace - 100) * .001, -.025, .025))
                estimate *= 1.025 if role_change >= 3 else (.975 if role_change <= -3 else 1.0)
                board.append({
                    "game_id": game.get("id"),
                    "matchup": f"{(game.get('visitor_team') or {}).get('abbreviation','Away')} @ {(game.get('home_team') or {}).get('abbreviation','Home')}",
                    "player_id": int(player["id"]),
                    "player": (player.get("first_name","") + " " + player.get("last_name","")).strip(),
                    "team": team.get("abbreviation",""), "opponent": opponent.get("abbreviation",""),
                    "market": stat, "projection": round(max(0, estimate), 2),
                    "last5": round(float(proj["last5"]), 2), "last10": round(float(proj["last10"]), 2),
                    "minutes": round(float(mins), 1), "role_change": round(role_change, 1),
                    "opponent_def_rating": round(float(defense), 2) if np.isfinite(defense) else None,
                    "opponent_pace": round(float(pace), 2) if np.isfinite(pace) else None,
                    "sample": len(values), "line": None, "_values": values
                })
    return sorted(board, key=lambda x: (x["minutes"], x["sample"]), reverse=True)

def build_model_legs(board, min_sample=6, min_probability=0.55):
    legs = []
    for row in board:
        values = np.asarray(row.get("_values") or [], dtype=float)
        values = values[np.isfinite(values)]
        if len(values) < min_sample:
            continue
        over_line = math.floor(float(np.quantile(values, .30))) + .5
        under_line = math.ceil(float(np.quantile(values, .70))) - .5
        for direction, line in (("over", over_line), ("under", under_line)):
            p_over = empirical_over_probability(values, line)
            if p_over is None:
                continue
            probability = p_over if direction == "over" else 1 - p_over
            if probability < min_probability or probability >= .96:
                continue
            item = {k:v for k,v in row.items() if not k.startswith("_")}
            item.update({"line": float(line), "direction": direction, "probability": float(probability),
                         "edge": float(probability - .5),
                         "source": "NBA Edge model target from recent player logs, minutes, role and available opponent context",
                         "target_line_type": "model suggestion; verify sportsbook availability"})
            legs.append(item)
    return sorted(legs, key=lambda x: (x["probability"], x["projection"], x["minutes"]), reverse=True)

def evaluate_manual_lines(board):
    evaluated = []
    for row in board:
        try:
            line = float(row.get("line"))
        except (TypeError, ValueError):
            continue
        over = empirical_over_probability(row.get("_values") or [], line)
        if over is None:
            continue
        direction = "over" if over >= .5 else "under"
        probability = over if direction == "over" else 1 - over
        item = {k:v for k,v in row.items() if not k.startswith("_")}
        item.update({"line": line, "direction": direction, "probability": float(probability),
                     "edge": abs(float(probability)-.5),
                     "source": "Recent NBA game logs; user-entered sportsbook line"})
        evaluated.append(item)
    return sorted(evaluated, key=lambda x: x["edge"], reverse=True)
