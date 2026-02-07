import re
from pyrogram.enums import ChatType

def ensure_chat_type_channel(chat):
    if chat.type != ChatType.CHANNEL:
        raise ValueError("This operation requires a Telegram Channel, not a group or supergroup.")

def validate_positive_int(text: str) -> int:
    try:
        num = int(text.strip())
        if num <= 0:
            raise ValueError("Number must be positive")
        return num
    except ValueError:
        raise ValueError("Invalid number format")

def validate_winner_type(text: str) -> str:
    text = text.strip().lower()
    if text in ["random", "r", "1"]:
        return "random"
    elif text in ["first", "first_x", "f", "2", "first x participants"]:
        return "first_x"
    else:
        raise ValueError("Invalid winner type. Choose 'random' or 'first_x'")

def parse_duration_to_seconds(text: str) -> int:
    text = text.strip().lower()
    match = re.match(r'^(\d+)([smhd])$', text)

    if not match:
        raise ValueError("Invalid duration format. Use: 5m, 1h, 2d, etc.")

    value = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400
    }

    return value * multipliers[unit]

def parse_prize_block(text: str) -> list:
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if not lines:
        raise ValueError("Prize cannot be empty")

    valid_prizes = []
    for line in lines:
        cleaned_line = line.strip()

        if ':' in cleaned_line:
            valid_prizes.append(cleaned_line)
        elif len(cleaned_line) >= 3:
            valid_prizes.append(cleaned_line)

    if not valid_prizes:
        raise ValueError("No valid prize format detected")

    return valid_prizes
