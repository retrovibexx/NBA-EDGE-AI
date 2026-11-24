import math
import numpy as np
STAT_MAP={"PTS":"pts","REB":"reb","AST":"ast","STL":"stl","BLK":"blk","MIN":"min","3PM":"fg3m"}
def as_float(v):
    try:
        if isinstance(v,str) and ":" in v:
            m,s=v.split(":",1); return float(m)+float(s)/60
        return float(v)
    except Exception: return float("nan")
def player_rows(rows):
    out=[]
    for row in rows:
        game=row.get("game") or {}; stats=row.get("stats") or {}
        merged=dict(stats); merged["date"]=game.get("date",""); merged["game_id"]=game.get("id")
        merged["team"]=row.get("team") or {}; out.append(merged)
    return sorted(out,key=lambda x:x.get("date",""),reverse=True)
def rolling_projection(rows,stat):
    key=STAT_MAP.get(stat,stat.lower()); values=[as_float(r.get(key)) for r in rows]
    values=[v for v in values if math.isfinite(v)]
    if not values: return None
    sample=values[:15]; weights=np.linspace(1.7,.75,len(sample)); mean=float(np.average(sample,weights=weights)); med=float(np.median(sample))
    return {"projection":.7*mean+.3*med,"mean":float(np.mean(sample)),"median":med,"last5":float(np.mean(sample[:5])),"last10":float(np.mean(sample[:10])),"n":len(sample),"values":sample}
def minutes_projection(rows):
    mins=[as_float(r.get("min")) for r in rows]; mins=[x for x in mins if math.isfinite(x) and x>0]
    if not mins: return None
    recent=mins[:10]; return float(np.average(recent,weights=np.linspace(1.8,.8,len(recent))))
def empirical_over_probability(values,line):
    arr=np.asarray(values,dtype=float); arr=arr[np.isfinite(arr)]
    if len(arr)<3: return None
    return (int(np.sum(arr>line))+1)/(len(arr)+2)
