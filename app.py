import streamlit as st
import pandas as pd
from datetime import date
from data import get_scoreboard, get_team_form, get_player_logs, refresh_cache, data_health
from model import predict_game, project_player
from parlays import build_parlay
from tracker import init_db, save_prediction, load_predictions, grade_predictions

st.set_page_config(page_title="NBA Edge AI", page_icon="🏀", layout="wide")
init_db()
st.title("🏀 NBA Edge AI")
st.caption("NBA game intelligence • player projections • simulation lab • $0 data stack")
with st.sidebar:
    st.subheader("Data controls")
    st.caption("Public NBA data can be delayed, throttled, or unavailable from cloud hosts.")
    if st.button("↻ Refresh NBA data", use_container_width=True):
        with st.spinner("Refreshing public NBA data…"):
            refresh_cache.clear()
            st.session_state["refresh_result"] = refresh_cache()
    if st.session_state.get("refresh_result"):
        st.success(st.session_state["refresh_result"])
    st.divider()
    st.caption("Model estimates are not guarantees or betting advice.")

tabs = st.tabs(["Today's slate", "Game lab", "Player projections", "Parlay builder", "Track record", "Data health"])
with tabs[0]:
    st.subheader("Today's NBA slate")
    games, note = get_scoreboard()
    st.caption(note)
    if games.empty:
        st.warning("The live scoreboard could not be loaded. Try Refresh, or return later. No games have been fabricated.")
    else:
        for _, g in games.iterrows():
            away, home = str(g.get("awayTeam",{}).get("teamName","Away")), str(g.get("homeTeam",{}).get("teamName","Home"))
            status = g.get("gameStatusText","")
            st.markdown(f"**{away}** at **{home}**  ·  {status}")
            c1,c2,c3 = st.columns([2,2,1])
            c1.metric(away, g.get("awayTeam",{}).get("score","—"))
            c2.metric(home, g.get("homeTeam",{}).get("score","—"))
            c3.write(g.get("gameEt",""))
            st.divider()
with tabs[1]:
    st.subheader("Game winner simulator")
    teams = ["ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"]
    a,b = st.columns(2)
    away = a.selectbox("Away team", teams, index=0)
    home = b.selectbox("Home team", teams, index=1)
    sims = st.slider("Monte Carlo simulations", 1000, 20000, 8000, 1000)
    if st.button("Simulate matchup", type="primary"):
        with st.spinner("Building matchup estimate…"):
            result = predict_game(away, home, sims)
        if result.get("error"):
            st.error(result["error"])
        else:
            x,y,z = st.columns(3)
            x.metric(f"{away} win estimate", f"{result['away_win']:.1%}")
            y.metric(f"{home} win estimate", f"{result['home_win']:.1%}")
            z.metric("Projected total", f"{result['total']:.1f}")
            st.write(f"Projected score: **{away} {result['away_score']:.1f} – {home} {result['home_score']:.1f}**")
            st.caption(result["explanation"])
            if st.button("Save this prediction"):
                save_prediction(away,home,result)
                st.success("Prediction saved.")
with tabs[2]:
    st.subheader("Player stat projection")
    player = st.text_input("Player name", placeholder="e.g. Jayson Tatum")
    stat = st.selectbox("Stat category", ["PTS","REB","AST","STL","BLK","MIN"])
    if st.button("Project player"):
        if not player.strip():
            st.warning("Enter a player name.")
        else:
            with st.spinner("Loading recent game logs…"):
                result = project_player(player.strip(),stat)
            if result.get("error"):
                st.error(result["error"])
            else:
                st.metric(f"Projected {stat}", f"{result['projection']:.1f}")
                st.write(f"Recent average: **{result['average']:.1f}** · Median: **{result['median']:.1f}** · Games sampled: **{result['games']}**")
                st.caption(result["note"])
                if not result.get("minutes_reliable",False):
                    st.warning("Minutes/role uncertainty can materially change this projection.")
with tabs[3]:
    st.subheader("Parlay research board")
    st.info("Build a research shortlist from manually entered model estimates. Correlated legs are flagged; combined probability is intentionally not presented as a precise hit rate.")
    raw = st.text_area("One leg per line: description, probability (0–1), correlation group\nExample: Celtics win,0.63,BOS game", height=130)
    count = st.slider("Legs to include",3,6,3)
    if st.button("Build shortlist"):
        legs=[]
        for line in raw.splitlines():
            parts=[p.strip() for p in line.split(",")]
            if len(parts)>=2:
                try: legs.append({"name":parts[0],"p":float(parts[1]),"group":parts[2] if len(parts)>2 else ""})
                except ValueError: pass
        chosen,warnings = build_parlay(legs,count)
        if not chosen: st.warning("Enter at least three valid legs with probabilities from 0 to 1.")
        else:
            st.dataframe(pd.DataFrame(chosen),use_container_width=True,hide_index=True)
            for w in warnings: st.warning(w)
            st.caption("This ranks entered estimates; it does not verify lines, injuries, odds, or actual market value.")
with tabs[4]:
    st.subheader("Prediction history")
    if st.button("Grade completed predictions"):
        st.write(grade_predictions())
    hist=load_predictions()
    if hist.empty: st.info("Saved predictions will appear here.")
    else: st.dataframe(hist,use_container_width=True,hide_index=True)
with tabs[5]:
    st.subheader("Data health")
    health=data_health()
    for item in health: st.write("• "+item)
    st.caption("NBA Stats access may fail or be delayed, especially on hosted servers. The app will show errors rather than invent data.")
