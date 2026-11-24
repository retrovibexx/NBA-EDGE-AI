from parlays import build_candidates

def test_builder_requires_positive_edge_and_distinct_games():
    legs=[
        {"player":"A","player_id":1,"game_id":10,"market":"points","probability":0.62,"edge":0.06},
        {"player":"B","player_id":2,"game_id":11,"market":"rebounds","probability":0.59,"edge":0.04},
        {"player":"C","player_id":3,"game_id":12,"market":"assists","probability":0.57,"edge":0.03},
        {"player":"D","player_id":4,"game_id":12,"market":"points","probability":0.7,"edge":0.1},
        {"player":"E","player_id":5,"game_id":13,"market":"points","probability":0.55,"edge":0.01},
    ]
    results=build_candidates(legs,3)
    assert results
    assert all(len({x["game_id"] for x in c["legs"]})==3 for c in results)
    assert all(x["edge"]>=0.025 for c in results for x in c["legs"])

def test_builder_rejects_same_player_twice():
    legs=[
        {"player":"A","player_id":1,"game_id":10,"market":"points","probability":0.62,"edge":0.06},
        {"player":"A","player_id":1,"game_id":11,"market":"rebounds","probability":0.59,"edge":0.04},
        {"player":"C","player_id":3,"game_id":12,"market":"assists","probability":0.57,"edge":0.03},
    ]
    assert build_candidates(legs,3)==[]
