"""BALLDONTLIE NBA data adapter. Store API keys only in Streamlit secrets or environment variables."""
import os, time, threading
from datetime import date, datetime, timezone
import requests
import streamlit as st
BASE="https://api.balldontlie.io"
_last_request=0.0
_rate_lock=threading.Lock()
def api_key():
    try: return st.secrets.get("BALLDONTLIE_API_KEY","") or os.getenv("BALLDONTLIE_API_KEY","")
    except Exception: return os.getenv("BALLDONTLIE_API_KEY","")
def request(path,params=None,required=True):
    global _last_request
    key=api_key()
    if not key:
        if required: raise RuntimeError("Add BALLDONTLIE_API_KEY in Streamlit Secrets to enable premium NBA data.")
        return {}
    try: rpm=int(st.secrets.get("BALLDONTLIE_RPM",os.getenv("BALLDONTLIE_RPM","30")))
    except Exception: rpm=int(os.getenv("BALLDONTLIE_RPM","5"))
    rpm=max(1,min(rpm,600))
    with _rate_lock:
        wait=max(0.0,(60.0/rpm)-(time.monotonic()-_last_request))
        if wait: time.sleep(wait)
        _last_request=time.monotonic()
    r=requests.get(BASE+path,headers={"Authorization":key},params=params or {},timeout=25)
    if r.status_code==401: raise RuntimeError("API key rejected or endpoint not in plan. Confirm NBA GOAT access.")
    if r.status_code==429: raise RuntimeError("Rate limit reached. Wait briefly and retry.")
    r.raise_for_status(); return r.json()
def pages(path,params=None,max_pages=8):
    params=dict(params or {}); params.setdefault("per_page",100); out=[]
    for _ in range(max_pages):
        payload=request(path,params); out.extend(payload.get("data",[]))
        cursor=payload.get("meta",{}).get("next_cursor")
        if cursor is None: break
        params["cursor"]=cursor; time.sleep(.12)
    return out
@st.cache_data(ttl=180,show_spinner=False)
def games_for_date(day): return pages("/v1/games",{"dates[]":day,"per_page":100})
@st.cache_data(ttl=900,show_spinner=False)
def injuries(): return pages("/v1/player_injuries",{"per_page":100},5)
@st.cache_data(ttl=300,show_spinner=False)
def projected_lineups(game_id): return pages("/nba/v1/projected_lineups",{"game_ids[]":game_id,"per_page":100},2)
@st.cache_data(ttl=90,show_spinner=False)
def player_props(game_id): return request("/v2/odds/player_props",{"game_id":game_id}).get("data",[])
@st.cache_data(ttl=90,show_spinner=False)
def game_odds(day): return pages("/v2/odds",{"dates[]":day,"per_page":100},3)
@st.cache_data(ttl=21600,show_spinner=False)
def search_players(name): return pages("/v1/players",{"search":name,"per_page":100},2)
@st.cache_data(ttl=21600,show_spinner=False)
def search_teams(query):
    """Search the small NBA team directory locally; no separate search endpoint required."""
    all_teams=pages("/v1/teams",{"per_page":100},1)
    q=str(query or "").strip().casefold()
    if not q: return all_teams
    return [team for team in all_teams if q in " ".join(str(team.get(k,"")) for k in ("full_name","name","abbreviation","city","conference","division")).casefold()]
@st.cache_data(ttl=1800,show_spinner=False)
def player_game_stats(player_id,season):
    rows=pages("/v1/stats",{"player_ids[]":player_id,"seasons[]":season,"per_page":100},12)
    rows.sort(key=lambda x:(x.get("game") or {}).get("date",""),reverse=True); return rows
@st.cache_data(ttl=1800,show_spinner=False)
def team_games(team_id,season):
    rows=pages("/v1/games",{"team_ids[]":team_id,"seasons[]":season,"per_page":100},5)
    rows.sort(key=lambda x:x.get("date",""),reverse=True); return rows
def current_season_start(today=None):
    today=today or date.today(); return today.year if today.month>=10 else today.year-1

@st.cache_data(ttl=300,show_spinner=False)
def game_by_id(game_id):
    return request(f"/v1/games/{int(game_id)}").get("data",{})
@st.cache_data(ttl=21600,show_spinner=False)
def player_by_id(player_id):
    return request(f"/v1/players/{int(player_id)}").get("data",{})
@st.cache_data(ttl=900,show_spinner=False)
def game_player_stats(game_id,player_id):
    return pages("/v1/stats",{"game_ids[]":int(game_id),"player_ids[]":int(player_id),"per_page":100},2)

def freshness_label(iso):
    if not iso: return "Timestamp unavailable"
    try:
        dt=datetime.fromisoformat(str(iso).replace("Z","+00:00"))
        mins=(datetime.now(timezone.utc)-dt).total_seconds()/60
        return f"Updated {int(max(0,mins))} min ago"
    except Exception: return str(iso)

@st.cache_data(ttl=21600,show_spinner=False)
def team_advanced_averages(team_id,season):
    return pages("/nba/v1/team_season_averages/general",{"season":season,"season_type":"regular","type":"advanced","team_ids[]":int(team_id),"per_page":100},2)
@st.cache_data(ttl=21600,show_spinner=False)
def team_base_averages(team_id,season):
    return pages("/nba/v1/team_season_averages/general",{"season":season,"season_type":"regular","type":"base","team_ids[]":int(team_id),"per_page":100},2)
@st.cache_data(ttl=300,show_spinner=False)
def game_lineups(game_id):
    return pages("/nba/v1/lineups",{"game_ids[]":int(game_id),"per_page":100},2)

@st.cache_data(ttl=900,show_spinner=False)
def player_season_averages(player_ids,season):
    ids=[int(x) for x in player_ids if x is not None]
    if not ids: return []
    return pages("/nba/v1/season_averages/general",{"season":season,"season_type":"regular","type":"base","player_ids[]":ids,"per_page":100},3)

@st.cache_data(ttl=21600,show_spinner=False)
def player_advanced_averages(player_id,season):
    return pages("/nba/v1/season_averages/general",{"season":season,"season_type":"regular","type":"advanced","player_ids[]":int(player_id),"per_page":100},2)

@st.cache_data(ttl=21600,show_spinner=False)
def team_games_history(team_id,season_start):
    seasons=[int(season_start)-2,int(season_start)-1,int(season_start)]
    rows=pages("/v1/games",{"team_ids[]":int(team_id),"seasons[]":seasons,"per_page":100},12)
    rows.sort(key=lambda x:x.get("date",""),reverse=True)
    return rows

@st.cache_data(ttl=21600,show_spinner=False)
def player_game_history(player_id,season_start):
    seasons=[int(season_start)-2,int(season_start)-1,int(season_start)]
    rows=pages("/v1/stats",{"player_ids[]":int(player_id),"seasons[]":seasons,"per_page":100},36)
    rows.sort(key=lambda x:(x.get("game") or {}).get("date",""),reverse=True)
    return rows

@st.cache_data(ttl=21600,show_spinner=False)
def team_lineup_stats(team_id,game_ids):
    ids=[int(x) for x in game_ids if x is not None]
    if not ids: return []
    return pages("/nba/v1/lineup_stats",{"team_ids[]":int(team_id),"game_ids[]":ids,"per_page":100},8)

@st.cache_data(ttl=21600,show_spinner=False)
def team_box_scores(game_ids):
    ids=[int(x) for x in game_ids if x is not None]
    if not ids: return []
    return pages("/v1/stats",{"game_ids[]":ids,"per_page":100},12)

@st.cache_data(ttl=21600,show_spinner=False)
def player_matchup_defense(player_id,game_ids):
    ids=[int(x) for x in game_ids if x is not None]
    if not ids: return []
    return pages("/nba/v1/matchups",{"player_ids[]":int(player_id),"game_ids[]":ids,"per_page":100},8)

@st.cache_data(ttl=21600,show_spinner=False)
def player_advanced_game_stats(player_id,season):
    return pages("/nba/v2/stats/advanced",{"player_ids[]":int(player_id),"seasons[]":int(season),"period":0,"per_page":100},12)

@st.cache_data(ttl=21600,show_spinner=False)
def all_player_season_averages(season):
    return pages("/nba/v1/season_averages/general",{"season":int(season),"season_type":"regular","type":"base","per_page":100},20)

@st.cache_data(ttl=300,show_spinner=False)
def player_game_lineup_status(game_id,player_id):
    actual=game_lineups(int(game_id))
    for row in actual:
        if int((row.get("player") or {}).get("id",-1))==int(player_id):
            return {"status":"Confirmed starter" if row.get("starter") else "Confirmed bench","source":"actual lineup","position":row.get("position")}
    projected=projected_lineups(int(game_id))
    for team_row in projected:
        for item in team_row.get("lineup") or []:
            if int((item.get("player") or {}).get("id",-1))==int(player_id):
                return {"status":"Listed in projected lineup","source":str(team_row.get("status","projected")),"position":item.get("position")}
    return {"status":"Not listed / unavailable feed","source":"No lineup match; this does not mean inactive","position":None}


@st.cache_data(ttl=21600,show_spinner=False)
def players_for_team(team_id):
    return pages('/v1/players', {'team_ids[]': int(team_id), 'per_page': 100}, 3)


@st.cache_data(ttl=1800,show_spinner=False)
def player_game_stats_many(player_ids, season):
    """Fetch player logs in small URL-safe batches to avoid HTTP 431 header/request-line errors."""
    ids = sorted({int(x) for x in player_ids if x is not None})
    if not ids:
        return []
    rows = []
    # The BDL API encodes each player_ids[] item into the URL. Keep batches small
    # because a full NBA slate roster can exceed proxy request-line limits.
    batch_size = 12
    for offset in range(0, len(ids), batch_size):
        batch = ids[offset:offset + batch_size]
        rows.extend(pages("/v1/stats", {"player_ids[]": batch, "seasons[]": int(season), "per_page": 100}, 30))
    rows.sort(key=lambda x: (x.get("game") or {}).get("date", ""), reverse=True)
    return rows

@st.cache_data(ttl=21600,show_spinner=False)
def players_for_teams(team_ids):
    ids = sorted({int(x) for x in team_ids if x is not None})
    if not ids:
        return []
    return pages("/v1/players", {"team_ids[]": ids, "per_page": 100}, 8)
