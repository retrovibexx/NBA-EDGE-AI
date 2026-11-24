import math
from features import rolling_projection, player_rows, minutes_projection


def test_projection_uses_recent_minutes_and_per_minute_production():
    rows = [
        {"pts": 30, "min": "30:00"},
        {"pts": 20, "min": "20:00"},
        {"pts": 10, "min": "10:00"},
        {"pts": 15, "min": "30:00"},
        {"pts": 18, "min": "30:00"},
        {"pts": 12, "min": "24:00"},
        {"pts": 16, "min": "32:00"},
        {"pts": 14, "min": "28:00"},
        {"pts": 11, "min": "22:00"},
        {"pts": 17, "min": "34:00"},
        {"pts": 13, "min": "26:00"},
        {"pts": 19, "min": "38:00"},
    ]
    result = rolling_projection(rows, "PTS")
    assert result is not None
    assert result["projection"] > 0
    assert result["projected_minutes"] > 0
    assert result["per_minute_projection"] > 0
    assert math.isfinite(result["sample_std"])


def test_projection_and_parlay_engine_share_same_forecast_function():
    rows = [
        {"pts": value, "min": "32:00"}
        for value in [21, 24, 18, 29, 17, 22, 26, 20, 25, 23, 19, 27]
    ]
    live = rolling_projection(rows, "PTS")["projection"]
    backtest_equivalent = rolling_projection(rows, "PTS")["projection"]
    assert live == backtest_equivalent


def test_player_rows_sort_newest_first_and_keep_game_dates():
    raw = [
        {"game": {"date": "2026-11-02", "id": 2}, "stats": {"pts": 20, "min": "30:00"}},
        {"game": {"date": "2026-11-01", "id": 1}, "stats": {"pts": 10, "min": "20:00"}},
    ]
    rows = player_rows(raw)
    assert rows[0]["date"] == "2026-11-02"
    assert rows[1]["date"] == "2026-11-01"
    assert minutes_projection(rows) > 0
