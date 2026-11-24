"""Player matchup model using NBA player logs, lineup performance and position-specific opponent box scores.

All context adjustments are bounded and sample-size shrunk. On/off ratings are descriptive team-lineup
splits, not causal player value; position splits are recent opponent production allowed per 36.
"""
import numpy as np
import streamlit as st
from bdl import (
    player_game_history, team_advanced_averages, current_season_start, injuries,
    team_games_history, team_lineup_stats, team_box_scores, player_advanced_game_stats, all_player_season_averages,
)
from features import player_rows, STAT_MAP, as_float, rolling_projection, minutes_projection

COMBO_STATS = {
    "PTS":"pts","REB":"reb","AST":"ast","STL":"stl","BLK":"blk","MIN":"min","3PM":"fg3m"
}

def _stats(row):
    return row.get("stats") if isinstance(row.get("stats"),dict) else row

def _finite(v):
    x=as_float(v)
    return float(x) if np.isfinite(x) else None

def _position(value):
    p=str(value or "").upper()
    if "G" in p and "F" in p: return "G-F"
    if "F" in p and "C" in p: return "F-C"
    if p.startswith("G"): return "G"
    if p.startswith("F"): return "F"
    if p.startswith("C"): return "C"
    return None

def detect_role_change(rows):
    usable=[r for r in rows if (_finite(r.get("min")) or 0)>0]
    if len(usable)<6:
        return {"label":"Insufficient sample","minutes_change":None,"recent_minutes":None,"prior_minutes":None,"usage_change":None}
    recent=usable[:5]; prior=usable[5:15]
    recent_min=float(np.mean([_finite(x.get("min")) for x in recent]))
    prior_min=float(np.mean([_finite(x.get("min")) for x in prior])) if prior else recent_min
    def opportunity(row):
        fga=_finite(row.get("fga")); fta=_finite(row.get("fta"))
        tov=_finite(row.get("turnover",row.get("tov")))
        if fga is None or fta is None or tov is None: return None
        return fga+0.44*fta+tov
    ru=[opportunity(x) for x in recent]; pu=[opportunity(x) for x in prior]
    ru=[x for x in ru if x is not None]; pu=[x for x in pu if x is not None]
    use_change=float(np.mean(ru)-np.mean(pu)) if ru and pu else None
    change=recent_min-prior_min
    if change>=3 and (use_change is None or use_change>=0.5): label="Role trending up"
    elif change<=-3: label="Minutes trending down"
    elif use_change is not None and use_change>=2: label="Usage trending up"
    elif use_change is not None and use_change<=-2: label="Usage trending down"
    else: label="Stable rotation"
    return {"label":label,"minutes_change":change,"recent_minutes":recent_min,"prior_minutes":prior_min,"usage_change":use_change}

@st.cache_data(ttl=1800,show_spinner=False)
def _lineup_impact(team_id,player_id,season):
    games=team_games_history(int(team_id),int(season))
    finals=[g for g in games if g.get("status_state")=="final" or str(g.get("status","")).lower()=="final"]
    game_ids=[g["id"] for g in finals[:12] if g.get("id") is not None]
    if not game_ids: return {"on_net":None,"off_net":None,"net_diff":None,"on_minutes":0,"off_minutes":0,"on_lineups":0,"off_lineups":0}
    rows=team_lineup_stats(int(team_id),game_ids)
    on=[]; off=[]
    for row in rows:
        ids=row.get("player_ids") or []
        stats=_stats(row)
        mins=_finite(stats.get("min")); net=_finite(stats.get("net_rating"))
        if mins is None or net is None or mins<=0: continue
        (on if int(player_id) in [int(x) for x in ids] else off).append((mins,net))
    on_minutes=sum(x[0] for x in on); off_minutes=sum(x[0] for x in off)
    on_net=float(np.average([x[1] for x in on],weights=[x[0] for x in on])) if on else None
    off_net=float(np.average([x[1] for x in off],weights=[x[0] for x in off])) if off else None
    adequate=on_minutes>=60 and off_minutes>=60 and len(on)>=3 and len(off)>=3
    return {"on_net":on_net,"off_net":off_net,"net_diff":(on_net-off_net) if adequate else None,
            "on_minutes":on_minutes,"off_minutes":off_minutes,"on_lineups":len(on),"off_lineups":len(off),
            "sample_adequate":adequate,"games":len(game_ids)}

@st.cache_data(ttl=1800,show_spinner=False)
def _positional_defense(team_id,position,season):
    games=team_games_history(int(team_id),int(season))
    finals=[g for g in games if g.get("status_state")=="final" or str(g.get("status","")).lower()=="final"]
    game_ids=[g["id"] for g in finals[:12] if g.get("id") is not None]
    rows=team_box_scores(game_ids)
    allowed={k:0.0 for k in ("pts","reb","ast","stl","blk","fg3m","min")}
    count=0
    for row in rows:
        team_id_row=row.get("team_id") or (row.get("team") or {}).get("id")
        if team_id_row is None or int(team_id_row)==int(team_id): continue
        player=row.get("player") or {}
        pos=_position(player.get("position"))
        if pos is None or pos!=position: continue
        stats=_stats(row); minutes=_finite(stats.get("min"))
        if minutes is None or minutes<=0: continue
        for key in allowed:
            value=_finite(stats.get(key))
            if value is not None: allowed[key]+=value
        count+=1
    minutes=allowed["min"]
    per36={k:(v/minutes*36 if minutes>0 else None) for k,v in allowed.items() if k!="min"}
    return {"position":position,"opponent_games":len(game_ids),"player_game_rows":count,
            "minutes":minutes,"allowed_per36":per36,
            "note":"Recent box-score production allowed to opposing players listed at this position; descriptive only, not a league-relative defensive rank."}

@st.cache_data(ttl=21600,show_spinner=False)
def _league_position_baseline(season):
    rows=all_player_season_averages(int(season))
    totals={}
    for row in rows:
        player=row.get("player") or {}
        pos=_position(player.get("position"))
        stats=_stats(row)
        if not pos: continue
        bucket=totals.setdefault(pos,{k:0.0 for k in ("pts","reb","ast","stl","blk","fg3m","min")})
        for key in bucket:
            value=_finite(stats.get(key))
            if value is not None: bucket[key]+=value
    out={}
    for pos,bucket in totals.items():
        mins=bucket["min"]
        out[pos]={k:(v/mins*36 if mins>0 else None) for k,v in bucket.items() if k!="min"}
    return out

@st.cache_data(ttl=1800,show_spinner=False)
def _player_advanced_context(player_id,season):
    rows=player_advanced_game_stats(int(player_id),int(season))
    if not rows: return {}
    fields=("usage_percentage","true_shooting_percentage","offensive_rating","defensive_rating","net_rating","pace","assist_percentage","rebound_percentage","matchup_fg_pct","matchup_fga","matchup_minutes")
    out={}
    for field in fields:
        values=[_finite(_stats(r).get(field)) for r in rows]
        values=[x for x in values if x is not None]
        if values: out[field]=float(np.mean(values))
    out["games"]=len(rows)
    return out

@st.cache_data(ttl=1800,show_spinner=False)
def analyze_matchup(player_id,opponent_id,stat="PTS",season=None):
    season=int(season or current_season_start())
    raw=player_game_history(int(player_id),season)
    rows=player_rows(raw)
    if len(rows)<5: return {"error":"Not enough player game logs for matchup analysis."}
    base=rolling_projection(rows,stat)
    if not base: return {"error":f"No usable {stat} history."}
    player=next((r.get("player") or {} for r in raw if r.get("player")), {})
    team=next((r.get("team") or {} for r in raw if r.get("team")), {})
    team_id=team.get("id") or player.get("team_id")
    position=_position(player.get("position"))
    key=STAT_MAP.get(stat,stat.lower())
    h2h=[]
    game_by_id={ (x.get("game") or {}).get("id"):x.get("game") or {} for x in raw}
    for row in rows:
        game=game_by_id.get(row.get("game_id"),{})
        home_id=(game.get("home_team") or {}).get("id"); away_id=(game.get("visitor_team") or {}).get("id")
        if int(opponent_id) in (home_id,away_id):
            value=_finite(row.get(key))
            if value is not None: h2h.append(value)
    h2h=h2h[:8]
    adv=team_advanced_averages(int(opponent_id),season)
    team_stats=_stats(adv[0]) if adv else {}
    defense=_finite(team_stats.get("def_rating",team_stats.get("defensive_rating")))
    pace=_finite(team_stats.get("pace",team_stats.get("e_pace")))
    role=detect_role_change(rows)
    minutes=minutes_projection(rows)
    adjustment=0.0
    # Team defensive efficiency: capped to avoid a small rating gap dominating the player's history.
    if defense is not None:
        adjustment+=base["projection"]*float(np.clip((defense-112.0)*0.0025,-0.045,0.045))
    h2h_mean=float(np.mean(h2h)) if h2h else None
    if h2h_mean is not None:
        adjustment+=(h2h_mean-base["projection"])*min(0.20,len(h2h)/25.0)
    if role["minutes_change"] is not None:
        delta_min=float(np.clip(role["minutes_change"]*0.20,-2.5,2.5))
        adjustment+=delta_min if stat=="MIN" else delta_min*(base["projection"]/max(1.0,minutes or 1.0))
    pos_context=_positional_defense(int(opponent_id),position,season) if position else None
    pos_adjustment=0.0
    pos_baseline=None
    if pos_context and stat!="MIN":
        try:
            pos_baseline=_league_position_baseline(season).get(position,{}).get(key)
            allowed=pos_context["allowed_per36"].get(key)
            if allowed is not None and pos_baseline is not None and pos_baseline>0:
                relative=(allowed/pos_baseline)-1.0
                reliability=min(1.0,pos_context["player_game_rows"]/35.0)
                pos_adjustment=base["projection"]*float(np.clip(relative*0.12*reliability,-0.035,0.035))
                adjustment+=pos_adjustment
        except Exception:
            pos_baseline=None
    lineup=_lineup_impact(int(team_id),int(player_id),season) if team_id else {}
    advanced=_player_advanced_context(int(player_id),season)
    return {
        "base_projection":float(base["projection"]),"adjusted_projection":float(max(0,base["projection"]+adjustment)),
        "opponent_def_rating":defense,"opponent_pace":pace,"h2h_mean":h2h_mean,"h2h_games":len(h2h),
        "role":role,"role_adjustment":float(adjustment),"sample":base["n"],"position":position,
        "positional_defense":pos_context,"positional_baseline_per36":pos_baseline,"positional_adjustment":float(pos_adjustment),"lineup_impact":lineup,"advanced":advanced,
        "note":"Projection combines opponent team rating, recent position-specific box-score allowance relative to league positional production, H2H and role trends. Lineup on/off and advanced player rates are also shown. Position splits and on/off are sample-dependent descriptive signals, not causal guarantees."
    }

def team_injury_context(team_id):
    rows=injuries(); relevant=[]
    for item in rows:
        p=item.get("player") or {}
        if p.get("team_id")==int(team_id):
            relevant.append({"player":f"{p.get('first_name','')} {p.get('last_name','')}".strip(),"status":item.get("status"),"description":item.get("description"),"return_date":item.get("return_date")})
    return relevant
