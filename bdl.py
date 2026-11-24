"""BALLDONTLIE NBA data adapter. Store API keys only in Streamlit secrets or environment variables."""
import os, time
from datetime import date, datetime, timezone
import requests
import streamlit as st
BASE="https://api.balldontlie.io"
def api_key():
    try: return st.secrets.get("BALLDONTLIE_API_KEY","") or os.getenv("BALLDONTLIE_API_KEY","")
    except Exception: return os.getenv("BALLDONTLIE_API_KEY","")
def request(path,params=None,required=True):
    key=api_key()
    if not key:
        if required: raise RuntimeError("Add BALLDONTLIE_API_KEY in Streamlit Secrets to enable premium NBA data.")
        return {}
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
