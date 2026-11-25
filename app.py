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
    st.subheader("Data-driven AI parlays")
    st.caption("The model builds player targets from game logs, projected minutes and role trends. OUT, DOUBTFUL and QUESTIONABLE players are excluded. If injury status cannot be verified, parlay generation stops.")
    leg_count = st.slider("Parlay legs", min_value=2, max_value=5, value=3, key="parlay_legs")
    if st.button("Build AI parlays", type="primary", key="build_ai_parlays"):
        if not scheduled:
            st.warning("No upcoming games are available for this date.")
        else:
            try:
                with st.spinner("Verifying injuries and loading slate player data…"):
                    statuses = injury_status_map()
                    board = build_player_projection_board(scheduled, max_players_per_team=6)
                    board = [row for row in board if not is_unavailable(statuses.get(int(row["player_id"])))]
                    legs = build_model_legs(board, min_sample=8, min_probability=0.58)
                    candidates = build_candidates(legs, leg_count, 8)
                st.session_state["nba_edge_board"] = board
                st.session_state["nba_edge_candidates"] = candidates
                st.success(f"Loaded {len(board)} player-stat projections and generated {len(candidates)} candidate parlays.")
            except Exception as exc:
                st.session_state["nba_edge_candidates"] = []
                st.error(f"Parlay build stopped: {type(exc).__name__}: {exc}")
                st.info("The app will not guess that players are healthy or show parlays from an unverified injury feed.")
    board = st.session_state.get("nba_edge_board", [])
    candidates = st.session_state.get("nba_edge_candidates", [])
    if board:
        st.markdown("**Top model-supported player targets**")
        preview = pd.DataFrame([{
            "Player": x["player"], "Matchup": x["matchup"], "Stat": x["market"],
            "Projection": x["projection"], "Minutes": x["minutes"],
            "Recent 5": x["last5"], "Recent 10": x["last10"],
            "Games sampled": x["sample"], "Injury status": x.get("injury_status", "not listed")
        } for x in board[:30]])
        st.dataframe(preview, use_container_width=True, hide_index=True)
    if candidates:
        st.markdown("**Best candidate parlays**")
        for index, candidate in enumerate(candidates, 1):
            with st.expander(f"AI parlay {index} · model separation {candidate['mean_edge']:.1%}"):
                for leg in candidate["legs"]:
                    st.write(f"**{leg['player']}** — {leg['direction'].upper()} {leg['line']} {leg['market']} · projection {leg['projection']:.1f} · sample estimate {leg['probability']:.1%} · {leg['matchup']}")
                st.caption(candidate["warning"])
                sim_runs = st.select_slider("Monte Carlo runs", options=[5000, 10000, 20000, 50000], value=20000, key=f"sim_runs_{index}")
                if st.button("Simulate this parlay", key=f"simulate_parlay_{index}"):
                    try:
                        with st.spinner("Bootstrapping historical player-game outcomes…"):
                            result = simulate_parlay(candidate["legs"], simulations=sim_runs)
                        st.session_state[f"parlay_sim_{index}"] = result
                    except Exception as exc:
                        st.error(f"Parlay simulation unavailable: {type(exc).__name__}: {exc}")
                sim_result = st.session_state.get(f"parlay_sim_{index}")
                if sim_result:
                    x, y, z = st.columns(3)
                    x.metric("Estimated parlay hit rate", f"{sim_result['parlay_hit_rate']:.1%}")
                    y.metric("95% simulation interval", f"{sim_result['confidence_low']:.1%}–{sim_result['confidence_high']:.1%}")
                    z.metric("Simulations", f"{sim_result['simulations']:,}")
                    st.write("**Individual simulated leg hit rates:** " + " · ".join(
                        f"{leg['player']} {leg['market']}: {rate:.1%}"
                        for leg, rate in zip(candidate["legs"], sim_result["leg_hit_rates"])
                    ))
                    st.caption(f"Method: {sim_result['method']} · Shared historical dates: {sim_result['overlap_dates']}")
                    st.warning(sim_result["warning"])
                st.caption("Suggested lines are model-generated targets, not confirmed sportsbook lines or calibrated market probabilities. Check that the exact line is offered before betting.")
    elif board:
        st.info(f"Not enough distinct games with adequate player samples for a {leg_count}-leg parlay. Lower the leg count or try another slate.")
    else:
        st.info("Tap Build AI parlays to verify player availability, load the slate data and generate candidates.")

st.sidebar.subheader("Data status")
st.sidebar.write(f"NBA provider: {'Connected' if api_key() else 'Missing key'}")
st.sidebar.write(f"Upcoming games: {len(scheduled)}")
if st.sidebar.button("Refresh provider data", use_container_width=True):
    st.cache_data.clear()
    st.session_state.pop("nba_edge_board", None)
    st.session_state.pop("nba_edge_candidates", None)
    st.rerun()
st.sidebar.caption("Only two core tools are shown: game simulation and AI parlays.")
