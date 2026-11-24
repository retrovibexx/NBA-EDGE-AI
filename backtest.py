"""Leakage-safe walk-forward evaluation for NBA Edge player projections.

Historical sportsbook prop lines are not available from the current provider.
When a user supplies a line, it is evaluated as a fixed historical threshold;
otherwise only projection-error metrics are reported.
"""
import numpy as np
import pandas as pd
from bdl import search_players, player_game_history, current_season_start
from features import player_rows, rolling_projection, STAT_MAP, as_float


def _summarize(frame, player, stat, line=None):
    errors = frame["actual"].to_numpy(dtype=float) - frame["predicted"].to_numpy(dtype=float)
    result = {
        "player": player,
        "stat": stat,
        "games": int(len(frame)),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "bias": float(np.mean(errors)),
        "within_2": float(np.mean(np.abs(errors) <= 2)),
        "within_3": float(np.mean(np.abs(errors) <= 3)),
        "within_5": float(np.mean(np.abs(errors) <= 5)),
        "rows": frame,
    }
    if line is not None:
        graded = frame[frame["line_result"].isin(["over", "under"])]
        result["line"] = float(line)
        result["line_games"] = int(len(graded))
        result["line_hit_rate"] = float(graded["line_hit"].mean()) if len(graded) else None
        result["pushes"] = int((frame["line_result"] == "push").sum())
        result["over_hits"] = int(((graded["predicted_side"] == "over") & (graded["line_hit"] == 1)).sum())
        result["under_hits"] = int(((graded["predicted_side"] == "under") & (graded["line_hit"] == 1)).sum())
    confidence = frame.dropna(subset=["confidence_within_3"])
    if len(confidence):
        result["confidence_within_3_mean"] = float(confidence["confidence_within_3"].mean())
        result["observed_within_3_when_calibrated"] = float(confidence["within_3"].mean())
    else:
        result["confidence_within_3_mean"] = None
        result["observed_within_3_when_calibrated"] = None
    return result


def player_walk_forward(name, stat, max_games=60, history=10, line=None):
    matches = search_players(name)
    if not matches:
        return None, "Player not found."
    exact = next(
        (p for p in matches if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip().lower() == name.lower()),
        matches[0],
    )
    rows = player_rows(player_game_history(exact["id"], current_season_start()))
    key = STAT_MAP.get(stat, stat.lower())
    chronological = list(reversed(rows))
    observations = []
    prior_abs_errors = []

    for i in range(history, len(chronological)):
        past_chronological = chronological[max(0, i-history):i]
        past = list(reversed(past_chronological))
        actual = as_float(chronological[i].get(key))
        if not np.isfinite(actual):
            continue
        projection = rolling_projection(past, stat)
        if not projection:
            continue
        predicted = float(projection["projection"])
        abs_error = abs(float(actual) - predicted)

        # This confidence estimate uses only errors from earlier test predictions.
        # It is intentionally unavailable until eight prior forecasts exist.
        confidence = (
            float((sum(x <= 3 for x in prior_abs_errors) + 1) / (len(prior_abs_errors) + 2))
            if len(prior_abs_errors) >= 8 else np.nan
        )
        row = {
            "date": chronological[i].get("date"),
            "predicted": predicted,
            "actual": float(actual),
            "error": float(actual) - predicted,
            "abs_error": abs_error,
            "within_2": int(abs_error <= 2),
            "within_3": int(abs_error <= 3),
            "within_5": int(abs_error <= 5),
            "confidence_within_3": confidence,
            "confidence_sample": len(prior_abs_errors),
        }
        if line is not None:
            p_over = (sum(as_float(x.get(key)) > float(line) for x in past) + 1) / (len(past) + 2)
            side = "over" if p_over >= 0.5 else "under"
            result = "push" if float(actual) == float(line) else ("over" if float(actual) > float(line) else "under")
            row.update({
                "line": float(line),
                "historical_over_estimate": float(p_over),
                "predicted_side": side,
                "line_result": result,
                "line_hit": int(side == result) if result != "push" else np.nan,
            })
        observations.append(row)
        prior_abs_errors.append(abs_error)

    frame = pd.DataFrame(observations[-max_games:])
    if frame.empty:
        return None, "Not enough historical games for walk-forward evaluation."
    player = f"{exact.get('first_name', '')} {exact.get('last_name', '')}".strip()
    return _summarize(frame, player, stat, line), (
        "Every forecast uses only games played before its target game. Confidence is a rolling "
        "historical estimate of being within 3 stat units, based only on earlier walk-forward errors. "
        "A supplied fixed line is a historical threshold proxy, not an archived sportsbook line."
    )


def multi_player_walk_forward(names, stat, max_games=60, history=10, line=None):
    """Run the same leakage-safe test across a small comma-separated player list."""
    results = []
    errors = []
    for name in [x.strip() for x in names if x and x.strip()][:8]:
        result, note = player_walk_forward(name, stat, max_games=max_games, history=history, line=line)
        if result:
            results.append(result)
        else:
            errors.append(f"{name}: {note}")
    if not results:
        return pd.DataFrame(), errors
    rows = []
    for item in results:
        rows.append({k: item.get(k) for k in (
            "player", "stat", "games", "mae", "rmse", "bias", "within_2", "within_3",
            "within_5", "line", "line_games", "line_hit_rate", "pushes",
            "confidence_within_3_mean", "observed_within_3_when_calibrated"
        )})
    frame = pd.DataFrame(rows)
    if line is not None:
        frame = frame.sort_values(["line_hit_rate", "games"], ascending=[False, False], na_position="last")
    else:
        frame = frame.sort_values(["mae", "games"], ascending=[True, False])
    return frame.reset_index(drop=True), errors
