import numpy as np
from data import get_team_form, get_player_logs

def _team_strength(abbr):
    df=get_team_form(abbr)
    if df.empty or "WL" not in df: return 0.0, "No recent team logs available; neutral baseline used."
    wins=(df["WL"]=="W").sum()
    losses=(df["WL"]=="L").sum()
    margin=(df["PLUS_MINUS"].astype(float).mean() if "PLUS_MINUS" in df else 0.0)
    # Shrink small samples toward neutral to reduce overconfidence.
    score=(wins-losses)*0.45 + float(margin)*0.055
    return float(np.clip(score,-2.5,2.5)), f"Recent form: {wins}–{losses} across {len(df)} games; strength estimate shrunk toward league average."

def predict_game(away,home,n=8000):
    if away==home: return {"error":"Choose two different teams."}
    try:
        sa,na=_team_strength(away); sh,nh=_team_strength(home)
        # Home-court prior is deliberately modest; score variance is broad.
        diff=(sh-sa)+1.6
        rng=np.random.default_rng()
        margin=rng.normal(diff,12.2,n)
        away_win=float(np.mean(margin<0))
        home_win=1-away_win
        total=float(np.clip(rng.normal(226,15,n).mean(),175,275))
        away_score=(total-diff)/2
        home_score=(total+diff)/2
        return {"away_win":away_win,"home_win":home_win,"total":total,"away_score":float(away_score),"home_score":float(home_score),"explanation":na+" "+nh+" Estimates are baseline simulations, not calibrated betting probabilities; injury, lineup and pace inputs are not yet complete."}
    except Exception as e: return {"error":f"Could not simulate: {type(e).__name__}."}

def project_player(name,stat):
    df,note=get_player_logs(name)
    if df.empty: return {"error":note}
    col={"PTS":"PTS","REB":"REB","AST":"AST","STL":"STL","BLK":"BLK","MIN":"MIN"}.get(stat)
    if col not in df: return {"error":f"{stat} is not present in the returned game logs."}
    vals=df[col].astype(str).str.replace(":","",regex=False)
    if stat=="MIN":
        # NBA minute strings may be MM:SS.
        def minutes(v):
            try:
                if ":" in str(v):
                    a,b=str(v).split(":"); return float(a)+float(b)/60
                return float(v)
            except: return np.nan
        series=df[col].apply(minutes).dropna()
    else: series=pd.to_numeric(df[col],errors="coerce").dropna()
    if series.empty: return {"error":"No usable stat values returned."}
    recent=series.head(10)
    avg=float(recent.mean()); median=float(recent.median())
    # Recency-weighted mean with modest shrinkage to recent median.
    weights=np.linspace(1.4,0.8,len(recent))
    projection=float(np.average(recent.to_numpy(),weights=weights)*0.65+median*0.35)
    return {"projection":projection,"average":avg,"median":median,"games":len(recent),"note":note+" Projection uses recent box-score production only; it does not yet adjust for confirmed opponent matchup, injury status, or starting role.","minutes_reliable":stat=="MIN"}
