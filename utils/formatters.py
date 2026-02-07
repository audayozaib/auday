from datetime import datetime
import re

def format_time_remaining(ends_at: datetime) -> str:
    now = datetime.utcnow()
    delta = ends_at - now

    if delta.total_seconds() <= 0:
        return "Expired"

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0 and not days and not hours:
        parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

    return ", ".join(parts) if parts else "Less than a second"

def format_channel_name(title: str, username: str = None) -> str:
    if username:
        return f"{title} (@{username})"
    return title

def format_winner_list(winners: list, client_app=None) -> str:
    if not winners:
        return "No winners"

    lines = []
    for idx, winner in enumerate(winners, 1):
        user_id = winner.get("user_id")
        lines.append(f"{idx}. User ID: {user_id}")

    return "\n".join(lines)

def detect_prize_type(prize_text: str) -> str:
    """
    Intelligently detect the type of prize based on its content.
    Returns a user-friendly description of the prize type.
    """
    if not prize_text or not prize_text.strip():
        return "Prize"

    prize = prize_text.strip()

    # Check for URLs/Links
    url_pattern = r'https?://[^\s]+'
    if re.search(url_pattern, prize, re.IGNORECASE):
        return "Access Link"

    # Check for email:password format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}:.+$'
    if re.match(email_pattern, prize):
        return "Account Credentials"

    # Check for username:password format (but not email)
    username_pass_pattern = r'^[a-zA-Z0-9_.-]+:[^\s@]+$'
    if re.match(username_pass_pattern, prize) and '@' not in prize.split(':')[0]:
        return "Account Credentials"

    # Check for typical redeem code patterns
    # (alphanumeric with hyphens, underscores, or all caps codes)
    code_pattern = r'^[A-Z0-9]{4,}(-[A-Z0-9]+)*$|^[A-Z0-9_]{8,}$'
    if re.match(code_pattern, prize, re.IGNORECASE):
        return "Redeem Code"

    # If it's a longer text (more than 50 chars or has multiple words), it's likely notes
    if len(prize) > 50 or len(prize.split()) > 5:
        return "Special Instructions"

    # Default to "Prize Details" for anything else
    return "Prize Details"

def format_prize_display(prize_lines: list) -> str:
    """
    Format prize display based on quantity and types detected.
    Returns a user-friendly description of prizes.
    """
    if not prize_lines:
        return "Prize"

    if len(prize_lines) == 1:
        # Single prize - detect its type
        return detect_prize_type(prize_lines[0])
    else:
        # Multiple prizes - check if they're all the same type
        prize_types = [detect_prize_type(p) for p in prize_lines]
        unique_types = set(prize_types)

        if len(unique_types) == 1:
            # All prizes are the same type
            prize_type = prize_types[0]
            return f"{len(prize_lines)} {prize_type}s" if len(prize_lines) > 1 else prize_type
        else:
            # Mixed prize types
            return f"{len(prize_lines)} Different Prizes"

def format_duration_from_hours(hours: int) -> str:
    """
    Convert hours to a human-readable duration format.
    """
    if hours < 1:
        minutes = hours * 60
        return f"{int(minutes)} minute{'s' if minutes != 1 else ''}"
    elif hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = hours // 24
        remaining_hours = hours % 24
        if remaining_hours == 0:
            return f"{days} day{'s' if days != 1 else ''}"
        else:
            return f"{days} day{'s' if days != 1 else ''} {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
