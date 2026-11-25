import streamlit as st
import pandas as pd
from datetime import date
from bdl import api_key, games_for_date
from model import predict_game
from prop_engine import build_player_projection_board, build_model_legs
from parlays import build_candidates
from injury_guard import injury_status_map, is_unavailable
from parlay_simulator import simulate_parlay

st.set_page_config(page_title="NBA Edge AI", page_icon="🏀", layout="wide")
st.title("🏀 NBA Edge AI")
st.caption("NBA game simulations · data-driven player parlays")
if not api_key():
    st.error("BALLDONTLIE API key is missing. Add it in Streamlit Secrets; never paste it into chat.")
    st.stop()

today = date.today().isoformat()
try:
    games = games_for_date(today)
    slate_error = None
except Exception as exc:
    games, slate_error = [], str(exc)

scheduled = []
for game in games:
    status = str(game.get("status", "")).lower()
    state = str(game.get("status_state", "")).lower()
    is_final_or_live = state in ("final", "live", "in_progress") or status in ("final", "in progress", "live")
    if not is_final_or_live and str(game.get("date", today)) >= today:
        scheduled.append(game)

def game_label(game):
    away = (game.get("visitor_team") or {}).get("full_name", "Away")
    home = (game.get("home_team") or {}).get("full_name", "Home")
    return f"{away} @ {home}"

tabs = st.tabs(["Game simulator", "AI parlay builder"])

with tabs[0]:
    st.subheader("NBA game simulator")
    if slate_error:
        st.error(f"Schedule could not load: {slate_error}")
    elif not scheduled:
        st.info("No upcoming games are listed for today. Check back when the provider posts the slate.")
    else:
        choices = {game_label(g): g for g in scheduled}
        selected_label = st.selectbox("Choose a matchup", list(choices))
        game = choices[selected_label]
        simulations = st.select_slider("Simulation runs", options=[5000, 10000, 20000, 30000], value=10000)
        if st.button("Simulate game", type="primary", key="simulate_game"):
            with st.spinner("Checking team form, rest, ratings, head-to-head and injury status…"):
                result = predict_game(game["visitor_team"], game["home_team"], simulations, game.get("date"), game.get("id"))
            if result.get("error"):
                st.error(result["error"])
            else:
                a, b, c = st.columns(3)
                a.metric(f"{game['visitor_team']['abbreviation']} win estimate", f"{result['away_win']:.1%}")
                b.metric(f"{game['home_team']['abbreviation']} win estimate", f"{result['home_win']:.1%}")
                c.metric("Projected total", f"{result['total']:.1f}")
                st.write(f"**Projected score:** {game['visitor_team']['abbreviation']} {result['away_score']:.1f} – {game['home_team']['abbreviation']} {result['home_score']:.1f}")
                st.write(f"**Recent form:** {game['visitor_team']['abbreviation']} {result['away_form']:+.1f} margin ({result['away_games']} games) · {game['home_team']['abbreviation']} {result['home_form']:+.1f} ({result['home_games']} games)")
                st.write(f"**Rest:** {game['visitor_team']['abbreviation']} {result['away_rest_days']} days · {game['home_team']['abbreviation']} {result['home_rest_days']} days · **H2H sample:** {result['h2h_games']}")
                st.write(f"**Injury adjustment:** {game['visitor_team']['abbreviation']} −{result['away_injury_penalty']:.1f} pts ({result['away_injured_count']} listed) · {game['home_team']['abbreviation']} −{result['home_injury_penalty']:.1f} pts ({result['home_injured_count']} listed)")
                st.caption(result["note"])
                st.warning("These are model estimates, not guaranteed outcomes. Review the latest injury report before tip-off.")
    st.divider()
    st.caption(f"Slate date: {today} · Only upcoming games are simulated; completed/live games are excluded.")

with tabs[1]:
    st.subheader("AI parlay lab")
    st.caption("One projection engine powers the player board and every parlay leg. Suggested lines are model targets, not confirmed sportsbook offerings.")
    leg_count = st.select_slider("Build parlays with", options=[2, 3, 4, 5], value=3, key="parlay_legs")
    if st.button("Build / refresh AI parlays", type="primary", key="build_ai_parlays"):
        if not scheduled:
            st.warning("No upcoming games are available for this date.")
        else:
            try:
                with st.spinner("Verifying player availability and loading player game logs…"):
                    board = build_player_projection_board(scheduled, max_players_per_team=6)
                    legs = build_model_legs(board, min_sample=8, min_probability=0.58)
                    candidate_sets = {}
                    for size in (2, 3, 4, 5):
                        candidate_sets[size] = build_candidates(legs, size, 5)
                st.session_state["nba_edge_board"] = board
                st.session_state["nba_edge_legs"] = legs
                st.session_state["nba_edge_candidate_sets"] = candidate_sets
                st.success(f"Loaded {len(board)} player-stat projections, {len(legs)} eligible prop targets, and built parlays from 2 through 5 legs.")
            except Exception as exc:
                st.session_state["nba_edge_board"] = []
                st.session_state["nba_edge_legs"] = []
                st.session_state["nba_edge_candidate_sets"] = {}
                st.error(f"Parlay build stopped: {type(exc).__name__}: {exc}")
                st.info("The builder will not assume a player is healthy when availability cannot be verified.")

    board = st.session_state.get("nba_edge_board", [])
    legs = st.session_state.get("nba_edge_legs", [])
    candidate_sets = st.session_state.get("nba_edge_candidate_sets", {})

    if board:
        st.markdown("### Player projection board")
        st.caption("Recent hit rate is calculated against each model-suggested line using the available player game-log sample. Confidence is sample-based, not a guarantee.")
        target_rows = []
        for leg in legs:
            target_rows.append({
                "Player": leg["player"],
                "Matchup": leg["matchup"],
                "Prop": f'{leg["direction"].upper()} {leg["line"]} {leg["market"]}',
                "Projection": leg["projection"],
                "Recent hit rate": leg["consistency_rate"],
                "Model estimate": leg["probability"],
                "Confidence floor": leg["confidence_score"],
                "Games": leg["confidence_sample"],
                "Minutes": leg["minutes"],
                "Injury": leg.get("injury_status", "not listed")
            })
        if target_rows:
            target_frame = pd.DataFrame(target_rows)
            for col in ("Recent hit rate", "Model estimate", "Confidence floor"):
                target_frame[col] = target_frame[col].map(lambda value: f"{value:.1%}")
            st.dataframe(target_frame.head(50), use_container_width=True, hide_index=True)
        else:
            st.info("No player props met the minimum sample and model-support filters for this slate.")

        st.markdown("### Best parlay combinations")
        st.caption("Ranked by model edge and prop diversity. The independence product is deliberately not shown as a true parlay probability; use Monte Carlo below for an empirical estimate.")
        for size in (2, 3, 4, 5):
            group = candidate_sets.get(size, [])
            with st.expander(f"{size}-leg parlays · {len(group)} candidates", expanded=(size == leg_count)):
                if not group:
                    st.info(f"Not enough distinct games with qualified player samples to build a {size}-leg parlay.")
                    continue
                for index, candidate in enumerate(group, 1):
                    title = f"Option {index} · average model edge {candidate['mean_edge']:.1%} · prop diversity {candidate['market_diversity']:.0%}"
                    with st.container(border=True):
                        st.markdown(f"**{title}**")
                        rows = []
                        for leg in candidate["legs"]:
                            rows.append({
                                "Player": leg["player"],
                                "Matchup": leg["matchup"],
                                "Selection": f'{leg["direction"].upper()} {leg["line"]} {leg["market"]}',
                                "Projection": leg["projection"],
                                "Historical hit rate": leg["consistency_rate"],
                                "Model estimate": leg["probability"],
                                "Sample": leg["confidence_sample"]
                            })
                        frame = pd.DataFrame(rows)
                        for col in ("Historical hit rate", "Model estimate"):
                            frame[col] = frame[col].map(lambda value: f"{value:.1%}")
                        st.dataframe(frame, use_container_width=True, hide_index=True)
                        sim_runs = st.select_slider(
                            "Monte Carlo simulations",
                            options=[5000, 10000, 20000, 50000],
                            value=20000,
                            key=f"sim_runs_{size}_{index}"
                        )
                        sim_key = f"parlay_sim_{size}_{index}"
                        if st.button("Run Monte Carlo simulation", key=f"simulate_parlay_{size}_{index}"):
                            try:
                                with st.spinner("Sampling historical player-game outcomes…"):
                                    result = simulate_parlay(candidate["legs"], simulations=sim_runs)
                                st.session_state[sim_key] = result
                            except Exception as exc:
                                st.session_state.pop(sim_key, None)
                                st.error(f"Simulation unavailable: {type(exc).__name__}: {exc}")
                        sim_result = st.session_state.get(sim_key)
                        if sim_result:
                            a, b, c = st.columns(3)
                            a.metric("Estimated parlay hit rate", f"{sim_result['parlay_hit_rate']:.1%}")
                            b.metric("95% Monte Carlo interval", f"{sim_result['confidence_low']:.1%}–{sim_result['confidence_high']:.1%}")
                            c.metric("Simulation runs", f"{sim_result['simulations']:,}")
                            leg_results = []
                            for leg, rate in zip(candidate["legs"], sim_result["leg_hit_rates"]):
                                leg_results.append(f"{leg['player']} {leg['market']}: {rate:.1%}")
                            st.write("**Simulated leg hit rates:** " + " · ".join(leg_results))
                            st.caption(f"Sampling method: {sim_result['method']} · Shared historical dates: {sim_result['overlap_dates']}")
                            st.warning(sim_result["warning"])
                        st.caption(candidate["warning"])
        st.info("Important: historical hit rates and bootstrap simulations describe past samples. They are not calibrated sportsbook odds, do not guarantee future results, and may assume independence when players lack enough shared game dates.")
    else:
        st.info("Tap Build / refresh AI parlays to load the slate, verify player availability, and generate the projection board and 2–5 leg combinations.")

st.sidebar.subheader("Data status")
st.sidebar.write(f"NBA provider: {'Connected' if api_key() else 'Missing key'}")
st.sidebar.write(f"Upcoming games: {len(scheduled)}")
if st.sidebar.button("Refresh provider data", use_container_width=True):
    st.cache_data.clear()
    st.session_state.pop("nba_edge_board", None)
    st.session_state.pop("nba_edge_candidates", None)
    st.rerun()
st.sidebar.caption("Only two core tools are shown: game simulation and AI parlays.")
