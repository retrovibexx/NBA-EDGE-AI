from parlays import build_parlay

def test_parlay_ranks_highest_probabilities():
    legs=[{"name":"A","p":0.55,"group":"g1"},{"name":"B","p":0.7,"group":"g2"},{"name":"C","p":0.6,"group":"g3"},{"name":"D","p":0.4,"group":"g4"}]
    chosen,warnings=build_parlay(legs,3)
    assert [x["name"] for x in chosen]==["B","C","A"]
    assert not warnings

def test_parlay_flags_shared_group():
    legs=[{"name":"A","p":0.6,"group":"same"},{"name":"B","p":0.5,"group":"same"},{"name":"C","p":0.4,"group":"other"}]
    chosen,warnings=build_parlay(legs,3)
    assert len(chosen)==3
    assert any("correlation" in warning.lower() for warning in warnings)
