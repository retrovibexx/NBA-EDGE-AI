from itertools import combinations
def build_candidates(legs,leg_count=3,limit=10):
    valid=[x for x in legs if 0.01<float(x.get("probability",0))<.99 and abs(float(x.get("edge",0)))>0]
    valid=sorted(valid,key=lambda x:(x.get("edge",0),x.get("probability",0)),reverse=True)
    candidates=[]
    for combo in combinations(valid,leg_count):
        players=[x.get("player_id") for x in combo if x.get("player_id") is not None]
        games=[x.get("game_id") for x in combo]
        if len(players)!=len(set(players)) or len(games)!=len(set(games)): continue
        product=1.0
        for x in combo: product*=float(x["probability"])
        candidates.append({"legs":list(combo),"independence_product":product,"mean_edge":sum(float(x.get("edge",0)) for x in combo)/len(combo),"warning":"Different-game legs reduce direct game correlation, but residual correlation may remain."})
    candidates.sort(key=lambda x:x["mean_edge"],reverse=True); return candidates[:limit]
def prop_probability(values,line,direction):
    from features import empirical_over_probability
    p=empirical_over_probability(values,line)
    if p is None: return None
    return p if direction=="over" else 1-p
