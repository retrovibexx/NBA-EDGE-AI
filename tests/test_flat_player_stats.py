from features import player_rows, rolling_projection

def test_player_rows_reads_flat_ball_dont_lie_stats():
    rows = player_rows([{
        "id": 7,
        "pts": 28,
        "reb": 9,
        "ast": 4,
        "min": "36:20",
        "fg3m": 3,
        "game": {"id": 99, "date": "2026-11-23"},
        "player": {"id": 12},
        "team": {"id": 3}
    }])
    assert rows[0]["pts"] == 28
    assert rows[0]["reb"] == 9
    assert rows[0]["min"] == "36:20"
    assert rows[0]["game_id"] == 99
    assert rolling_projection(rows, "PTS")["projection"] == 28

def test_player_rows_still_supports_nested_stats():
    rows = player_rows([{
        "stats": {"pts": 21, "reb": 5, "min": "30:00"},
        "game": {"id": 100, "date": "2026-11-22"},
        "player": {"id": 12}
    }])
    assert rows[0]["pts"] == 21
    assert rows[0]["reb"] == 5
