"""Model-only player prop research. No sportsbook odds or live prop feed required."""
import numpy as np
from bdl import player_game_stats, current_season_start, players_for_team
from features import player_rows, rolling_projection, empirical_over_probability, as_float

PROP_STATS = ["PTS", "REB", "AST", "3PM", "STL", "BLK"]

def build_player_projection_board(games, max_players_per_team=12):
    board, seen = [], set()
    for game in games:
        home, away = game.get("home_team") or {}, game.get("visitor_team") or {}
        for team, opponent in ((home, away), (away, home)):
            if not team.get("id"): continue
            try: roster = players_for_team(team["id"])
            except Exception: continue
            eligible = []
            for player in roster:
                pid = player.get("id")
                if not pid or pid in seen or player.get("is_active") is False: continue
                try: logs = player_rows(player_game_stats(pid, current_season_start()))
                except Exception: continue
                if len(logs) < 5: continue
                mins = [as_float(r.get("min")) for r in logs[:10]]
                mins = [x for x in mins if np.isfinite(x) and x > 0]
                if not mins: continue
                minutes = float(np.mean(mins))
                if minutes >= 8: eligible.append((minutes, player, logs))
            eligible.sort(key=lambda x: x[0], reverse=True)
            for minutes, player, logs in eligible[:max_players_per_team]:
                seen.add(player["id"])
                for stat in PROP_STATS:
                    proj = rolling_projection(logs, stat)
                    if not proj or proj["n"] < 5: continue
                    values = [float(v) for v in proj["values"] if np.isfinite(v)]
                    board.append({
                        "game_id": game.get("id"),
                        "matchup": f"{away.get('abbreviation','Away')} @ {home.get('abbreviation','Home')}",
                        "player_id": player["id"],
                        "player": (player.get("first_name","") + " " + player.get("last_name","")).strip(),
                        "team": team.get("abbreviation",""),
                        "opponent": opponent.get("abbreviation",""),
                        "market": stat,
                        "projection": round(float(proj["projection"]), 2),
                        "last5": round(float(proj["last5"]), 2),
                        "last10": round(float(proj["last10"]), 2),
                        "minutes": round(minutes, 1),
                        "sample": len(values),
                        "line": None,
                        "_values": values
                    })
    return sorted(board, key=lambda x: (x["minutes"], x["sample"]), reverse=True)

def evaluate_manual_lines(board):
    evaluated = []
    for row in board:
        try: line = float(row.get("line"))
        except (TypeError, ValueError): continue
        values = row.get("_values") or []
        over = empirical_over_probability(values, line)
        if over is None: continue
        direction = "over" if over >= 0.5 else "under"
        probability = over if direction == "over" else 1 - over
        item = {k:v for k,v in row.items() if not k.startswith("_")}
        item.update({"line": line, "direction": direction, "probability": float(probability),
                     "edge": abs(float(probability)-0.5),
                     "source": "Recent NBA game logs; user-entered sportsbook line"})
        evaluated.append(item)
    return sorted(evaluated, key=lambda x: x["edge"], reverse=True)
