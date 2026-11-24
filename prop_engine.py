import numpy as np
from bdl import player_game_stats, current_season_start, player_by_id
from features import player_rows, rolling_projection, empirical_over_probability, as_float
from matchup_engine import analyze_matchup

STAT_FOR_PROP={"points":"PTS","rebounds":"REB","assists":"AST","steals":"STL","blocks":"BLK","threes":"3PM","points_rebounds":"PTS","points_assists":"PTS","points_rebounds_assists":"PTS","rebounds_assists":"REB"}
COMBO_KEYS={"points_rebounds":["pts","reb"],"points_assists":["pts","ast"],"points_rebounds_assists":["pts","reb","ast"],"rebounds_assists":["reb","ast"]}

def american_prob(odds):
    try:
        o=float(odds)
        return (-o)/((-o)+100) if o<0 else 100/(o+100)
    except Exception:
        return None

def analyze_props(game,props,max_players=35):
    results=[]; seen=set(); unique_players=set()
    for prop in props:
        pid=prop.get("player_id"); kind=prop.get("prop_type"); line=prop.get("line_value")
        stat=STAT_FOR_PROP.get(kind)
        if not pid or not stat or line is None: continue
        marker=(pid,kind,str(line),prop.get("vendor"))
        if marker in seen: continue
        seen.add(marker); unique_players.add(pid)
        if len(unique_players)>max_players: break
        try:
            logs=player_rows(player_game_stats(pid,current_season_start()))
            if not logs: continue
            if kind in COMBO_KEYS:
                values=[]
                for row in logs:
                    vals=[as_float(row.get(k)) for k in COMBO_KEYS[kind]]
                    if all(np.isfinite(v) for v in vals): values.append(sum(vals))
                values=values[:15]
                if len(values)<3: continue
                projection=float(np.average(values,weights=np.linspace(1.7,.75,len(values))))
            else:
                proj=rolling_projection(logs,stat)
                if not proj: continue
                values=proj["values"]; projection=float(proj["projection"])
            player=prop.get("player") or player_by_id(pid)
            team_id=(player.get("team") or {}).get("id")
            home_id=(game.get("home_team") or {}).get("id")
            away_id=(game.get("visitor_team") or {}).get("id")
            opponent_id=away_id if team_id==home_id else home_id if team_id==away_id else None
            matchup=None
            if opponent_id is not None and kind not in COMBO_KEYS:
                try:
                    matchup=analyze_matchup(pid,opponent_id,stat,current_season_start(),include_full=False)
                    if matchup and not matchup.get("error"):
                        delta=float(matchup["adjusted_projection"])-float(matchup["base_projection"])
                        projection=max(0.0,projection+delta)
                        values=[float(v)+delta for v in values]
                except Exception:
                    matchup=None
            over=empirical_over_probability(values,float(line))
            if over is None: continue
            market=prop.get("market") or {}
            op=american_prob(market.get("over_odds")); up=american_prob(market.get("under_odds"))
            if op is not None and up is not None and (op+up)>0:
                fair_over=op/(op+up); fair_under=up/(op+up)
                # Shrink small-sample hit rates toward the no-vig market baseline.
                n=len(values); weight=n/(n+10.0)
                over_est=weight*over+(1-weight)*fair_over
                under_est=1-over_est
                over_edge=over_est-fair_over; under_edge=under_est-fair_under
            else:
                over_est=over
                over_edge=under_edge=0.0
            direction="over" if over_edge>=under_edge else "under"
            probability=over_est if direction=="over" else 1-over_est
            edge=max(over_edge,under_edge)
            role_label=(matchup or {}).get("role",{}).get("label","Unavailable")
            results.append({"game_id":game["id"],"player_id":pid,"player":f"{player.get('first_name','Player')} {player.get('last_name','')}","market":kind,"line":float(line),"direction":direction,"probability":float(probability),"projection":projection,"edge":float(edge),"vendor":prop.get("vendor",""),"updated_at":prop.get("updated_at"),"sample":len(values),"role_signal":role_label,"matchup_adjustment":round(float(matchup["adjusted_projection"])-float(matchup["base_projection"]),2) if matchup and not matchup.get("error") else None,"h2h_games":(matchup or {}).get("h2h_games",0),"position":(matchup or {}).get("position"),"positional_adjustment":(matchup or {}).get("positional_adjustment"),"source":"BALLDONTLIE player props + matchup-adjusted recent game logs"})
        except Exception:
            continue
    return sorted(results,key=lambda x:x["edge"],reverse=True)
