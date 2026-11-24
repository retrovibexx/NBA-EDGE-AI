import numpy as np
import pandas as pd
from bdl import search_players, player_game_history, current_season_start
from features import player_rows, rolling_projection, STAT_MAP, as_float

def player_walk_forward(name,stat,max_games=60,history=10):
    matches=search_players(name)
    if not matches: return None,"Player not found."
    exact=next((p for p in matches if f"{p.get('first_name','')} {p.get('last_name','')}".strip().lower()==name.lower()),matches[0])
    rows=player_rows(player_game_history(exact["id"],current_season_start()))
    key=STAT_MAP.get(stat,stat.lower())
    chronological=list(reversed(rows))
    observations=[]
    for i in range(history,len(chronological)):
        past=list(reversed(chronological[max(0,i-history):i]))
        actual=as_float(chronological[i].get(key))
        if not np.isfinite(actual): continue
        projection=rolling_projection(past,stat)
        if not projection: continue
        observations.append({"date":chronological[i].get("date"),"predicted":projection["projection"],"actual":actual,"error":actual-projection["projection"]})
    frame=pd.DataFrame(observations[-max_games:])
    if frame.empty: return None,"Not enough historical games for walk-forward evaluation."
    return {"player":f"{exact.get('first_name','')} {exact.get('last_name','')}","stat":stat,"games":len(frame),"mae":float(np.mean(np.abs(frame["error"]))),"rmse":float(np.sqrt(np.mean(np.square(frame["error"])))),"bias":float(np.mean(frame["error"])),"rows":frame},"Walk-forward test uses only games played before each target game. It is historical evidence, not a guarantee of future performance."
