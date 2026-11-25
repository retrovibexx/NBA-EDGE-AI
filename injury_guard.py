"""Shared fail-closed injury availability guard for NBA player projections."""
from bdl import injuries

EXCLUDED_STATUSES = {
    "out", "doubtful", "questionable", "inactive", "injured reserve",
    "injury reserve", "out for season", "suspended",
}

def normalize_status(value):
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())

def injury_status_map():
    """Return player_id -> normalized status. Raise if the feed cannot be verified."""
    try:
        rows = injuries()
    except Exception as exc:
        raise RuntimeError(f"Injury status could not be verified; projections/parlays are paused for safety: {exc}") from exc
    result = {}
    for row in rows or []:
        player = row.get("player") or {}
        player_id = player.get("id")
        status = normalize_status(row.get("status"))
        if player_id is not None and status:
            result[int(player_id)] = status
    return result

def is_unavailable(status):
    status = normalize_status(status)
    return status in EXCLUDED_STATUSES or any(
        phrase in status for phrase in ("injured reserve", "out for", "suspended")
    )

def require_available(player_id, statuses):
    status = statuses.get(int(player_id))
    return (not is_unavailable(status), status)
