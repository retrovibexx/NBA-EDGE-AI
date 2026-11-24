import prop_engine

def test_evaluate_manual_lines_uses_model_history_only():
    board=[{
        "game_id":1,"player_id":10,"player":"Test Player","market":"PTS",
        "projection":25.0,"line":20.5,"_values":[22,24,26,28,30,21,25,27,23,29]
    }]
    rows=prop_engine.evaluate_manual_lines(board)
    assert len(rows)==1
    assert rows[0]["direction"]=="over"
    assert rows[0]["probability"]>0.5
    assert rows[0]["source"].startswith("Recent NBA game logs")

def test_evaluate_manual_lines_skips_blank_or_invalid_lines():
    board=[
        {"line":None,"_values":[1,2,3]},
        {"line":"not-a-number","_values":[1,2,3]},
        {"line":2,"_values":[1,2]}
    ]
    assert prop_engine.evaluate_manual_lines(board)==[]

def test_projection_board_does_not_need_live_props(monkeypatch):
    monkeypatch.setattr(prop_engine,"players_for_team",lambda team_id: [])
    assert prop_engine.build_player_projection_board([
        {"id":1,"home_team":{"id":2,"abbreviation":"H"},"visitor_team":{"id":3,"abbreviation":"A"}}
    ])==[]
