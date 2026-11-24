"""Shared NBA player-log feature engineering and projection functions."""
import math
import numpy as np

STAT_MAP = {"PTS":"pts", "REB":"reb", "AST":"ast", "STL":"stl", "BLK":"blk", "MIN":"min", "3PM":"fg3m"}


def as_float(value):
    try:
        if isinstance(value, str) and ":" in value:
            minutes, seconds = value.split(":", 1)
            return float(minutes) + float(seconds) / 60
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def player_rows(rows):
    """Normalize flat BALLDONTLIE /v1/stats rows and nested stats payloads."""
    out = []
    metadata = {"id", "game", "player", "team", "stats", "season", "postseason"}
    for row in rows:
        game = row.get("game") or {}
        nested = row.get("stats")
        merged = dict(nested) if isinstance(nested, dict) else {}
        for key, value in row.items():
            if key not in metadata and key not in merged:
                merged[key] = value
        merged["date"] = game.get("date", row.get("date", ""))
        merged["game_id"] = game.get("id", row.get("game_id"))
        merged["team"] = row.get("team") or {}
        out.append(merged)
    return sorted(out, key=lambda x: x.get("date", ""), reverse=True)


def minutes_projection(rows):
    """Estimate minutes with a recency-weighted mean of valid appearances."""
    mins = [as_float(r.get("min")) for r in rows]
    mins = [x for x in mins if math.isfinite(x) and x > 0]
    if not mins:
        return None
    recent = mins[:10]
    weights = np.linspace(1.6, 1.0, len(recent))
    return float(np.average(recent, weights=weights))


def rolling_projection(rows, stat):
    """Project a stat using recent form, longer baseline, and per-minute production.

    Rows must be newest first. The same function is used by live projections and
    walk-forward backtests so evaluation measures the actual production logic.
    """
    key = STAT_MAP.get(stat, stat.lower())
    valid = []
    for row in rows:
        value = as_float(row.get(key))
        if math.isfinite(value):
            valid.append((value, as_float(row.get("min"))))
    if not valid:
        return None

    values = np.asarray([x[0] for x in valid], dtype=float)
    sample = values[:min(20, len(values))]
    n = len(sample)
    # Recent form is balanced against the player's longer recent baseline.
    short = sample[:min(5, n)]
    medium = sample[:min(10, n)]
    weights = np.linspace(1.5, 0.85, n)
    weighted = float(np.average(sample, weights=weights))
    recent5 = float(np.mean(short))
    recent10 = float(np.mean(medium))
    median = float(np.median(sample))
    raw_projection = 0.50 * weighted + 0.30 * recent5 + 0.20 * median

    projected_minutes = minutes_projection(rows)
    rate_values = []
    for value, minutes in valid[:min(15, len(valid))]:
        if math.isfinite(minutes) and minutes >= 1:
            rate_values.append(value / minutes)
    if stat.upper() != "MIN" and projected_minutes is not None and rate_values:
        # Shrink the per-minute estimate toward its sample mean to reduce noise.
        rate_weights = np.linspace(1.4, 0.9, len(rate_values))
        rate = float(np.average(rate_values, weights=rate_weights))
        rate_projection = rate * projected_minutes
        raw_projection = 0.65 * raw_projection + 0.35 * rate_projection

    return {
        "projection": float(max(0.0, raw_projection)),
        "mean": float(np.mean(sample)),
        "median": median,
        "last5": recent5,
        "last10": recent10,
        "n": n,
        "values": sample.tolist(),
        "minutes_projection": projected_minutes,
        "std": float(np.std(sample, ddof=1)) if n > 1 else 0.0,
    }


def empirical_over_probability(values, line):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 3:
        return None
    return (int(np.sum(arr > line)) + 1) / (len(arr) + 2)
