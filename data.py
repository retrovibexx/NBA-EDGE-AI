import json, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import leaguegamelog, playergamelog
from nba_api.stats.static import players, teams

DB=Path("data/nba_edge.db")
DB.parent.mkdir(parents=True,exist_ok=True)

def _conn():
    return sqlite3.connect(DB)

@st.cache_data(ttl=900, show_spinner=False)
def get_scoreboard():
    try:
        payload=scoreboard.ScoreBoard(timeout=20).get_dict()
        games=payload.get("scoreboard",{}).get("games",[])
        return pd.DataFrame(games), f"NBA live scoreboard fetched {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
    except Exception as e:
        return pd.DataFrame(), f"Scoreboard unavailable: {type(e).__name__}. Data feed may be throttled or temporarily down."

@st.cache_data(ttl=21600, show_spinner=False)
def get_team_form(abbr):
    try:
        team=teams.find_team_by_abbreviation(abbr)
        if not team: return pd.DataFrame()
        df=leaguegamelog.LeagueGameLog(player_or_team_abbreviation="T",season="2026-27",season_type_all_star="Regular Season",timeout=25).get_data_frames()[0]
        df=df[df["TEAM_ID"]==team["id"]].sort_values("GAME_DATE",ascending=False)
        return df.head(12)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=21600, show_spinner=False)
def get_player_logs(name):
    try:
        matches=players.find_players_by_full_name(name)
        if not matches:
            matches=[p for p in players.get_players() if name.lower() in p["full_name"].lower() and p.get("is_active")]
        if not matches: return pd.DataFrame(), "No matching player found."
        exact=next((p for p in matches if p["full_name"].lower()==name.lower()),matches[0])
        df=playergamelog.PlayerGameLog(player_id=exact["id"],season="2026-27",season_type_all_star="Regular Season",timeout=25).get_data_frames()[0]
        if df.empty: return df, f"No 2026-27 game logs returned for {exact['full_name']}."
        return df.sort_values("GAME_DATE",ascending=False), f"Recent logs for {exact['full_name']}."
    except Exception as e:
        return pd.DataFrame(), f"Player stats unavailable: {type(e).__name__}."

def refresh_cache():
    try:
        df,_=get_scoreboard()
        return f"Scoreboard refresh completed ({len(df)} games returned). Team/player logs load on demand."
    except Exception as e: return f"Refresh failed: {type(e).__name__}."

def data_health():
    return [
        "NBA live scoreboard: on-demand, 15-minute cache.",
        "Team and player logs: on-demand, 6-hour cache.",
        "Injury/confirmed lineup feed: not yet integrated; availability is unknown unless independently verified.",
        "Source access: nba_api uses NBA.com endpoints; cloud-hosted requests can be throttled or blocked.",
        f"Local database: {'present' if DB.exists() else 'will be created when predictions are saved'}.",
        "Last health check: "+datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ]
