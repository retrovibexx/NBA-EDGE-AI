import math
import numpy as np

STAT_MAP={"PTS":"pts","REB":"reb","AST":"ast","STL":"stl","BLK":"blk","MIN":"min","3PM":"fg3m"}

def as_float(v):
    try:
        if isinstance(v,str) and ":" in v:
            m,s=v.split(":",1)
            return float(m)+float(s)/60
        return float(v)
    except Exception:
        return float("nan")

def player_rows(rows):
    """Normalize flat BALLDONTLIE /v1/stats rows and nested stats payloads."""
    out=[]
    metadata={"id","game","player","team","stats","season","postseason"}
    for row in rows:
        game=row.get("game") or {}
        nested=row.get("stats")
        merged=dict(nested) if isinstance(nested,dict) else {}
        for key,value in row.items():
            if key not in metadata and key not in merged:
                merged[key]=value
        merged["date"]=game.get("date",row.get("date",""))
        merged["game_id"]=game.get("id",row.get("game_id"))
        merged["team"]=row.get("team") or {}
        out.append(merged)
    return sorted(out,key=lambda x:x.get("date",""),reverse=True)

def _weighted_average(values, decay=0.92):
    arr=np.asarray(values,dtype=float)
    arr=arr[np.isfinite(arr)]
    if not len(arr):
        return None
    weights=np.power(float(decay),np.arange(len(arr),dtype=float))
    return float(np.average(arr,weights=weights))

def minutes_projection(rows):
    mins=[as_float(r.get("min")) for r in rows]
    mins=[x for x in mins if math.isfinite(x) and x>0]
    if not mins:
        return None
    # Recent minutes are more informative for the player's current role.
    recent=mins[:15]
    return _weighted_average(recent,decay=0.90)

def rolling_projection(rows,stat):
    """Unified player-stat forecast used by the live projection board and backtest.

    Uses recency-weighted box-score production, a robust median component,
    per-minute production scaled by projected minutes, and a small season-level
    shrinkage term. All inputs must be games completed before the forecast date.
    """
    key=STAT_MAP.get(stat,stat.lower())
    values=[as_float(r.get(key)) for r in rows]
    values=[v for v in values if math.isfinite(v)]
    if not values:
        return None

    recent=values[:20]
    weighted=_weighted_average(recent,decay=0.92)
    median=float(np.median(recent))
    direct=0.75*weighted+0.25*median

    minutes=minutes_projection(rows)
    per_minute=[]
    for row in rows[:20]:
        value=as_float(row.get(key))
        played=as_float(row.get("min"))
        if math.isfinite(value) and math.isfinite(played) and played>0:
            per_minute.append((value/played,played))
    rate_estimate=None
    if stat!="MIN" and per_minute and minutes is not None:
        rates=[x[0] for x in per_minute]
        rate=_weighted_average(rates,decay=0.92)
        rate_estimate=rate*minutes

    if stat=="MIN" or rate_estimate is None:
        estimate=direct
    else:
        estimate=0.55*direct+0.45*rate_estimate

    # Stabilize small recent samples against a broader, still historical baseline.
    season_values=values[:40]
    if len(season_values)>=10:
        season_mean=float(np.mean(season_values))
        shrink=min(0.20, max(0.0,(10-len(recent))*0.02))
        estimate=(1-shrink)*estimate+shrink*season_mean

    return {
        "projection":float(max(0.0,estimate)),
        "mean":float(np.mean(recent)),
        "median":median,
        "last5":float(np.mean(recent[:5])),
        "last10":float(np.mean(recent[:10])),
        "n":len(recent),
        "values":recent,
        "weighted_mean":float(weighted),
        "per_minute_projection":float(rate_estimate) if rate_estimate is not None else None,
        "projected_minutes":float(minutes) if minutes is not None else None,
        "sample_std":float(np.std(recent,ddof=1)) if len(recent)>1 else 0.0,
    }

def empirical_over_probability(values,line):
    arr=np.asarray(values,dtype=float)
    arr=arr[np.isfinite(arr)]
    if len(arr)<3:
        return None
    return (int(np.sum(arr>line))+1)/(len(arr)+2)
