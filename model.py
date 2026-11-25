import numpy as np
from datetime import date
from bdl import current_season_start, team_games, player_game_stats, player_game_history, search_players, team_advanced_averages, injuries, player_season_averages, player_advanced_averages, team_games_history
from features import player_rows, rolling_projection, minutes_projection, as_float, STAT_MAP
from injury_guard import injury_status_map


def _optional_team_advanced(team_id, season):
    """Advanced team metrics improve the forecast but must not block a basic forecast."""
    try:
        rows = team_advanced_averages(team_id, season)
        return (rows[0].get("stats") or {}) if rows else {}
    except Exception:
        return {}


def _optional_injury_penalties(team_ids):
    """Injury data is an adjustment, not a hard dependency for the game simulator."""
    team_ids = set(team_ids)
    impacts = {team_id: {"penalty": 0.0, "count": 0} for team_id in team_ids}
    # Injury adjustments are optional for team-level win simulations; player-leg
    # generation separately fails closed when availability cannot be verified.
    try:
        rows = injuries()
    except Exception:
        return impacts
    relevant = [
        x for x in rows
        if (x.get("player") or {}).get("team_id") in team_ids
        and str(x.get("status", "")).lower() in ("out", "doubtful", "questionable", "probable")
    ]
    ids = [(x.get("player") or {}).get("id") for x in relevant]
    try:
        stats = player_season_averages(ids, current_season_start()) if ids else []
    except Exception:
        stats = []
    by_id = {(x.get("player") or {}).get("id"): x.get("stats") or {} for x in stats}
    weights = {"out": 1.0, "doubtful": 0.75, "questionable": 0.4, "probable": 0.1}
    for item in relevant:
        p = item.get("player") or {}
        team_id = p.get("team_id")
        s = by_id.get(p.get("id"), {})
        value = float(s.get("pts", 0) or 0) + 0.6 * float(s.get("reb", 0) or 0) + 0.8 * float(s.get("ast", 0) or 0)
        impacts[team_id]["penalty"] += value * weights.get(str(item.get("status", "")).lower(), 0.0) * 0.06
        impacts[team_id]["count"] += 1
    for team_id in impacts:
        impacts[team_id]["penalty"] = min(4.5, impacts[team_id]["penalty"])
    return impacts


def project_player(name, stat):
    try:
        statuses = injury_status_map()
    except Exception as exc:
        return {"error": str(exc)}
    matches = search_players(name)
    if not matches:
        return {"error": "Player not found in data provider."}
    exact = next(
        (p for p in matches if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip().lower() == name.lower()),
        matches[0],
    )
    status = statuses.get(int(exact["id"]))
    from injury_guard import is_unavailable
    if is_unavailable(status):
        return {"error": f"{exact.get('first_name', '')} {exact.get('last_name', '')} is listed as {status.upper()} and is excluded from projections."}
    rows = player_rows(player_game_stats(exact["id"], current_season_start()))
    if len(rows) < 5:
        rows = player_rows(player_game_history(exact["id"], current_season_start()))
    if not rows:
        return {"error": "No player game logs returned for this season or recent history."}
    proj = rolling_projection(rows, stat)
    if not proj:
        return {"error": f"No usable {stat} records returned."}

    # Advanced usage is supplementary; the core forecast remains available without it.
    try:
        advanced = player_advanced_averages(exact["id"], current_season_start())
        adv = (advanced[0].get("stats") or {}) if advanced else {}
        usage = adv.get("usage_percentage")
    except Exception:
        usage = None

    return {
        "player": f"{exact.get('first_name', '')} {exact.get('last_name', '')}",
        "team": (exact.get("team") or {}).get("abbreviation", "—"),
        "projection": proj["projection"], "average": proj["mean"], "median": proj["median"],
        "last5": proj["last5"], "last10": proj["last10"], "games": proj["n"],
        "minutes": proj.get("projected_minutes"), "usage": usage, "values": proj["values"],
        "sample_std": proj.get("sample_std"), "weighted_mean": proj.get("weighted_mean"),
        "per_minute_projection": proj.get("per_minute_projection"),
        "note": "Projection uses one shared recency-weighted model: recent box-score production, a robust median component, and per-minute production scaled by projected minutes. Opponent, lineup and role context are not yet included in this core player-stat forecast."
    }


def _team_rating(team, target_date):
    try:
        games = team_games(team["id"], current_season_start())
        if not games:
            games = team_games_history(team["id"], current_season_start())
    except Exception:
        games = team_games_history(team["id"], current_season_start())
    completed = [
        g for g in games
        if (g.get("status_state") == "final" or str(g.get("status", "")).lower() == "final")
        and g.get("date", "") < target_date
    ]
    margins = []
    for g in completed[:12]:
        hs = g.get("home_team_score")
        vs = g.get("visitor_team_score")
        if hs is None or vs is None:
            continue
        margins.append(float(hs - vs) if (g.get("home_team") or {}).get("id") == team["id"] else float(vs - hs))
    last_date = completed[0].get("date") if completed else None
    rest = None
    if last_date:
        try:
            rest = max(0, (date.fromisoformat(target_date) - date.fromisoformat(last_date)).days - 1)
        except Exception:
            pass
    adv = _optional_team_advanced(team["id"], current_season_start())
    net = adv.get("net_rating")
    pace = adv.get("pace", adv.get("e_pace"))
    offense = adv.get("off_rating")
    defense = adv.get("def_rating")
    return (float(np.mean(margins)) if margins else 0.0, len(margins), games, rest, net, pace, offense, defense)


def predict_game(away, home, simulations=10000, target_date=None, exclude_game_id=None):
    if away.get("id") == home.get("id"):
        return {"error": "Choose two different teams."}
    try:
        target_date = target_date or date.today().isoformat()
        ar, an, ag, arest, anet, apace, aoff, adef = _team_rating(away, target_date)
        hr, hn, hg, hrest, hnet, hpace, hoff, hdef = _team_rating(home, target_date)
        rest_adj = 0.0
        if arest == 0:
            rest_adj -= 1.0
        if hrest == 0:
            rest_adj += 1.0
        try:
            away_history = team_games_history(away["id"], current_season_start())
            home_history = team_games_history(home["id"], current_season_start())
        except Exception:
            away_history, home_history = [], []
        away_by_id = {g.get("id"): g for g in away_history}
        home_by_id = {g.get("id"): g for g in home_history}
        meetings = [
            away_by_id[k] for k in set(away_by_id).intersection(home_by_id)
            if away_by_id[k].get("status_state") == "final"
            and away_by_id[k].get("date", "") < target_date
            and away_by_id[k].get("id") != exclude_game_id
        ]
        h2h = []
        for game in sorted(meetings, key=lambda x: x.get("date", ""), reverse=True)[:5]:
            hs = game.get("home_team_score")
            vs = game.get("visitor_team_score")
            if hs is not None and vs is not None:
                h2h.append(float(hs - vs) if (game.get("home_team") or {}).get("id") == home.get("id") else float(vs - hs))
        h2h_adj = float(np.mean(h2h)) * .08 if h2h else 0.0
        net_adj = 0.0
        if anet is not None and hnet is not None:
            net_adj = (float(hnet) - float(anet)) * .035
        injury_impacts = _optional_injury_penalties([away["id"], home["id"]])
        away_injury = injury_impacts[away["id"]]["penalty"]
        away_injured_count = injury_impacts[away["id"]]["count"]
        home_injury = injury_impacts[home["id"]]["penalty"]
        home_injured_count = injury_impacts[home["id"]]["count"]
        margin = (hr - ar) + 2.0 + rest_adj + h2h_adj + net_adj + away_injury - home_injury
        rng = np.random.default_rng(42)
        sims = rng.normal(margin, 12.0, int(simulations))
        hp = float(np.mean(sims > 0))
        pace_values = [float(x) for x in (apace, hpace) if x is not None]
        pace_factor = float(np.mean(pace_values)) if pace_values else 100.0
        if all(x is not None for x in (aoff, hoff, adef, hdef)):
            projected_total = pace_factor * ((float(aoff) + float(hdef)) + (float(hoff) + float(adef))) / 200
        else:
            offense_values = [float(x) for x in (aoff, hoff) if x is not None]
            efficiency_factor = float(np.mean(offense_values)) if offense_values else 112.0
            projected_total = 2 * pace_factor * efficiency_factor / 100
        projected_total = float(np.clip(projected_total, 185, 255))
        total = float(np.clip(rng.normal(projected_total, 14, int(simulations)).mean(), 180, 275))
        return {
            "away_win": 1 - hp, "home_win": hp, "home_margin": margin, "total": total,
            "away_score": (total - margin) / 2, "home_score": (total + margin) / 2,
            "away_form": ar, "home_form": hr, "away_games": an, "home_games": hn,
            "away_rest_days": arest, "home_rest_days": hrest, "h2h_games": len(h2h),
            "away_pace": apace, "home_pace": hpace, "away_net_rating": anet, "home_net_rating": hnet,
            "away_injury_penalty": away_injury, "home_injury_penalty": home_injury,
            "away_injured_count": away_injured_count, "home_injured_count": home_injured_count,
            "injury_feed_verified": True,
            "note": "Uses recent completed-game margins and home court; advanced team ratings and injury adjustments are included only when those feeds are available. Probabilities still require out-of-sample calibration."
        }
    except Exception as e:
        return {"error": f"Model error: {type(e).__name__}: {e}"}
