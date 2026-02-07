import time
from typing import Dict, Tuple

# Cache format: {giveaway_id: (last_update_time, participant_count)}
_message_edit_cache: Dict[str, Tuple[float, int]] = {}

# Minimum seconds between message edits for the same giveaway
MIN_EDIT_INTERVAL = 5

def should_update_message(giveaway_id: str, current_participant_count: int) -> bool:
    """
    Check if a message should be updated based on time and participant count.

    Returns:
        True if the message should be updated, False otherwise.
    """
    current_time = time.time()

    if giveaway_id not in _message_edit_cache:
        _message_edit_cache[giveaway_id] = (current_time, current_participant_count)
        return True

    last_update_time, last_count = _message_edit_cache[giveaway_id]
    time_since_last_update = current_time - last_update_time

    # If participant count changed AND enough time has passed
    if current_participant_count != last_count and time_since_last_update >= MIN_EDIT_INTERVAL:
        _message_edit_cache[giveaway_id] = (current_time, current_participant_count)
        return True

    # If 30 seconds have passed, force update regardless
    if time_since_last_update >= 30:
        _message_edit_cache[giveaway_id] = (current_time, current_participant_count)
        return True

    return False

def clear_cache(giveaway_id: str):
    """Clear cache for a specific giveaway (useful when giveaway ends)."""
    if giveaway_id in _message_edit_cache:
        del _message_edit_cache[giveaway_id]

def get_next_update_time(giveaway_id: str) -> int:
    """Get the seconds until next allowed update."""
    if giveaway_id not in _message_edit_cache:
        return 0

    last_update_time, _ = _message_edit_cache[giveaway_id]
    elapsed = time.time() - last_update_time
    remaining = max(0, MIN_EDIT_INTERVAL - elapsed)
    return int(remaining)
