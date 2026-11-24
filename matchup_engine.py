"""Opponent-aware player context and rotation-change signals.

These are transparent, sample-size-shrunk adjustments, not trained causal estimates.
"""
import numpy as np
from bdl import player_game_history, team_advanced_averages, current_season_start, injuries, player_season_averages
from features import player_rows, STAT_MAP, as_float, rolling_projection, minutes_projection

def _stat_key(stat):
    return STAT_MAP.get(stat, str(stat).lower())

def analyze_matchup(player_id, opponent_id, stat="PTS", season=None):
    season = int(season or current_season_start())
    raw = player_game_history(int(player_id), season)
    rows = player_rows(raw)
    if len(rows) < 5:
        return {"error":"Not enough player game logs for matchup analysis."}
    key = _stat_key(stat)
    base = rolling_projection(rows, stat)
    if not base:
        return {"error":f"No usable {stat} history."}
    h2h = []
    for row in rows:
        game = next((x.get("game") or {} for x in raw if (x.get("game") or {}).get("id")==row.get("game_id")), {})
        home_id = (game.get("home_team") or {}).get("id")
        away_id = (game.get("visitor_team") or {}).get("id")
        if int(opponent_id) in (home_id, away_id):
            value = as_float(row.get(key))
            if np.isfinite(value): h2h.append(value)
    h2h = h2h[:8]
    # Opponent team-level defensive efficiency is used as a light contextual signal.
    adv = team_advanced_averages(int(opponent_id), season)
    stats = (adv[0].get("stats") or {}) if adv else {}
    defense = stats.get("def_rating")
    pace = stats.get("pace", stats.get("e_pace"))
    adjustment = 0.0
    defense_factor = None
    if defense is not None:
        try:
            # NBA defensive rating is points allowed per 100 possessions; 112 is a neutral anchor.
            defense_factor = float(np.clip((float(defense)-112.0)*0.0035, -0.06, 0.06))
            adjustment += base["projection"] * defense_factor
        except (TypeError, ValueError):
            defense_factor = None
    h2h_mean = float(np.mean(h2h)) if h2h else None
    h2h_weight = min(0.25, len(h2h)/20.0)
    if h2h_mean is not None:
        adjustment += (h2h_mean-base["projection"])*h2h_weight
    role = detect_role_change(rows)
    role_adjustment = 0.0
    if role["minutes_change"] is not None:
        role_adjustment = float(np.clip(role["minutes_change"]*0.22, -3.0, 3.0))
        if stat != "MIN":
            per_minute = base["projection"]/max(1.0, minutes_projection(rows) or 1.0)
            adjustment += role_adjustment*per_minute
        else:
            adjustment += role_adjustment
    return {
        "base_projection":float(base["projection"]),
        "adjusted_projection":float(max(0,base["projection"]+adjustment)),
        "opponent_def_rating":float(defense) if defense is not None else None,
        "opponent_pace":float(pace) if pace is not None else None,
        "h2h_mean":h2h_mean,"h2h_games":len(h2h),
        "role":role,"role_adjustment":float(role_adjustment),
        "sample":base["n"],
        "note":"Opponent defense is a team-level rating adjustment and H2H is shrunk toward the player's baseline. Small H2H samples are descriptive, not predictive."
    }

def detect_role_change(rows):
    mins=[as_float(r.get("min")) for r in rows]
    mins=[x for x in mins if np.isfinite(x) and x>0]
    if len(mins)<6:
        return {"label":"Insufficient sample","minutes_change":None,"recent_minutes":None,"prior_minutes":None,"usage_change":None}
    recent=mins[:5]; prior=mins[5:15]
    recent_min=float(np.mean(recent)); prior_min=float(np.mean(prior)) if prior else recent_min
    # Approximate usage from box-score opportunity counts; not official usage percentage.
    def usage(row):
        vals=[as_float(row.get(k)) for k in ("fga","fta","tov")]
        if not all(np.isfinite(v) for v in vals): return None
        return vals[0]+0.44*vals[1]+vals[2]
    r_use=[usage(x) for x in rows[:5]]
    p_use=[usage(x) for x in rows[5:15]]
    r_use=[x for x in r_use if x is not None]; p_use=[x for x in p_use if x is not None]
    use_change=(float(np.mean(r_use))-float(np.mean(p_use))) if r_use and p_use else None
    change=recent_min-prior_min
    if change>=3 and (use_change is None or use_change>=0.5): label="Role trending up"
    elif change<=-3: label="Minutes trending down"
    else: label="Stable rotation"
    return {"label":label,"minutes_change":float(change),"recent_minutes":recent_min,"prior_minutes":prior_min,"usage_change":use_change}

def team_injury_context(team_id):
    rows=injuries()
    relevant=[]
    for item in rows:
        p=item.get("player") or {}
        if p.get("team_id")==int(team_id):
            relevant.append({"player":f"{p.get('first_name','')} {p.get('last_name','')}".strip(),"status":item.get("status"),"description":item.get("description"),"return_date":item.get("return_date")})
    return relevant
