import model


def test_optional_team_advanced_feed_failure_is_nonfatal(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("plan does not include advanced stats")
    monkeypatch.setattr(model, "team_advanced_averages", fail)
    assert model._optional_team_advanced(1, 2026) == {}


def test_optional_injury_feed_failure_returns_zero_adjustments(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injury feed unavailable")
    monkeypatch.setattr(model, "injuries", fail)
    result = model._optional_injury_penalties([1, 2])
    assert result == {
        1: {"penalty": 0.0, "count": 0},
        2: {"penalty": 0.0, "count": 0},
    }
