import pandas as pd
from sqlalchemy import text
from storage import get_engine

def init_db():
    engine=get_engine()
    with engine.begin() as c:
        if engine.dialect.name=="postgresql":
            c.execute(text("""CREATE TABLE IF NOT EXISTS predictions(
                id BIGSERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                game_id BIGINT, away TEXT, home TEXT, p_away DOUBLE PRECISION, p_home DOUBLE PRECISION,
                predicted_margin DOUBLE PRECISION, actual_winner TEXT, graded INTEGER DEFAULT 0, source TEXT)"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS prop_predictions(
                id BIGSERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                game_id BIGINT, player_id BIGINT, player TEXT, market TEXT, line DOUBLE PRECISION,
                direction TEXT, probability DOUBLE PRECISION, projection DOUBLE PRECISION,
                actual_value DOUBLE PRECISION, graded INTEGER DEFAULT 0, source TEXT, hit INTEGER)"""))
        else:
            c.execute(text("""CREATE TABLE IF NOT EXISTS predictions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                game_id INTEGER, away TEXT, home TEXT, p_away REAL, p_home REAL,
                predicted_margin REAL, actual_winner TEXT, graded INTEGER DEFAULT 0, source TEXT)"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS prop_predictions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                game_id INTEGER, player_id INTEGER, player TEXT, market TEXT, line REAL,
                direction TEXT, probability REAL, projection REAL, actual_value REAL,
                graded INTEGER DEFAULT 0, source TEXT, hit INTEGER)"""))

def save_game_prediction(game,result):
    init_db()
    with get_engine().begin() as c:
        c.execute(text("""INSERT INTO predictions(game_id,away,home,p_away,p_home,predicted_margin,source)
            VALUES(:game_id,:away,:home,:p_away,:p_home,:margin,:source)"""),{
            "game_id":game["id"],"away":game["visitor_team"]["full_name"],"home":game["home_team"]["full_name"],
            "p_away":result["away_win"],"p_home":result["home_win"],"margin":result["home_margin"],
            "source":"BALLDONTLIE + NBA Edge model"})

def save_prop_prediction(game_id,leg):
    init_db()
    with get_engine().begin() as c:
        c.execute(text("""INSERT INTO prop_predictions(game_id,player_id,player,market,line,direction,probability,projection,source)
            VALUES(:game_id,:player_id,:player,:market,:line,:direction,:probability,:projection,:source)"""),{
            "game_id":game_id,"player_id":leg.get("player_id"),"player":leg.get("player"),"market":leg.get("market"),
            "line":leg.get("line"),"direction":leg.get("direction"),"probability":leg.get("probability"),
            "projection":leg.get("projection"),"source":"BALLDONTLIE + matchup-adjusted rolling model"})

def load_predictions():
    init_db()
    engine=get_engine()
    games=pd.read_sql_query(text("SELECT * FROM predictions ORDER BY id DESC"),engine)
    props=pd.read_sql_query(text("SELECT * FROM prop_predictions ORDER BY id DESC"),engine)
    return games,props

def grade_completed():
    from bdl import game_by_id, game_player_stats
    stat_map={"points":"pts","rebounds":"reb","assists":"ast","steals":"stl","blocks":"blk","threes":"fg3m"}
    graded_games=0; graded_props=0; pending=0
    games,props=load_predictions()
    engine=get_engine()
    for _,row in games[games["graded"]==0].iterrows():
        try:
            g=game_by_id(int(row["game_id"]))
            if g.get("status_state")!="final" and str(g.get("status","")).lower()!="final":
                pending+=1; continue
            hs=g.get("home_team_score"); vs=g.get("visitor_team_score")
            if hs is None or vs is None: continue
            winner=(g.get("home_team") or {}).get("full_name") if hs>vs else (g.get("visitor_team") or {}).get("full_name")
            with engine.begin() as c:
                c.execute(text("UPDATE predictions SET actual_winner=:winner,graded=1 WHERE id=:id"),{"winner":winner,"id":int(row["id"])})
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
            with engine.begin() as c:
                c.execute(text("UPDATE prop_predictions SET actual_value=:actual,graded=1,hit=:hit WHERE id=:id"),
                    {"actual":actual,"hit":1 if won else 0,"id":int(row["id"])})
            graded_props+=1
        except Exception:
            continue
    return {"games_graded":graded_games,"props_graded":graded_props,"still_pending":pending}
