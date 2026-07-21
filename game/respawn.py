PLAYER_RESPAWN_DELAY_MS = 20_000


def should_auto_respawn(dead_since_ms, now_ms, has_living_teammate, respawn_delay_ms=PLAYER_RESPAWN_DELAY_MS):
    """Return True when a dead player should be revived after the delay."""
    if dead_since_ms is None:
        return False
    if not has_living_teammate:
        return False
    return (now_ms - dead_since_ms) >= respawn_delay_ms
