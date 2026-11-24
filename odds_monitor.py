"""Local market snapshot history for line/price movement monitoring."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB=Path("data/nba_edge.db")
def _connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS odds_snapshots(
        id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL,
        game_id INTEGER, player_id INTEGER, player TEXT, market TEXT,
        line REAL, over_odds REAL, under_odds REAL, vendor TEXT, snapshot_type TEXT
    )""")
    return c

def record_snapshot(game_id, props=None, game_odds=None):
    now=datetime.now(timezone.utc).isoformat()
    count=0
    with _connect() as c:
        for item in (game_odds or []):
            c.execute("INSERT INTO odds_snapshots(captured_at,game_id,line,over_odds,under_odds,vendor,snapshot_type) VALUES(?,?,?,?,?,?,?)",
                (now,game_id,item.get("total_value"),None,None,item.get("vendor"),"game"))
            count+=1
        for item in (props or []):
            market=item.get("market") or {}
            player=item.get("player") or {}
            try: line=float(item.get("line_value"))
            except (TypeError,ValueError): continue
            c.execute("INSERT INTO odds_snapshots(captured_at,game_id,player_id,player,market,line,over_odds,under_odds,vendor,snapshot_type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now,game_id,item.get("player_id"),f"{player.get('first_name','')} {player.get('last_name','')}".strip(),item.get("prop_type"),line,market.get("over_odds"),market.get("under_odds"),item.get("vendor"),"player_prop"))
            count+=1
    return count

def movement_history(limit=500):
    with _connect() as c:
        rows=c.execute("""SELECT a.game_id,a.player_id,a.player,a.market,a.vendor,a.snapshot_type,
            a.line AS latest_line,a.over_odds AS latest_over,a.under_odds AS latest_under,a.captured_at AS latest_at,
            (SELECT b.line FROM odds_snapshots b WHERE b.game_id=a.game_id
             AND COALESCE(b.player_id,0)=COALESCE(a.player_id,0)
             AND COALESCE(b.market,'')=COALESCE(a.market,'')
             AND COALESCE(b.vendor,'')=COALESCE(a.vendor,'')
             AND b.snapshot_type=a.snapshot_type ORDER BY b.id ASC LIMIT 1) AS opening_line,
            (SELECT b.captured_at FROM odds_snapshots b WHERE b.game_id=a.game_id
             AND COALESCE(b.player_id,0)=COALESCE(a.player_id,0)
             AND COALESCE(b.market,'')=COALESCE(a.market,'')
             AND COALESCE(b.vendor,'')=COALESCE(a.vendor,'')
             AND b.snapshot_type=a.snapshot_type ORDER BY b.id ASC LIMIT 1) AS first_at
            FROM odds_snapshots a WHERE a.id IN
            (SELECT MAX(id) FROM odds_snapshots GROUP BY game_id,player_id,market,vendor,snapshot_type)
            ORDER BY a.id DESC LIMIT ?""",(int(limit),)).fetchall()
    cols=["game_id","player_id","player","market","vendor","snapshot_type","latest_line","latest_over","latest_under","latest_at","opening_line","first_at"]
    out=[]
    for row in rows:
        item=dict(zip(cols,row))
        if item["latest_line"] is not None and item["opening_line"] is not None:
            item["line_change"]=float(item["latest_line"])-float(item["opening_line"])
        else: item["line_change"]=None
        out.append(item)
    return out
