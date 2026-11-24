import streamlit as st
import pandas as pd
from datetime import date
from bdl import api_key, games_for_date, injuries, projected_lineups, game_lineups, game_odds, freshness_label, search_players, search_teams, team_games_history, current_season_start
from model import predict_game, project_player
from prop_engine import build_player_projection_board, build_model_legs, evaluate_manual_lines
from parlays import build_candidates
from tracker import init_db, save_game_prediction, save_prop_prediction, load_predictions, grade_completed
from matchup_engine import analyze_matchup, team_injury_context
from odds_monitor import record_snapshot, movement_history

st.set_page_config(page_title="NBA Edge AI",page_icon="🏀",layout="wide")
init_db()
st.title("🏀 NBA Edge AI")
st.caption("NBA-only prediction lab · player projections · injuries · lineups · market edges · parlay research")
if not api_key():
    st.warning("Connect your BALLDONTLIE API key to activate premium NBA data. Do not paste the key into chat.")
    st.markdown("[Create your BALLDONTLIE account](https://app.balldontlie.io/) · [API documentation](https://docs.balldontlie.io/)")
    st.code('BALLDONTLIE_API_KEY = "YOUR_KEY"\nBALLDONTLIE_RPM = 30',language="toml")
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

tabs=st.tabs(["Today's slate","Game lab","Player projections","Injuries & lineups","Parlay builder","Accuracy tracker","Backtesting","Data health","Search players & teams","Matchup & role lab","Odds movement"])
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
        can_predict=(g.get("status_state")=="scheduled" or (not g.get("status_state") and str(g.get("status","")).lower() not in ("final","in progress","live") and str(g.get("date",today)) >= today))
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
    st.subheader('Model-only parlay research')
    st.caption('No sportsbook feed is required. AI parlays are generated from player game logs, recent minutes and role trends. Optional opponent advanced feeds are skipped to respect your 5-requests-per-minute provider limit.')
    leg_count=st.slider('Parlay size',3,6,3,key='parlay_size')
    if st.button('Build player projection board',type='primary'):
        if not games: st.warning('No games are available for this date.')
        else:
            with st.spinner('Loading team rosters and recent player game logs…'):
                try:
                    board=build_player_projection_board(games)
                    st.session_state['model_player_board']=board
                    st.session_state['model_auto_legs']=build_model_legs(board)
                    if board: st.success(f'Built {len(board)} player-stat projections and {len(st.session_state["model_auto_legs"])} model-generated legs.')
                    else: st.warning('No player projections returned. Check Data Health and player/team game-log access.')
                except Exception as e: st.error(f'Projection board failed: {type(e).__name__}: {e}')
    if st.session_state.get('model_auto_legs'):
        st.subheader('AI-generated parlay candidates')
        st.caption('Suggested target lines are calculated from player game logs, projected minutes, role trend and available opponent defense/pace data. They are model targets, not confirmed sportsbook lines.')
        auto_legs=st.session_state['model_auto_legs']
        auto_candidates=build_candidates(auto_legs,leg_count,10)
        if auto_candidates:
            for i,candidate in enumerate(auto_candidates[:5]):
                with st.expander(f"AI parlay {i+1} · {candidate['mean_edge']:.1%} average model separation"):
                    for leg in candidate['legs']:
                        st.write(f"{leg['player']} — {leg['direction'].upper()} {leg['line']} {leg['market']} · projection {leg['projection']:.1f} · sample hit estimate {leg['probability']:.1%} · conservative confidence floor {leg.get('confidence_score',0):.1%} · {leg['matchup']}")
                    st.caption(candidate['warning'] + " Check that each suggested line is available at your sportsbook.")
        else:
            st.info(f"Not enough different games with supported player samples for a {leg_count}-leg parlay. Try fewer legs or another slate.")
    raw_board=st.session_state.get('model_player_board',[])
    if raw_board:
        st.write('Enter a sportsbook line for each player/stat you want to evaluate. Leave unused rows blank.')
        editable=pd.DataFrame([{k:v for k,v in r.items() if not k.startswith('_')} for r in raw_board])
        edited=st.data_editor(editable,use_container_width=True,hide_index=True,
            column_config={'line':st.column_config.NumberColumn('Your book line',help='Enter the actual line; leave blank to skip.',format='%.1f')},
            disabled=[c for c in editable.columns if c!='line'],key='model_board_editor')
        if st.button('Evaluate entered lines'):
            merged=[]
            for i,row in edited.iterrows():
                item=dict(raw_board[i]); item['line']=row.get('line'); merged.append(item)
            legs=evaluate_manual_lines(merged)
            st.session_state['model_manual_legs']=legs
            st.success(f'Evaluated {len(legs)} entered player lines.')
    legs=st.session_state.get('model_manual_legs',[])
    if legs:
        st.subheader('Model estimates against your entered lines')
        st.dataframe(pd.DataFrame(legs).drop(columns=['game_id','player_id'],errors='ignore'),use_container_width=True,hide_index=True)
        st.caption("Confidence score is the Wilson lower confidence bound from the player's recent game-log sample. It is a conservative sample-quality indicator, not sportsbook-calibrated win probability.")
        candidates=build_candidates(legs,leg_count,20)
        if candidates:
            st.subheader(f'Top {leg_count}-leg combinations')
            for i,candidate in enumerate(candidates[:5]):
                with st.expander(f'Combination {i+1} · average model separation {candidate["mean_edge"]:.1%}'):
                    for leg in candidate['legs']:
                        st.write(f'{leg["player"]} — {leg["direction"].upper()} {leg["line"]} {leg["market"]} · projection {leg["projection"]:.1f} · model estimate {leg["probability"]:.1%}')
                    st.caption('Recent historical outcomes are not calibrated sportsbook edges. Different-game selection does not make legs independent.')
                    if st.button('Save these legs',key=f'save_model_combo_{i}'):
                        for leg in candidate['legs']: save_prop_prediction(leg['game_id'],leg)
                        st.success('Saved legs for post-game grading.')
        else: st.info('Not enough distinct games with entered lines and supported samples for this parlay size.')
    else: st.info('Tap Build player projection board above. It will generate the player projections and AI parlay candidates in the same run; no sportsbook lines or odds feed are required.')
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
            st.download_button("Download game prediction history CSV", game_hist.to_csv(index=False).encode("utf-8"), "nba_game_predictions.csv", "text/csv")
            graded=game_hist[game_hist["graded"]==1]
            if len(graded):
                correct=((graded.apply(lambda r: (r["home"] if r["p_home"]>=0.5 else r["away"])==r["actual_winner"],axis=1))).mean()
                st.metric("Winner-direction accuracy",f"{correct:.1%}",f"{len(graded)} graded")
            graded["actual_home_win"] = (graded["actual_winner"] == graded["home"]).astype(float)
            game_brier = ((graded["p_home"] - graded["actual_home_win"]) ** 2).mean()
            st.metric("Game probability Brier score", f"{game_brier:.3f}", "Lower is better; 0 is perfect")
        if not prop_hist.empty:
            st.markdown("**Player prop predictions**")
            st.dataframe(prop_hist,use_container_width=True,hide_index=True)
            st.download_button("Download player prop history CSV", prop_hist.to_csv(index=False).encode("utf-8"), "nba_prop_predictions.csv", "text/csv")
            graded_props=prop_hist[prop_hist["graded"]==1]
            if len(graded_props):
                st.metric("Player prop hit rate",f"{graded_props.hit.mean():.1%}",f"{len(graded_props)} graded legs")
                prop_brier = ((graded_props["probability"] - graded_props["hit"]) ** 2).mean()
                st.metric("Player prop probability Brier score", f"{prop_brier:.3f}", "Lower is better; 0 is perfect")
        if game_hist.empty and prop_hist.empty: st.info("Save predictions before games to start the record.")
    except Exception as e: st.error(f"History unavailable: {e}")
with tabs[6]:
    st.subheader("Historical player projection backtest")
    st.caption("Walk-forward testing uses only earlier games to predict later games. Historical sportsbook prop lines are not included in the current provider feed.")
    bt_players=st.text_input("Players to compare (comma-separated, up to 8)",placeholder="Anthony Davis, Jayson Tatum, Nikola Jokic",key="bt_players")
    bt_stat=st.selectbox("Backtest stat",["PTS","REB","AST","STL","BLK","MIN","3PM"],key="bt_stat")
    bt_line_text=st.text_input("Optional fixed prop line (leave blank for projection accuracy only)",placeholder="e.g. 24.5",key="bt_line")
    bt_line=None
    if bt_line_text.strip():
        try: bt_line=float(bt_line_text.strip())
        except ValueError: st.warning("Enter a numeric prop line, or leave it blank.")
    if st.button("Run NBA Edge accuracy tests"):
        from backtest import player_walk_forward, multi_player_walk_forward
        names=[x.strip() for x in bt_players.split(",") if x.strip()]
        if not names:
            st.warning("Enter at least one player.")
        elif bt_line_text.strip() and bt_line is None:
            st.warning("The prop line must be numeric.")
        else:
            with st.spinner("Running leakage-safe walk-forward tests. This can take a little while for several players…"):
                try:
                    comparison,errors=multi_player_walk_forward(names,bt_stat,line=bt_line)
                    st.session_state["nba_edge_bt_comparison"]=comparison
                    st.session_state["nba_edge_bt_errors"]=errors
                    first,note=player_walk_forward(names[0],bt_stat,line=bt_line)
                    st.session_state["nba_edge_bt_detail"]=first
                    st.session_state["nba_edge_bt_note"]=note
                except Exception as e:
                    st.error(f"Backtest failed: {type(e).__name__}: {e}")
    comparison=st.session_state.get("nba_edge_bt_comparison")
    if comparison is not None and not comparison.empty:
        st.markdown("**Player consistency and accuracy leaderboard**")
        st.dataframe(comparison,use_container_width=True,hide_index=True)
        if bt_line is not None and "line_hit_rate" in comparison:
            valid=comparison.dropna(subset=["line_hit_rate"])
            if not valid.empty:
                best=valid.iloc[0]
                st.metric("Best historical line hit rate in this test",f"{best['line_hit_rate']:.1%}",f"{best['player']} · {int(best['line_games'])} non-push games")
        st.caption("The consistency leaderboard is based on the fixed line you entered. It is historical performance, not a guarantee or a verified sportsbook backtest.")
    for issue in st.session_state.get("nba_edge_bt_errors",[]):
        st.warning(issue)
    bt=st.session_state.get("nba_edge_bt_detail")
    if bt:
        st.markdown(f"**Detailed walk-forward results: {bt['player']} ({bt_stat})**")
        a,b,c=st.columns(3)
        a.metric("Mean absolute error",f"{bt['mae']:.2f}")
        b.metric("Root mean squared error",f"{bt['rmse']:.2f}")
        c.metric("Average bias",f"{bt['bias']:+.2f}")
        d,e,f=st.columns(3)
        d.metric("Within 2 units",f"{bt['within_2']:.1%}")
        e.metric("Within 3 units",f"{bt['within_3']:.1%}")
        f.metric("Within 5 units",f"{bt['within_5']:.1%}")
        if bt.get("line") is not None:
            st.metric("Over/under direction hit rate",f"{bt['line_hit_rate']:.1%}" if bt.get("line_hit_rate") is not None else "Not enough graded games",f"{bt['line_games']} non-push games · {bt['pushes']} pushes")
        if bt.get("confidence_within_3_mean") is not None:
            st.write(f"Rolling confidence estimate of being within 3 units: {bt['confidence_within_3_mean']:.1%} · Observed rate in those later tests: {bt['observed_within_3_when_calibrated']:.1%}")
        st.line_chart(bt["rows"].set_index("date")[["predicted","actual"]])
        st.dataframe(bt["rows"],use_container_width=True,hide_index=True)
        st.caption(st.session_state.get("nba_edge_bt_note",""))
    elif st.session_state.get("nba_edge_bt_comparison") is not None:
        st.info("No detailed player result is available yet.")

with tabs[7]:
    st.subheader("Data health and source limitations")
    st.write(f"Provider key: {'Connected' if api_key() else 'Missing'}")
    st.write(f"Schedule: {'Loaded' if games else 'No records returned'} · {today}")
    st.write("Injuries and lineups: BALLDONTLIE GOAT endpoints; always inspect status and updated_at.")
    st.write("Player props: live market snapshot. Provider notes that props are not historically stored and may disappear as games near completion.")
    st.write("Team model: recent scoring margin, pace/efficiency, home court, rest and head-to-head context. Player prop estimates now include opponent team defensive rating, recent opponent production allowed by player position (relative to league positional baselines), player H2H sample and recent minutes/usage trends. The Matchup & Role Lab also shows five-player lineup on/off net ratings and advanced player rates when coverage and minimum samples are available. Walk-forward player-stat backtesting is available in the Backtesting tab.")
    from storage import get_engine
    storage_type = get_engine().dialect.name
    st.write(f"Storage backend: {storage_type.upper()} · {'persistent managed database' if storage_type == 'postgresql' else 'local SQLite; hosted resets may clear history'}")
    st.write("For persistent history on Streamlit Cloud, configure DATABASE_URL with a managed PostgreSQL connection string in Streamlit Secrets.")
    st.caption("No model probability is a guarantee. Missing or stale data should reduce confidence, not be silently filled.")


with tabs[8]:
    st.subheader("Search the NBA")
    st.caption("Look up any player or NBA team by name, nickname, abbreviation or city. This is an additional search area; all existing tabs remain available.")
    player_col, team_col = st.columns(2)
    with player_col:
        st.markdown("**Player search**")
        player_query = st.text_input("Player name", placeholder="e.g. Anthony Edwards", key="directory_player_query")
        if st.button("Search players", key="directory_player_search"):
            st.session_state.pop("directory_players", None)
            st.session_state.pop("directory_player_query_done", None)
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
            st.session_state.pop("directory_teams", None)
            st.session_state.pop("directory_team_query_done", None)
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


with tabs[9]:
    st.subheader("Opponent matchup and role-change lab")
    st.caption("Combines recent player logs, opponent team defensive rating, head-to-head history and recent minutes/opportunity trends. Contextual adjustments are deliberately conservative.")
    query = st.text_input("Search player for matchup", placeholder="e.g. Shai Gilgeous-Alexander", key="matchup_player_query")
    if st.button("Find matchup player", key="matchup_player_search"):
        try:
            st.session_state["matchup_players"] = search_players(query.strip()) if query.strip() else []
        except Exception as e:
            st.error(f"Player lookup failed: {e}")
    player_matches = st.session_state.get("matchup_players", [])
    teams_for_matchup = search_teams("") if player_matches else []
    if player_matches and teams_for_matchup:
        player_map = {f"{x.get('first_name','')} {x.get('last_name','')} · {(x.get('team') or {}).get('abbreviation','FA')} · ID {x.get('id')}":x for x in player_matches}
        selected_matchup_player = player_map[st.selectbox("Player", list(player_map.keys()), key="matchup_player_pick")]
        team_map = {f"{x.get('full_name',x.get('name','Team'))} · {x.get('abbreviation','')}":x for x in teams_for_matchup}
        opponent = team_map[st.selectbox("Opponent", list(team_map.keys()), key="matchup_opponent_pick")]
        matchup_stat = st.selectbox("Projection stat", ["PTS","REB","AST","STL","BLK","MIN","3PM"], key="matchup_stat")
        if st.button("Analyze player vs opponent", type="primary", key="run_matchup"):
            with st.spinner("Reviewing player history, opponent defense and rotation trends…"):
                try:
                    result = analyze_matchup(selected_matchup_player["id"], opponent["id"], matchup_stat)
                    st.session_state["matchup_result"] = result
                    st.session_state["matchup_player_name"] = f"{selected_matchup_player.get('first_name','')} {selected_matchup_player.get('last_name','')}"
                    st.session_state["matchup_opponent_name"] = opponent.get("full_name", opponent.get("name","Opponent"))
                except Exception as e:
                    st.error(f"Matchup analysis failed: {e}")
    result = st.session_state.get("matchup_result")
    if result:
        if result.get("error"):
            st.warning(result["error"])
        else:
            st.markdown(f"**{st.session_state.get('matchup_player_name','Player')} vs {st.session_state.get('matchup_opponent_name','Opponent')}**")
            a,b,c = st.columns(3)
            a.metric("Base projection", f"{result['base_projection']:.1f}")
            b.metric("Context-adjusted estimate", f"{result['adjusted_projection']:.1f}", f"{result['adjusted_projection']-result['base_projection']:+.1f}")
            c.metric("H2H sample", f"{result['h2h_games']} games", f"{result['h2h_mean']:.1f} avg" if result["h2h_mean"] is not None else "No sample")
            st.write(f"**Rotation signal:** {result['role']['label']}")
            d,e,g = st.columns(3)
            d.metric("Recent minutes (L5)", f"{result['role']['recent_minutes']:.1f}" if result['role']['recent_minutes'] is not None else "N/A")
            e.metric("Prior minutes", f"{result['role']['prior_minutes']:.1f}" if result['role']['prior_minutes'] is not None else "N/A")
            g.metric("Minutes change", f"{result['role']['minutes_change']:+.1f}" if result['role']['minutes_change'] is not None else "N/A")
            st.write(f"Opponent defensive rating: {result['opponent_def_rating'] if result['opponent_def_rating'] is not None else 'Unavailable'} · Pace: {result['opponent_pace'] if result['opponent_pace'] is not None else 'Unavailable'} · Player log sample: {result['sample']}")
            pos = result.get("positional_defense") or {}
            allowed = pos.get("allowed_per36") or {}
            st.markdown(f"**Opponent defense vs {result.get('position') or 'unknown position'}** · {pos.get('opponent_games',0)} recent games · {pos.get('player_game_rows',0)} opponent player-game rows")
            pos_keys = [("pts","PTS allowed/36"),("reb","REB allowed/36"),("ast","AST allowed/36"),("fg3m","3PM allowed/36")]
            cols = st.columns(4)
            for col,(key,label) in zip(cols,pos_keys):
                value = allowed.get(key)
                col.metric(label, f"{value:.1f}" if value is not None else "N/A")
            st.caption(f"Positional adjustment to projection: {result.get('positional_adjustment',0):+.2f} · League positional baseline: {result.get('positional_baseline_per36') if result.get('positional_baseline_per36') is not None else 'Unavailable'}")
            lineup = result.get("lineup_impact") or {}
            st.markdown("**Player on/off lineup performance**")
            if lineup.get("net_diff") is not None:
                x,y,z = st.columns(3)
                x.metric("Net rating with player", f"{lineup['on_net']:.1f}")
                y.metric("Without player", f"{lineup['off_net']:.1f}")
                z.metric("On/off difference", f"{lineup['net_diff']:+.1f}")
                st.caption(f"Weighted over {lineup.get('games',0)} recent team games · {lineup.get('on_minutes',0):.0f} on-court lineup minutes and {lineup.get('off_minutes',0):.0f} off-court lineup minutes. Descriptive, not causal.")
            else:
                st.info("On/off split unavailable or below minimum sample (at least 60 lineup minutes and 3 lineup rows both with and without the player).")
            advanced = result.get("advanced") or {}
            if advanced:
                st.markdown("**Player advanced profile (season game-level averages)**")
                adv_cols = st.columns(4)
                for col,(key,label) in zip(adv_cols,[("usage_percentage","Usage"),("true_shooting_percentage","True shooting"),("net_rating","Net rating"),("matchup_fg_pct","Matchup FG%")]):
                    value = advanced.get(key)
                    col.metric(label, f"{value:.3f}" if value is not None and abs(value)<2 else (f"{value:.1f}" if value is not None else "N/A"))
            vacancy = result.get("team_injury_vacancy") or {}
            weighted = vacancy.get("weighted_vacated") or {}
            st.markdown("**Teammate injury / rotation context**")
            st.write(f"Weighted unavailable teammate production (status-adjusted estimate): {weighted.get('pts',0):.1f} PTS · {weighted.get('reb',0):.1f} REB · {weighted.get('ast',0):.1f} AST · {weighted.get('min',0):.1f} MIN")
            if result.get("other_injured_teammates"):
                st.dataframe(pd.DataFrame(result["other_injured_teammates"]),use_container_width=True,hide_index=True)
            else:
                st.caption("No other injured teammates with a usable status and season-average record were returned.")
            st.caption(result["note"])
    st.divider()
    st.markdown("**Current injury list for a team**")
    injury_team_query = st.text_input("Team abbreviation or city", placeholder="e.g. BOS", key="injury_context_team")
    if st.button("Check team injury context", key="injury_context_button"):
        try:
            matches = search_teams(injury_team_query.strip())
            if matches:
                st.session_state["injury_context_rows"] = team_injury_context(matches[0]["id"])
                st.session_state["injury_context_name"] = matches[0].get("full_name", matches[0].get("name","Team"))
            else:
                st.session_state["injury_context_rows"] = None
                st.warning("No team matched that search.")
        except Exception as e:
            st.error(f"Injury context unavailable: {e}")
    if st.session_state.get("injury_context_rows") is not None:
        st.write(st.session_state.get("injury_context_name","Team"))
        if st.session_state["injury_context_rows"]:
            st.dataframe(pd.DataFrame(st.session_state["injury_context_rows"]), use_container_width=True, hide_index=True)
        else:
            st.info("No injury records returned for this team.")

with tabs[10]:
    st.subheader("Odds and line-movement monitor")
    st.caption("The provider does not supply a historical props archive here. This tab builds your own local snapshot history from the moments you capture; movement starts after the first capture.")
    if st.button("Capture current slate market snapshot", type="primary", key="capture_odds_snapshot"):
        saved = 0
        try:
            game_markets = game_odds(today)
            for market_row in game_markets:
                gid = market_row.get("game_id")
                if gid is not None:
                    saved += record_snapshot(gid, game_odds=[market_row])
            for game in games:
                try:
                    current_props = player_props(game["id"])
                    saved += record_snapshot(game["id"], props=current_props)
                except Exception:
                    continue
            st.success(f"Captured {saved} market rows. Capture again later to compare movement.")
        except Exception as e:
            st.error(f"Snapshot capture failed: {e}")
    try:
        movement = movement_history()
        if movement:
            frame = pd.DataFrame(movement)
            display_cols = [x for x in ["player","market","vendor","snapshot_type","opening_line","latest_line","line_change","latest_over","latest_under","first_at","latest_at"] if x in frame.columns]
            st.dataframe(frame[display_cols], use_container_width=True, hide_index=True)
            if "line_change" in frame.columns:
                moved = frame[frame["line_change"].fillna(0) != 0]
                st.metric("Markets with a recorded line change", len(moved))
        else:
            st.info("No snapshots yet. Capture the current slate now, then capture again later to see changes.")
    except Exception as e:
        st.error(f"Movement history unavailable: {e}")
    from storage import get_engine
    st.warning(f"This is your own snapshot journal, not a full sportsbook tick history. Storage: {get_engine().dialect.name.upper()}. Configure DATABASE_URL for durable PostgreSQL history on hosted Streamlit.")
