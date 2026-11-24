"""Market snapshot journal; uses the same durable database as prediction tracking."""
from datetime import datetime, timezone
from sqlalchemy import text
from storage import get_engine

def _number(value):
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None

def init_odds_db():
    engine=get_engine()
    with engine.begin() as c:
        if engine.dialect.name=="postgresql":
            c.execute(text("""CREATE TABLE IF NOT EXISTS odds_snapshots(
                id BIGSERIAL PRIMARY KEY, captured_at TIMESTAMP NOT NULL,
                game_id BIGINT, player_id BIGINT, player TEXT, market TEXT,
                line DOUBLE PRECISION, over_odds DOUBLE PRECISION, under_odds DOUBLE PRECISION,
                vendor TEXT, snapshot_type TEXT)"""))
        else:
            c.execute(text("""CREATE TABLE IF NOT EXISTS odds_snapshots(
                id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL,
                game_id INTEGER, player_id INTEGER, player TEXT, market TEXT,
                line REAL, over_odds REAL, under_odds REAL, vendor TEXT, snapshot_type TEXT)"""))

def record_snapshot(game_id, props=None, game_odds=None):
    init_odds_db()
    now=datetime.now(timezone.utc)
    engine=get_engine()
    captured=now if engine.dialect.name=="postgresql" else now.isoformat()
    count=0
    with engine.begin() as c:
        for item in (game_odds or []):
            c.execute(text("""INSERT INTO odds_snapshots(captured_at,game_id,line,over_odds,under_odds,vendor,snapshot_type)
                VALUES(:captured_at,:game_id,:line,:over,:under,:vendor,'game')"""),{
                "captured_at":captured,"game_id":game_id,"line":_number(item.get("total_value")),
                "over":None,"under":None,"vendor":item.get("vendor")})
            count+=1
        for item in (props or []):
            market=item.get("market") or {}; player=item.get("player") or {}
            try: line=float(item.get("line_value"))
            except (TypeError,ValueError): continue
            c.execute(text("""INSERT INTO odds_snapshots(captured_at,game_id,player_id,player,market,line,over_odds,under_odds,vendor,snapshot_type)
                VALUES(:captured_at,:game_id,:player_id,:player,:market,:line,:over,:under,:vendor,'player_prop')"""),{
                "captured_at":captured,"game_id":game_id,"player_id":item.get("player_id"),
                "player":f"{player.get('first_name','')} {player.get('last_name','')}".strip(),
                "market":item.get("prop_type"),"line":line,"over":_number(market.get("over_odds")),
                "under":_number(market.get("under_odds")),"vendor":item.get("vendor")})
            count+=1
    return count

def movement_history(limit=500):
    init_odds_db()
    sql="""SELECT a.game_id,a.player_id,a.player,a.market,a.vendor,a.snapshot_type,
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
        ORDER BY a.id DESC LIMIT :limit"""
    with get_engine().connect() as c:
        rows=c.execute(text(sql),{"limit":int(limit)}).mappings().all()
    out=[]
    for source in rows:
        item=dict(source)
        item["line_change"]=(float(item["latest_line"])-float(item["opening_line"])) if item["latest_line"] is not None and item["opening_line"] is not None else None
        out.append(item)
    return out
