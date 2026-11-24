from prop_engine import build_model_legs
from parlays import build_candidates

def test_default_model_legs_and_parlay_candidates_load():
    board=[]
    for game_id, player_id, base in [(101,1,10),(102,2,15),(103,3,20),(104,4,12)]:
        values=[base+i for i in range(12)]
        board.append({
            "game_id":game_id,"player_id":player_id,"player":f"Player {player_id}",
            "market":"PTS","projection":base+5.5,"minutes":32,"sample":12,
            "_values":values
        })
    legs=build_model_legs(board)
    assert legs
    candidates=build_candidates(legs,3,5)
    assert candidates
    assert all(len(c["legs"])==3 for c in candidates)
    assert all(len({leg["game_id"] for leg in c["legs"]})==3 for c in candidates)
