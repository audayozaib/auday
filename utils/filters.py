from pyrogram import filters
from database.user_state import get_user_state

def user_state_filter(state_value = None, state_prefix: str = None):
    async def func(flt, _, message):
        if not message.from_user:
            return False

        user_state = await get_user_state(message.from_user.id)
        if not user_state:
            return False

        current_state = user_state.get("state", "")

        if flt.state_value:
            if isinstance(flt.state_value, list):
                return current_state in flt.state_value
            else:
                return current_state == flt.state_value
        elif flt.state_prefix:
            return current_state.startswith(flt.state_prefix)

        return bool(current_state)

    return filters.create(func, state_value=state_value, state_prefix=state_prefix)
