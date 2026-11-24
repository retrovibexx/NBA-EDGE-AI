import sqlite3
from pathlib import Path
import pandas as pd
DB=Path("data/nba_edge.db"); DB.parent.mkdir(parents=True,exist_ok=True)
def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,game_id INTEGER,away TEXT,home TEXT,p_away REAL,p_home REAL,predicted_margin REAL,actual_winner TEXT,graded INTEGER DEFAULT 0,source TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prop_predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,game_id INTEGER,player_id INTEGER,player TEXT,market TEXT,line REAL,direction TEXT,probability REAL,projection REAL,actual_value REAL,graded INTEGER DEFAULT 0,source TEXT)""")
def save_game_prediction(game,result):
    init_db()
    with sqlite3.connect(DB) as c: c.execute("INSERT INTO predictions(game_id,away,home,p_away,p_home,predicted_margin,source) VALUES(?,?,?,?,?,?,?)",(game["id"],game["visitor_team"]["full_name"],game["home_team"]["full_name"],result["away_win"],result["home_win"],result["home_margin"],"BALLDONTLIE + NBA Edge model"))
def save_prop_prediction(game_id,leg):
    init_db()
    with sqlite3.connect(DB) as c: c.execute("INSERT INTO prop_predictions(game_id,player_id,player,market,line,direction,probability,projection,source) VALUES(?,?,?,?,?,?,?,?,?)",(game_id,leg.get("player_id"),leg.get("player"),leg.get("market"),leg.get("line"),leg.get("direction"),leg.get("probability"),leg.get("projection"),"BALLDONTLIE + rolling empirical model"))
def load_predictions():
    init_db()
    with sqlite3.connect(DB) as c: return pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC",c),pd.read_sql_query("SELECT * FROM prop_predictions ORDER BY id DESC",c)
