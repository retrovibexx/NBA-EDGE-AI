"""Monte Carlo parlay simulation using empirical player-game logs.

When legs have overlapping game dates, bootstrap the same dates together to
preserve observed co-movement. Otherwise, sample each leg independently.
"""
import numpy as np


def simulate_parlay(legs, simulations=20000, seed=7):
    if not legs:
        raise ValueError("At least one parlay leg is required.")
    if not 1000 <= int(simulations) <= 200000:
        raise ValueError("Simulation count must be between 1,000 and 200,000.")

    histories = []
    for leg in legs:
        history = leg.get("simulation_history") or []
        clean = {}
        for item in history:
            try:
                day = str(item["date"])[:10]
                value = float(item["value"])
                if day and np.isfinite(value):
                    clean[day] = value
            except (KeyError, TypeError, ValueError):
                continue
        if len(clean) < 3:
            raise ValueError(
                f"Not enough dated game-log samples to simulate {leg.get('player', 'a leg')}."
            )
        histories.append(clean)

    common_dates = sorted(set.intersection(*(set(h) for h in histories)))
    rng = np.random.default_rng(seed)
    n = int(simulations)
    outcomes = np.zeros((n, len(legs)), dtype=bool)
    method = "date-aligned joint historical bootstrap" if len(common_dates) >= 5 else "independent empirical bootstrap"
    if len(common_dates) >= 5:
        chosen = rng.integers(0, len(common_dates), size=n)
        for j, (leg, history) in enumerate(zip(legs, histories)):
            draws = np.asarray([history[common_dates[i]] for i in chosen], dtype=float)
            line = float(leg["line"])
            outcomes[:, j] = draws > line if leg["direction"] == "over" else draws < line
    else:
        for j, (leg, history) in enumerate(zip(legs, histories)):
            vals = np.asarray(list(history.values()), dtype=float)
            draws = rng.choice(vals, size=n, replace=True)
            line = float(leg["line"])
            outcomes[:, j] = draws > line if leg["direction"] == "over" else draws < line

    hit_all = np.all(outcomes, axis=1)
    hit_rate = float(np.mean(hit_all))
    # Monte Carlo standard error, not a guarantee or sportsbook-calibrated probability.
    se = float(np.sqrt(hit_rate * (1.0 - hit_rate) / n))
    leg_rates = [float(np.mean(outcomes[:, j])) for j in range(len(legs))]
    return {
        "simulations": n,
        "parlay_hit_rate": hit_rate,
        "confidence_low": max(0.0, hit_rate - 1.96 * se),
        "confidence_high": min(1.0, hit_rate + 1.96 * se),
        "leg_hit_rates": leg_rates,
        "method": method,
        "overlap_dates": len(common_dates),
        "warning": (
            "Historical bootstrap estimate, not a guarantee or calibrated sportsbook probability. "
            "Date alignment can capture observed co-movement only when enough shared dates exist; "
            "otherwise legs are simulated independently."
        ),
    }
