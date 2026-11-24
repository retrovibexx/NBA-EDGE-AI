from matchup_engine import detect_role_change

def test_detect_role_increase_from_minutes():
    rows=[{"min":35} for _ in range(5)]+[{"min":27} for _ in range(10)]
    result=detect_role_change(rows)
    assert result["label"]=="Role trending up"
    assert result["minutes_change"]==8

def test_detect_role_decline_from_minutes():
    rows=[{"min":22} for _ in range(5)]+[{"min":31} for _ in range(10)]
    result=detect_role_change(rows)
    assert result["label"]=="Minutes trending down"

def test_role_detector_handles_small_samples():
    result=detect_role_change([{"min":30} for _ in range(3)])
    assert result["label"]=="Insufficient sample"
    assert result["minutes_change"] is None
