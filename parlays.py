from itertools import combinations, product

def build_candidates(legs,leg_count=3,limit=10):
    valid=[x for x in legs if 0.01<float(x.get("probability",0))<.99 and float(x.get("edge",0))>=0.025 and x.get("game_id") is not None]
    # Limit the search space to the three best distinct-player candidates per game.
    by_game={}
    for leg in sorted(valid,key=lambda x:(float(x.get("edge",0)),float(x.get("probability",0))),reverse=True):
        group=by_game.setdefault(leg["game_id"],[])
        if any(x.get("player_id")==leg.get("player_id") for x in group): continue
        if len(group)<3: group.append(leg)
    game_ids=sorted(by_game,key=lambda gid:max(x["edge"] for x in by_game[gid]),reverse=True)[:10]
    if len(game_ids)<leg_count: return []
    candidates=[]
    for selected_games in combinations(game_ids,leg_count):
        pools=[by_game[gid] for gid in selected_games]
        for combo in product(*pools):
            players=[x.get("player_id") for x in combo if x.get("player_id") is not None]
            if len(players)!=len(set(players)): continue
            mean_edge=sum(float(x.get("edge",0)) for x in combo)/len(combo)
            candidates.append({"legs":list(combo),"independence_product":float(__import__("math").prod(float(x["probability"]) for x in combo)),"mean_edge":mean_edge,"warning":"Different-game legs reduce direct game correlation, but residual correlation may remain."})
    candidates.sort(key=lambda x:x["mean_edge"],reverse=True)
    return candidates[:limit]

def prop_probability(values,line,direction):
    from features import empirical_over_probability
    p=empirical_over_probability(values,line)
    if p is None: return None
    return p if direction=="over" else 1-p
