import streamlit as st
import pandas as pd
from datetime import date
from bdl import api_key, games_for_date, injuries, projected_lineups, game_lineups, player_props, game_odds, freshness_label, search_players, search_teams, team_games_history, current_season_start
from model import predict_game, project_player
from prop_engine import analyze_props
from parlays import build_candidates
from tracker import init_db, save_game_prediction, save_prop_prediction, load_predictions, grade_completed

st.set_page_config(page_title="NBA Edge AI",page_icon="🏀",layout="wide")
init_db()
st.title("🏀 NBA Edge AI")
st.caption("NBA-only prediction lab · player projections · injuries · lineups · market edges · parlay research")
if not api_key():
    st.warning("Connect your BALLDONTLIE API key to activate premium NBA data. Do not paste the key into chat.")
    st.markdown("[Create your BALLDONTLIE account](https://app.balldontlie.io/) · [API documentation](https://docs.balldontlie.io/)")
    st.code('BALLDONTLIE_API_KEY = "YOUR_KEY"\nBALLDONTLIE_RPM = 5',language="toml")
    st.stop()

today=date.today().isoformat()
with st.sidebar:
    st.subheader("Data controls")
    st.caption("NBA GOAT is recommended for injuries, lineups, props, odds and advanced endpoints.")
    if st.button("↻ Clear cached data and refresh",use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Slate date: {today}")
    st.caption("Provider data timestamps are shown where supplied.")

tabs=st.tabs(["Today's slate","Game lab","Player projections","Injuries & lineups","Parlay builder","Accuracy tracker","Backtesting","Data health","Search players & teams"])
try:
    games=games_for_date(today)
    slate_error=None
except Exception as e:
    games=[]; slate_error=str(e)
game_labels={}
for g in games:
    away=(g.get("visitor_team") or {}).get("full_name","Away")
    home=(g.get("home_team") or {}).get("full_name","Home")
    game_labels[f"{away} @ {home} · {g.get('status','')} · #{g.get('id')}"]=g

with tabs[0]:
    st.subheader("Today's NBA slate")
    if slate_error: st.error(slate_error)
    elif not games: st.info("No games returned for this date, or the provider has not posted the schedule.")
    else:
        odds_by_game={}
        try:
            for o in game_odds(today): odds_by_game.setdefault(o.get("game_id"),[]).append(o)
        except Exception as e: st.caption(f"Odds feed unavailable: {e}")
        for g in games:
            away=g.get("visitor_team") or {}; home=g.get("home_team") or {}
            a,b,c=st.columns([3,3,2])
            a.markdown(f"**{away.get('full_name','Away')}**")
            b.markdown(f"**{home.get('full_name','Home')}**")
            c.write(g.get("status",""))
            a.metric("Away score",g.get("visitor_team_score","—"))
            b.metric("Home score",g.get("home_team_score","—"))
            c.caption(g.get("datetime") or g.get("date",""))
            market=odds_by_game.get(g.get("id"),[])
            if market:
                m=market[0]
                st.caption(f"Market snapshot ({m.get('vendor','book')}): ML {m.get('moneyline_away_odds','—')} / {m.get('moneyline_home_odds','—')} · Spread {m.get('spread_away_value','—')} / {m.get('spread_home_value','—')} · Total {m.get('total_value','—')} · {freshness_label(m.get('updated_at'))}")
            st.divider()

with tabs[1]:
    st.subheader("Game winner simulator")
    if games:
        selected=st.selectbox("Choose matchup",list(game_labels.keys()),key="game_lab")
        g=game_labels[selected]
        away=g["visitor_team"]; home=g["home_team"]
        sims=st.slider("Simulations",2000,50000,15000,1000)
        can_predict=(g.get("status_state")=="scheduled")
        if not can_predict:
            st.warning("Only upcoming scheduled games can be forecast. Live and completed games are excluded to prevent result leakage.")
        if st.button("Run matchup simulation",type="primary",disabled=not can_predict):
            with st.spinner("Analyzing recent team results…"):
                result=predict_game(away,home,sims,g.get("date"),g.get("id"))
            if result.get("error"): st.error(result["error"])
            else:
                x,y,z=st.columns(3)
                x.metric(f"{away['abbreviation']} win estimate",f"{result['away_win']:.1%}")
                y.metric(f"{home['abbreviation']} win estimate",f"{result['home_win']:.1%}")
                z.metric("Projected total",f"{result['total']:.1f}")
                st.write(f"Projected score: **{away['abbreviation']} {result['away_score']:.1f} – {home['abbreviation']} {result['home_score']:.1f}**")
                st.write(f"Recent scoring margin: {away['abbreviation']} {result['away_form']:+.1f} ({result['away_games']} games) · {home['abbreviation']} {result['home_form']:+.1f} ({result['home_games']} games)")
                st.write(f"Estimated injury adjustment (heuristic): {away['abbreviation']} −{result['away_injury_penalty']:.1f} pts · {home['abbreviation']} −{result['home_injury_penalty']:.1f} pts")
                st.write(f"Rest days: {away['abbreviation']} {result['away_rest_days']} · {home['abbreviation']} {result['home_rest_days']} · Head-to-head games sampled: {result['h2h_games']}")
                st.warning(result["note"])
                if st.button("Save game prediction",key="save_game"):
                    save_game_prediction(g,result); st.success("Saved before tip-off.")
    else: st.info("Today's game slate is unavailable.")
with tabs[2]:
    st.subheader("Player projection lab")
    player=st.text_input("Search player",placeholder="e.g. Nikola Jokic")
    stat=st.selectbox("Stat",["PTS","REB","AST","STL","BLK","MIN","3PM"])
    if st.button("Project player stat"):
        if not player.strip(): st.warning("Enter a player name.")
        else:
            with st.spinner("Loading player logs…"):
                try: result=project_player(player.strip(),stat)
                except Exception as e: result={"error":str(e)}
            if result.get("error"): st.error(result["error"])
            else:
                st.metric(f"{result['player']} projected {stat}",f"{result['projection']:.1f}")
                a,b,c,d,e=st.columns(5)
                a.metric("Last 5 avg",f"{result['last5']:.1f}")
                b.metric("Last 10 avg",f"{result['last10']:.1f}")
                c.metric("Season sample avg",f"{result['average']:.1f}")
                d.metric("Projected minutes",f"{result['minutes']:.1f}" if result["minutes"] else "Unavailable")
                e.metric("Season usage",f"{result['usage']:.1f}%" if result["usage"] is not None else "Unavailable")
                st.caption(f"Team: {result['team']} · Sample: {result['games']} games")
                st.line_chart(pd.DataFrame({"Recent game values":result["values"]}))
                st.warning(result["note"])
with tabs[3]:
    st.subheader("Injury report and lineup monitor")
    try:
        injury_rows=injuries()
        if injury_rows:
            injury_data=[]
            for x in injury_rows:
                p=x.get("player") or {}
                injury_data.append({"Player":f"{p.get('first_name','')} {p.get('last_name','')}","Team ID":p.get("team_id"),"Status":x.get("status"),"Description":x.get("description"),"Return":x.get("return_date")})
            st.dataframe(pd.DataFrame(injury_data),use_container_width=True,hide_index=True)
        else: st.info("No injury records returned by provider.")
    except Exception as e: st.error(f"Injury feed unavailable: {e}")
    if games:
        pick=st.selectbox("Lineup game",list(game_labels.keys()),key="lineup_game")
        lg=game_labels[pick]
        try:
            lineups=projected_lineups(lg["id"])
            if lineups:
                for lu in lineups:
                    st.markdown(f"**Team ID {lu.get('team_id')} · {str(lu.get('status','unknown')).upper()}** · {freshness_label(lu.get('updated_at'))}")
                    players=[{"Position":p.get("position"),"Player":f"{(p.get('player') or {}).get('first_name','')} {(p.get('player') or {}).get('last_name','')}"} for p in lu.get("lineup",[])]
                    st.dataframe(pd.DataFrame(players),use_container_width=True,hide_index=True)
            else: st.info("No projected lineup available yet. Missing does not mean confirmed inactive.")
            st.markdown("**Actual starting lineup and bench**")
            actual_lineups=game_lineups(lg["id"])
            if actual_lineups:
                actual_rows=[]
                for item in actual_lineups:
                    team_name=(item.get("team") or {}).get("full_name",str(item.get("team_id")))
                    p=item.get("player") or {}
                    actual_rows.append({"Team":team_name,"Player":f"{p.get('first_name','')} {p.get('last_name','')}","Starter":bool(item.get("starter")),"Position":item.get("position","")})
                st.dataframe(pd.DataFrame(actual_rows),use_container_width=True,hide_index=True)
            else: st.info("No official lineup records returned yet.")
        except Exception as e: st.error(f"Lineup feed unavailable: {e}")
with tabs[4]:
    st.subheader("Automatic 3–6 leg parlay research")
    st.caption("The builder compares recent player outcomes with current prop lines and removes repeated players and same-game combinations. It is not a guarantee of winning.")
    leg_count=st.slider("Parlay size",3,6,3,key="parlay_size")
    if st.button("Scan today's player props",type="primary"):
        candidates_legs=[]
        progress=st.progress(0)
        if not games: st.warning("No games available to scan.")
        else:
            for i,g in enumerate(games):
                try:
                    props=player_props(g["id"])
                    candidates_legs.extend(analyze_props(g,props,max_players=25))
                except Exception as e:
                    st.caption(f"Props unavailable for game {g.get('id')}: {e}")
                progress.progress((i+1)/len(games))
            st.session_state["prop_legs"]=candidates_legs
            st.session_state["prop_candidates"]=build_candidates(candidates_legs,leg_count,20)
            st.success(f"Scanned {len(candidates_legs)} modelled prop candidates.")
    legs=st.session_state.get("prop_legs",[])
    if legs:
        st.markdown("**Best individual edges (model estimate vs available market price)**")
        st.dataframe(pd.DataFrame(legs[:30]),use_container_width=True,hide_index=True)
        candidates=build_candidates(legs,leg_count,20)
        if candidates:
            st.markdown(f"**Top {leg_count}-leg combinations**")
            for i,candidate in enumerate(candidates[:5]):
                with st.expander(f"Combination {i+1} · mean edge {candidate['mean_edge']:.1%}"):
                    for leg in candidate["legs"]:
                        st.write(f"{leg['player']} — {leg['direction'].upper()} {leg['line']} {leg['market']} · projection {leg['projection']:.1f} · estimated probability {leg['probability']:.1%} · edge {leg['edge']:.1%}")
                    st.caption(candidate["warning"])
                    if st.button("Save these legs",key=f"save_combo_{i}"):
                        for leg in candidate["legs"]: save_prop_prediction(leg["game_id"],leg)
                        st.success("Saved all legs for post-game grading.")
        else: st.warning("Not enough different games with supported props and usable recent logs to make this size parlay.")
    else: st.info("Tap Scan today's player props to build candidate legs from current provider lines.")
with tabs[5]:
    st.subheader("Accuracy tracker")
    if st.button("Grade all completed games and props"):
        with st.spinner("Checking completed box scores…"):
            try: st.write(grade_completed())
            except Exception as e: st.error(f"Grading failed: {e}")
    try:
        game_hist,prop_hist=load_predictions()
        if not game_hist.empty:
            st.markdown("**Game winner predictions**")
            st.dataframe(game_hist,use_container_width=True,hide_index=True)
            graded=game_hist[game_hist["graded"]==1]
            if len(graded):
                correct=((graded.apply(lambda r: (r["home"] if r["p_home"]>=0.5 else r["away"])==r["actual_winner"],axis=1))).mean()
                st.metric("Winner-direction accuracy",f"{correct:.1%}",f"{len(graded)} graded")
        if not prop_hist.empty:
            st.markdown("**Player prop predictions**")
            st.dataframe(prop_hist,use_container_width=True,hide_index=True)
            graded_props=prop_hist[prop_hist["graded"]==1]
            if len(graded_props): st.metric("Player prop hit rate",f"{graded_props.hit.mean():.1%}",f"{len(graded_props)} graded legs")
        if game_hist.empty and prop_hist.empty: st.info("Save predictions before games to start the record.")
    except Exception as e: st.error(f"History unavailable: {e}")
with tabs[6]:
    st.subheader("Historical player projection backtest")
    st.caption("Walk-forward testing uses only earlier games to predict later games; it does not use future data.")
    bt_player=st.text_input("Player to backtest",placeholder="e.g. Jayson Tatum",key="bt_player")
    bt_stat=st.selectbox("Backtest stat",["PTS","REB","AST","STL","BLK","MIN","3PM"],key="bt_stat")
    if st.button("Run walk-forward backtest"):
        from backtest import player_walk_forward
        with st.spinner("Testing historical projections…"):
            try: bt,note=player_walk_forward(bt_player,bt_stat)
            except Exception as e: bt,note=None,str(e)
        if bt:
            a,b,c=st.columns(3)
            a.metric("Mean absolute error",f"{bt['mae']:.2f}")
            b.metric("Root mean squared error",f"{bt['rmse']:.2f}")
            c.metric("Average bias",f"{bt['bias']:+.2f}")
            st.write(f"Tested {bt['games']} historical games for {bt['player']} ({bt_stat}).")
            st.line_chart(bt["rows"].set_index("date")[["predicted","actual"]])
            st.dataframe(bt["rows"],use_container_width=True,hide_index=True)
        else: st.warning(note)

with tabs[7]:
    st.subheader("Data health and source limitations")
    st.write(f"Provider key: {'Connected' if api_key() else 'Missing'}")
    st.write(f"Schedule: {'Loaded' if games else 'No records returned'} · {today}")
    st.write("Injuries and lineups: BALLDONTLIE GOAT endpoints; always inspect status and updated_at.")
    st.write("Player props: live market snapshot. Provider notes that props are not historically stored and may disappear as games near completion.")
    st.write("Team model: recent scoring margin, team pace/efficiency, home court, rest and a small head-to-head adjustment. Player on/off impact, role-change adjustments and opponent positional defense remain planned upgrades. Walk-forward player-stat backtesting is available in the Backtesting tab.")
    st.write("Cloud SQLite storage may reset on redeploy/restart. For durable season-long accuracy tracking, connect persistent Postgres.")
    st.caption("No model probability is a guarantee. Missing or stale data should reduce confidence, not be silently filled.")


with tabs[8]:
    st.subheader("Search the NBA")
    st.caption("Look up any player or NBA team by name, nickname, abbreviation or city. This is an additional search area; all existing tabs remain available.")
    player_col, team_col = st.columns(2)
    with player_col:
        st.markdown("**Player search**")
        player_query = st.text_input("Player name", placeholder="e.g. Anthony Edwards", key="directory_player_query")
        if st.button("Search players", key="directory_player_search"):
            if not player_query.strip():
                st.warning("Enter a player name first.")
            else:
                try:
                    found_players = search_players(player_query.strip())
                    st.session_state["directory_players"] = found_players
                    st.session_state["directory_player_query_done"] = player_query.strip()
                except Exception as e:
                    st.error(f"Player search failed: {e}")
        found_players = st.session_state.get("directory_players", [])
        if found_players:
            player_options = {
                f"{p.get('first_name','')} {p.get('last_name','')} · {((p.get('team') or {}).get('abbreviation') or 'Free agent')} · {'Active' if p.get('is_active') else 'Inactive'} · ID {p.get('id')}": p
                for p in found_players
            }
            selected_player_label = st.selectbox("Matching players", list(player_options.keys()), key="directory_player_choice")
            selected_player = player_options[selected_player_label]
            st.write(f"**Player:** {selected_player.get('first_name','')} {selected_player.get('last_name','')}")
            st.write(f"**Team:** {(selected_player.get('team') or {}).get('full_name','Not listed')}")
            st.write(f"**Position:** {selected_player.get('position') or 'Not listed'}")
            st.write(f"**Active:** {'Yes' if selected_player.get('is_active') else 'No'}")
            st.caption(f"Provider player ID: {selected_player.get('id')}")
            quick_stat = st.selectbox("Quick projection stat", ["PTS","REB","AST","STL","BLK","MIN","3PM"], key="directory_player_stat")
            if st.button("Project selected player", key="directory_player_project"):
                with st.spinner("Calculating player projection…"):
                    try:
                        result = project_player(f"{selected_player.get('first_name','')} {selected_player.get('last_name','')}", quick_stat)
                        if result.get("error"):
                            st.error(result["error"])
                        else:
                            st.metric(f"{result['player']} projected {quick_stat}", f"{result['projection']:.1f}")
                            a,b,d = st.columns(3)
                            a.metric("Last 5 average", f"{result['last5']:.1f}")
                            b.metric("Last 10 average", f"{result['last10']:.1f}")
                            d.metric("Projected minutes", f"{result['minutes']:.1f}" if result["minutes"] else "Unavailable")
                    except Exception as e:
                        st.error(f"Projection failed: {e}")
        elif st.session_state.get("directory_player_query_done"):
            st.info("No player matches returned. Try a shorter name or surname.")
    with team_col:
        st.markdown("**Team search**")
        team_query = st.text_input("Team name, city or abbreviation", placeholder="e.g. Lakers, Los Angeles or LAL", key="directory_team_query")
        if st.button("Search teams", key="directory_team_search"):
            if not team_query.strip():
                st.warning("Enter a team, city or abbreviation first.")
            else:
                try:
                    found_teams = search_teams(team_query.strip())
                    st.session_state["directory_teams"] = found_teams
                    st.session_state["directory_team_query_done"] = team_query.strip()
                except Exception as e:
                    st.error(f"Team search failed: {e}")
        found_teams = st.session_state.get("directory_teams", [])
        if found_teams:
            team_options = {f"{t.get('full_name', t.get('name','NBA Team'))} · {t.get('abbreviation','')}": t for t in found_teams}
            selected_team_label = st.selectbox("Matching teams", list(team_options.keys()), key="directory_team_choice")
            selected_team = team_options[selected_team_label]
            st.write(f"**Team:** {selected_team.get('full_name', selected_team.get('name',''))}")
            st.write(f"**Abbreviation:** {selected_team.get('abbreviation','—')}")
            st.write(f"**City:** {selected_team.get('city','—')}")
            st.write(f"**Conference:** {selected_team.get('conference','—')}")
            st.write(f"**Division:** {selected_team.get('division','—')}")
            if st.button("Load recent team results", key="directory_team_results"):
                with st.spinner("Loading recent team schedule…"):
                    try:
                        team_rows = team_games_history(selected_team["id"], current_season_start())
                        finals = [g for g in team_rows if g.get("status_state") == "final" or str(g.get("status","")).lower() == "final"]
                        result_rows = []
                        for game in finals[:10]:
                            home = game.get("home_team") or {}
                            away = game.get("visitor_team") or {}
                            is_home = home.get("id") == selected_team["id"]
                            own_score = game.get("home_team_score") if is_home else game.get("visitor_team_score")
                            opp_score = game.get("visitor_team_score") if is_home else game.get("home_team_score")
                            opponent = away.get("full_name","") if is_home else home.get("full_name","")
                            result_rows.append({"Date":game.get("date",""),"Opponent":opponent,"Location":"Home" if is_home else "Away","Score":f"{own_score}-{opp_score}","Result":"W" if own_score is not None and opp_score is not None and own_score > opp_score else "L"})
                        if result_rows:
                            st.dataframe(pd.DataFrame(result_rows), use_container_width=True, hide_index=True)
                            wins = sum(1 for row in result_rows if row["Result"] == "W")
                            st.metric("Last 10 completed games", f"{wins}-{len(result_rows)-wins}")
                        else:
                            st.info("No completed team games were returned for the current season.")
                    except Exception as e:
                        st.error(f"Could not load team results: {e}")
        elif st.session_state.get("directory_team_query_done"):
            st.info("No team matches returned. Try a nickname, city or three-letter abbreviation.")
