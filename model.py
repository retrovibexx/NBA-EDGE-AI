import numpy as np
from datetime import date
from bdl import current_season_start, team_games, player_game_stats, search_players
from features import player_rows, rolling_projection, minutes_projection

def project_player(name,stat):
    matches=search_players(name)
    if not matches: return {"error":"Player not found in data provider."}
    exact=next((p for p in matches if f"{p.get('first_name','')} {p.get('last_name','')}".strip().lower()==name.lower()),matches[0])
    rows=player_rows(player_game_stats(exact["id"],current_season_start()))
    if not rows: return {"error":"No player game logs returned for this season."}
    proj=rolling_projection(rows,stat)
    if not proj: return {"error":f"No usable {stat} records returned."}
    return {"player":f"{exact.get('first_name','')} {exact.get('last_name','')}","team":(exact.get("team") or {}).get("abbreviation","—"),"projection":proj["projection"],"average":proj["mean"],"median":proj["median"],"last5":proj["last5"],"last10":proj["last10"],"games":proj["n"],"minutes":minutes_projection(rows),"values":proj["values"],"note":"Recency-weighted box-score projection; confirm current minutes, injuries, role and matchup before relying on it."}

def _team_rating(team):
    games=team_games(team["id"],current_season_start())
    completed=[g for g in games if g.get("status_state")=="final" or str(g.get("status","")).lower()=="final"]
    margins=[]
    for g in completed[:12]:
        hs=g.get("home_team_score"); vs=g.get("visitor_team_score")
        if hs is None or vs is None: continue
        margins.append(float(hs-vs) if (g.get("home_team") or {}).get("id")==team["id"] else float(vs-hs))
    last_date=completed[0].get("date") if completed else None
    rest=None
    if last_date:
        try: rest=max(0,(date.today()-date.fromisoformat(last_date)).days-1)
        except Exception: pass
    return (float(np.mean(margins)) if margins else 0.0),len(margins),games,rest

def predict_game(away,home,simulations=10000):
    if away.get("id")==home.get("id"): return {"error":"Choose two different teams."}
    try:
        ar,an,ag,arest=_team_rating(away)
        hr,hn,hg,hrest=_team_rating(home)
        rest_adj=0.0
        if arest==0: rest_adj-=1.0
        if hrest==0: rest_adj+=1.0
        away_by_id={g.get("id"):g for g in ag}
        home_by_id={g.get("id"):g for g in hg}
        meetings=[away_by_id[k] for k in set(away_by_id).intersection(home_by_id) if away_by_id[k].get("status_state")=="final"]
        h2h=[]
        for game in sorted(meetings,key=lambda x:x.get("date",""),reverse=True)[:5]:
            hs=game.get("home_team_score"); vs=game.get("visitor_team_score")
            if hs is not None and vs is not None:
                h2h.append(float(hs-vs) if (game.get("home_team") or {}).get("id")==home.get("id") else float(vs-hs))
        h2h_adj=float(np.mean(h2h))*.08 if h2h else 0.0
        margin=(hr-ar)+2.0+rest_adj+h2h_adj
        rng=np.random.default_rng(42)
        sims=rng.normal(margin,12.0,int(simulations))
        hp=float(np.mean(sims>0))
        total=float(np.clip(rng.normal(226,14,int(simulations)).mean(),180,275))
        return {"away_win":1-hp,"home_win":hp,"home_margin":margin,"total":total,"away_score":(total-margin)/2,"home_score":(total+margin)/2,"away_form":ar,"home_form":hr,"away_games":an,"home_games":hn,"away_rest_days":arest,"home_rest_days":hrest,"h2h_games":len(h2h),"note":"Team recent scoring margin + home-court prior + modest rest and head-to-head adjustments. Pace/efficiency and player-level availability still need calibration and historical testing."}
    except Exception as e:
        return {"error":f"Model error: {type(e).__name__}: {e}"}
