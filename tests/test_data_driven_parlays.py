import prop_engine

def test_model_target_legs_are_generated_without_book_lines():
    values=[12,14,15,16,17,18,19,20,21,22,23,24]
    board=[{
        "game_id":1,"player_id":7,"player":"Example Player","market":"PTS",
        "projection":18.5,"minutes":32,"sample":len(values),"_values":values
    }]
    legs=prop_engine.build_model_legs(board,min_sample=8,min_probability=.58)
    assert legs
    assert all(x["line"] is not None for x in legs)
    assert all(x["target_line_type"].startswith("model suggestion") for x in legs)

def test_bulk_projection_board_uses_bulk_stats_and_optional_feeds(monkeypatch):
    monkeypatch.setattr(prop_engine,"_injury_ids",lambda:set())
    monkeypatch.setattr(prop_engine,"players_for_teams",lambda team_ids:[
        {"id":team_id*10+1,"first_name":"Sample","last_name":"Player","is_active":True,"team":{"id":team_id,"abbreviation":str(team_id)}}
        for team_id in team_ids
    ])
    def bulk(ids,season):
        pid=ids[0]
        return [{
            "player":{"id":pid},
            "game":{"id":i,"date":f"2026-11-{i+1:02d}"},
            "stats":{"min":32,"pts":15+i,"reb":5,"ast":4,"fg3m":2,"stl":1,"blk":0}
        } for i in range(12)]
    monkeypatch.setattr(prop_engine,"player_game_stats_many",bulk)
    monkeypatch.setattr(prop_engine,"_optional_opponent_context",lambda *args:{"def_rating":float("nan"),"pace":float("nan")})
    games=[{"id":100,"home_team":{"id":1,"abbreviation":"H"},"visitor_team":{"id":2,"abbreviation":"A"}}]
    board=prop_engine.build_player_projection_board(games)
    assert board
    assert {"PTS","REB","AST","3PM","STL","BLK"} <= {x["market"] for x in board}
