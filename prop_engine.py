from bdl import player_game_stats, search_players, current_season_start, player_by_id
from features import player_rows, rolling_projection, empirical_over_probability
STAT_FOR_PROP={"points":"PTS","rebounds":"REB","assists":"AST","steals":"STL","blocks":"BLK","threes":"3PM","points_rebounds":"PTS","points_assists":"PTS","points_rebounds_assists":"PTS","rebounds_assists":"REB"}
def american_prob(odds):
    try:
        o=float(odds)
        return (-o)/((-o)+100) if o<0 else 100/(o+100)
    except Exception: return None
def analyze_props(game,props,max_players=35):
    results=[]; seen=set(); unique_players=set()
    for prop in props:
        pid=prop.get("player_id"); kind=prop.get("prop_type"); line=prop.get("line_value")
        stat=STAT_FOR_PROP.get(kind)
        if not pid or not stat or line is None or pid in seen: continue
        seen.add(pid)
        if len(seen)>max_players: break
        try:
            logs=player_rows(player_game_stats(pid,current_season_start()))
            proj=rolling_projection(logs,stat)
            if not proj: continue
            values=proj["values"]
            over=empirical_over_probability(values,float(line))
            if over is None: continue
            market=prop.get("market") or {}
            op=american_prob(market.get("over_odds")); up=american_prob(market.get("under_odds"))
            if op is not None and up is not None:
                fair_over=op/(op+up); fair_under=up/(op+up)
                over_edge=over-fair_over; under_edge=(1-over)-fair_under
            else:
                fair_over=fair_under=None; over_edge=under_edge=0.0
            direction="over" if over_edge>=under_edge else "under"
            probability=over if direction=="over" else 1-over
            edge=max(over_edge,under_edge)
            player=prop.get("player") or player_by_id(pid)
            results.append({"game_id":game["id"],"player_id":pid,"player":f"{player.get('first_name','Player')} {player.get('last_name','')}","market":kind,"line":float(line),"direction":direction,"probability":float(probability),"projection":float(projection),"edge":float(edge),"vendor":prop.get("vendor",""),"updated_at":prop.get("updated_at"),"sample":proj["n"],"source":"BALLDONTLIE player props + season game logs"})
        except Exception:
            continue
    return sorted(results,key=lambda x:x["edge"],reverse=True)
