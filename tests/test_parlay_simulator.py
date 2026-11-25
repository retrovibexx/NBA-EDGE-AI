from parlay_simulator import simulate_parlay


def _leg(player, direction="over", line=10, values=None):
    values = values or [8, 9, 10, 11, 12, 13]
    return {
        "player": player, "direction": direction, "line": line,
        "simulation_history": [
            {"date": f"2026-11-{i+1:02d}", "value": value}
            for i, value in enumerate(values)
        ],
    }


def test_monte_carlo_returns_parlay_and_leg_hit_rates():
    result = simulate_parlay([_leg("A"), _leg("B", "under", 12)], simulations=5000)
    assert 0 <= result["parlay_hit_rate"] <= 1
    assert len(result["leg_hit_rates"]) == 2
    assert result["simulations"] == 5000
    assert result["overlap_dates"] == 6
    assert "joint historical bootstrap" in result["method"]


def test_simulator_rejects_missing_history():
    try:
        simulate_parlay([{"player": "A", "line": 10, "direction": "over"}])
    except ValueError as exc:
        assert "dated game-log samples" in str(exc)
    else:
        raise AssertionError("Expected missing history to be rejected")
