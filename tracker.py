import sqlite3
from pathlib import Path
import pandas as pd
DB=Path("data/nba_edge.db")
DB.parent.mkdir(parents=True,exist_ok=True)

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        away TEXT, home TEXT, away_win REAL, home_win REAL, total REAL,
        actual_winner TEXT, graded INTEGER DEFAULT 0)""")

def save_prediction(away,home,result):
    init_db()
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO predictions(away,home,away_win,home_win,total) VALUES(?,?,?,?,?)",
        (away,home,result["away_win"],result["home_win"],result["total"]))

def load_predictions():
    init_db()
    with sqlite3.connect(DB) as c: return pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC",c)

def grade_predictions():
    return "Automatic grading is staged for the next iteration; no result has been guessed. Use the history table to review saved forecasts."
