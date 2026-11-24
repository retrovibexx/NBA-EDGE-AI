import pandas as pd
from backtest import _summarize
from prop_engine import _wilson_lower, _sample_quality


def test_walk_forward_error_metrics_and_line_grading():
    frame = pd.DataFrame([
        {"predicted": 10.0, "actual": 11.0, "within_3": 1, "confidence_within_3": 0.7,
         "line_result": "over", "line_hit": 1, "predicted_side": "over"},
        {"predicted": 10.0, "actual": 8.0, "within_3": 1, "confidence_within_3": 0.6,
         "line_result": "under", "line_hit": 1, "predicted_side": "under"},
        {"predicted": 10.0, "actual": 10.0, "within_3": 1, "confidence_within_3": 0.5,
         "line_result": "push", "line_hit": float("nan"), "predicted_side": "over"},
    ])
    result = _summarize(frame, "Test Player", "PTS", line=10)
    assert result["games"] == 3
    assert result["mae"] == 1.0
    assert result["line_games"] == 2
    assert result["line_hit_rate"] == 1.0
    assert result["pushes"] == 1
    assert result["observed_within_3_when_calibrated"] == 1.0


def test_wilson_lower_bound_is_conservative_and_sample_aware():
    assert 0 < _wilson_lower(8, 10) < 0.8
    assert _wilson_lower(80, 100) > _wilson_lower(8, 10)


def test_sample_quality_uses_correct_over_under_direction():
    n, over_rate, over_floor = _sample_quality([10, 11, 12, 8, 9], 9.5, "over")
    assert n == 5
    assert over_rate == 4 / 7
    assert 0 <= over_floor <= over_rate
    _, under_rate, _ = _sample_quality([10, 11, 12, 8, 9], 9.5, "under")
    assert under_rate == 3 / 7
