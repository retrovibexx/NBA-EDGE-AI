from itertools import combinations, product
from math import prod

def build_candidates(legs,leg_count=3,limit=10):
    """Build diversified candidates; never treat multiplied leg probabilities as calibrated parlay odds."""
    valid=[]
    for leg in legs:
        try:
            probability=float(leg.get("probability",0)); edge=float(leg.get("edge",0))
        except (TypeError,ValueError):
            continue
        if 0.01<probability<0.99 and edge>=0.025 and leg.get("game_id") is not None:
            valid.append(leg)
    by_game={}
    for leg in sorted(valid,key=lambda x:(float(x.get("edge",0)),float(x.get("probability",0))),reverse=True):
        group=by_game.setdefault(leg["game_id"],[])
        if any(x.get("player_id")==leg.get("player_id") for x in group): continue
        if len(group)<3: group.append(leg)
    game_ids=sorted(by_game,key=lambda gid:max(float(x["edge"]) for x in by_game[gid]),reverse=True)[:12]
    if len(game_ids)<leg_count: return []
    candidates=[]
    for selected_games in combinations(game_ids,leg_count):
        pools=[by_game[gid] for gid in selected_games]
        for combo in product(*pools):
            players=[x.get("player_id") for x in combo if x.get("player_id") is not None]
            if len(players)!=len(set(players)): continue
            probabilities=[float(x["probability"]) for x in combo]
            mean_edge=sum(float(x["edge"]) for x in combo)/len(combo)
            joint_product=prod(probabilities)
            markets={x.get("market") for x in combo}
            directions={x.get("direction") for x in combo}
            # This is a diversity descriptor, not a statistical correlation estimate.
            diversity=len(markets)/max(1,len(combo))
            candidates.append({
                "legs":list(combo),"independence_product":joint_product,
                "mean_edge":mean_edge,"market_diversity":diversity,
                "ranking_score":mean_edge+0.01*diversity,
                "warning":"Different-game legs avoid direct same-game dependence, but multiplied probabilities assume independence and are not calibrated parlay odds. Same-market player outcomes can still share league-wide factors."
            })
    candidates.sort(key=lambda x:(x["ranking_score"],x["independence_product"]),reverse=True)
    return candidates[:limit]

def prop_probability(values,line,direction):
    from features import empirical_over_probability
    p=empirical_over_probability(values,line)
    if p is None: return None
    return p if direction=="over" else 1-p
