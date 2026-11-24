from matchup_engine import _position, detect_role_change

def test_position_groups():
    assert _position("G") == "G"
    assert _position("F") == "F"
    assert _position("C") == "C"
    assert _position("G-F") == "G-F"
    assert _position("F-C") == "F-C"
    assert _position(None) is None

def test_role_detector_uses_turnover_field():
    rows=[{"min":35,"fga":20,"fta":8,"turnover":5} for _ in range(5)]
    rows += [{"min":27,"fga":14,"fta":4,"turnover":2} for _ in range(10)]
    result=detect_role_change(rows)
    assert result["label"] == "Role trending up"
    assert result["minutes_change"] == 8
    assert result["usage_change"] is not None
