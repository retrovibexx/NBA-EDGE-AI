import pytest
import injury_guard

def test_unavailable_statuses_are_excluded():
    for status in ("Out", "Doubtful", "Questionable", "Injured Reserve", "Suspended"):
        assert injury_guard.is_unavailable(status)

def test_probable_and_unlisted_are_not_excluded():
    assert not injury_guard.is_unavailable("Probable")
    assert not injury_guard.is_unavailable(None)

def test_status_map_uses_player_ids(monkeypatch):
    monkeypatch.setattr(injury_guard, "injuries", lambda: [
        {"player": {"id": 12}, "status": "Questionable"},
        {"player": {"id": 13}, "status": "Out"},
    ])
    assert injury_guard.injury_status_map() == {12: "questionable", 13: "out"}

def test_status_feed_failure_fails_closed(monkeypatch):
    def fail():
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(injury_guard, "injuries", fail)
    with pytest.raises(RuntimeError, match="could not be verified"):
        injury_guard.injury_status_map()
