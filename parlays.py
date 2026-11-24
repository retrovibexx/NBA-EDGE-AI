def build_parlay(legs,count):
    valid=[x for x in legs if 0<float(x.get("p",0))<1]
    valid=sorted(valid,key=lambda x:x["p"],reverse=True)[:count]
    warnings=[]
    groups=[x.get("group","") for x in valid if x.get("group")]
    if len(groups)!=len(set(groups)):
        warnings.append("Potential correlation detected: multiple legs share a game/team group. Do not multiply probabilities as if independent.")
    if len(valid)<3: warnings.append("At least three valid legs are required.")
    return valid,warnings
