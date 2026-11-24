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

def build_player_projection_board(games, max_players_per_team=4):
    """Fetch slate rosters and player logs in bulk; optional context never blocks the board."""
    season = current_season_start()
    teams = {}
    for game in games:
        for team, opponent in ((game.get("home_team") or {}, game.get("visitor_team") or {}),
                               (game.get("visitor_team") or {}, game.get("home_team") or {})):
            if team.get("id"):
                teams[int(team["id"])] = (team, opponent, game)
    try:
        roster = players_for_teams(list(teams))
        roster = [p for p in roster if p.get("id") and p.get("is_active") is not False]
        roster_by_team = {}
        for player in roster:
            tid = (player.get("team") or {}).get("id") or player.get("team_id")
            if tid is not None:
                roster_by_team.setdefault(int(tid), []).append(player)
        # Limit API log pulls to a small rotation sample before requesting stats.
        roster = [p for tid in teams for p in roster_by_team.get(tid, [])[:max_players_per_team]]
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
        # Optional opponent feeds are disabled to preserve the provider request budget.
        context = {}
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
                # Keep the parlay board's player projection identical to the
                # Player Projection Lab and walk-forward backtest.
                # Role/minute changes are shown as context, not applied as an
                # unvalidated multiplier to the forecast.
                estimate = float(proj["projection"])
                defense, pace = context.get("def_rating", float("nan")), context.get("pace", float("nan"))
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

def _wilson_lower(successes, trials, z=1.96):
    """Conservative lower confidence bound for a binomial hit rate."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    z2 = z * z
    denom = 1 + z2 / trials
    center = p + z2 / (2 * trials)
    spread = z * math.sqrt((p * (1 - p) / trials) + z2 / (4 * trials * trials))
    return max(0.0, (center - spread) / denom)


def _sample_quality(values, line, direction):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if not len(arr):
        return 0, 0.0, 0.0
    hits = int(np.sum(arr > line)) if direction == "over" else int(np.sum(arr < line))
    rate = (hits + 1) / (len(arr) + 2)
    return len(arr), float(rate), float(_wilson_lower(hits, len(arr)))


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
            sample_n, consistency_rate, confidence_floor = _sample_quality(values, line, direction)
            item.update({"line": float(line), "direction": direction, "probability": float(probability),
                         "edge": float(probability - .5), "consistency_rate": consistency_rate,
                         "confidence_score": confidence_floor, "confidence_sample": sample_n,
                         "confidence_label": "sample-supported" if sample_n >= 15 else "limited sample",
                         "source": "NBA Edge model target from recent player logs, minutes, role and available opponent context",
                         "target_line_type": "model suggestion; verify sportsbook availability"})
            legs.append(item)
    # Rank by the conservative lower confidence bound first, not raw hit rate alone.
    return sorted(legs, key=lambda x: (x["confidence_score"], x["confidence_sample"], x["minutes"]), reverse=True)

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
        sample_n, consistency_rate, confidence_floor = _sample_quality(row.get("_values") or [], line, direction)
        item.update({"line": line, "direction": direction, "probability": float(probability),
                     "edge": abs(float(probability)-.5), "consistency_rate": consistency_rate,
                     "confidence_score": confidence_floor, "confidence_sample": sample_n,
                     "confidence_label": "sample-supported" if sample_n >= 15 else "limited sample",
                     "source": "Recent NBA game logs; user-entered sportsbook line"})
        evaluated.append(item)
    return sorted(evaluated, key=lambda x: (x["confidence_score"], x["confidence_sample"]), reverse=True)
