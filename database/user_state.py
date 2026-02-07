from database.connection import get_db

async def set_user_state(user_id: int, state: str, data: dict = None):
    db = get_db()
    await db.user_states.update_one(
        {"user_id": user_id},
        {"$set": {"state": state, "data": data or {}}},
        upsert=True
    )

async def get_user_state(user_id: int):
    db = get_db()
    return await db.user_states.find_one({"user_id": user_id})

async def clear_user_state(user_id: int):
    db = get_db()
    await db.user_states.delete_one({"user_id": user_id})

async def update_user_state_data(user_id: int, data: dict):
    db = get_db()
    current = await get_user_state(user_id)
    if current:
        merged_data = {**current.get("data", {}), **data}
        await db.user_states.update_one(
            {"user_id": user_id},
            {"$set": {"data": merged_data}}
        )
