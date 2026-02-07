from datetime import datetime
from database.connection import get_db

async def save_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    db = get_db()

    existing = await db.users.find_one({"user_id": user_id})
    if existing:
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_interaction": datetime.utcnow()
            }}
        )
        return existing

    user_doc = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "joined_at": datetime.utcnow(),
        "last_interaction": datetime.utcnow()
    }

    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return user_doc

async def get_all_users():
    db = get_db()
    return await db.users.find({}).to_list(length=None)

async def get_total_users_count():
    db = get_db()
    return await db.users.count_documents({})
