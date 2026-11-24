import sqlite3
from pathlib import Path
import pandas as pd
DB=Path("data/nba_edge.db")
DB.parent.mkdir(parents=True,exist_ok=True)

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,game_id INTEGER,away TEXT,home TEXT,p_away REAL,p_home REAL,predicted_margin REAL,actual_winner TEXT,graded INTEGER DEFAULT 0,source TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prop_predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,game_id INTEGER,player_id INTEGER,player TEXT,market TEXT,line REAL,direction TEXT,probability REAL,projection REAL,actual_value REAL,graded INTEGER DEFAULT 0,source TEXT,hit INTEGER)""")
        try:
            c.execute("ALTER TABLE prop_predictions ADD COLUMN hit INTEGER")
        except sqlite3.OperationalError:
            pass

def save_game_prediction(game,result):
    init_db()
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO predictions(game_id,away,home,p_away,p_home,predicted_margin,source) VALUES(?,?,?,?,?,?,?)",(game["id"],game["visitor_team"]["full_name"],game["home_team"]["full_name"],result["away_win"],result["home_win"],result["home_margin"],"BALLDONTLIE + NBA Edge model"))

def save_prop_prediction(game_id,leg):
    init_db()
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO prop_predictions(game_id,player_id,player,market,line,direction,probability,projection,source) VALUES(?,?,?,?,?,?,?,?,?)",(game_id,leg.get("player_id"),leg.get("player"),leg.get("market"),leg.get("line"),leg.get("direction"),leg.get("probability"),leg.get("projection"),"BALLDONTLIE + rolling empirical model"))

def load_predictions():
    init_db()
    with sqlite3.connect(DB) as c:
        games=pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC",c)
        props=pd.read_sql_query("SELECT * FROM prop_predictions ORDER BY id DESC",c)
    return games,props

def grade_completed():
    from bdl import game_by_id, game_player_stats
    stat_map={"points":"pts","rebounds":"reb","assists":"ast","steals":"stl","blocks":"blk","threes":"fg3m"}
    graded_games=0; graded_props=0; pending=0
    games,props=load_predictions()
    with sqlite3.connect(DB) as c:
        for _,row in games[games["graded"]==0].iterrows():
            try:
                g=game_by_id(int(row["game_id"]))
                if g.get("status_state")!="final" and str(g.get("status","")).lower()!="final":
                    pending+=1; continue
                hs=g.get("home_team_score"); vs=g.get("visitor_team_score")
                if hs is None or vs is None: continue
                winner=(g.get("home_team") or {}).get("full_name") if hs>vs else (g.get("visitor_team") or {}).get("full_name")
                c.execute("UPDATE predictions SET actual_winner=?,graded=1 WHERE id=?",(winner,int(row["id"])))
                graded_games+=1
            except Exception:
                continue
        for _,row in props[props["graded"]==0].iterrows():
            try:
                rows=game_player_stats(int(row["game_id"]),int(row["player_id"]))
                if not rows: continue
                stats=rows[0].get("stats") or {}
                market=str(row["market"])
                if market in ("points_rebounds","points_assists","points_rebounds_assists","rebounds_assists"):
                    keys={"points_rebounds":["pts","reb"],"points_assists":["pts","ast"],"points_rebounds_assists":["pts","reb","ast"],"rebounds_assists":["reb","ast"]}[market]
                    actual=sum(float(stats.get(k,0) or 0) for k in keys)
                else:
                    key=stat_map.get(market)
                    if not key: continue
                    actual=float(stats.get(key,0) or 0)
                won=(actual>float(row["line"])) if row["direction"]=="over" else (actual<float(row["line"]))
                c.execute("UPDATE prop_predictions SET actual_value=?,graded=1,hit=? WHERE id=?",(actual,1 if won else 0,int(row["id"])))
                graded_props+=1
            except Exception:
                continue
    return {"games_graded":graded_games,"props_graded":graded_props,"still_pending":pending}
