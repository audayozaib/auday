from datetime import datetime
from database.connection import get_db
from bson import ObjectId

async def add_participant(giveaway_id, user_id: int):
    db = get_db()

    existing = await db.participants.find_one({
        "giveaway_id": ObjectId(giveaway_id),
        "user_id": user_id
    })

    if existing:
        return False

    participant_doc = {
        "giveaway_id": ObjectId(giveaway_id),
        "user_id": user_id,
        "joined_at": datetime.utcnow()
    }

    await db.participants.insert_one(participant_doc)
    return True

async def is_participant(giveaway_id, user_id: int):
    db = get_db()
    result = await db.participants.find_one({
        "giveaway_id": ObjectId(giveaway_id),
        "user_id": user_id
    })
    return result is not None

async def count_participants(giveaway_id):
    db = get_db()
    return await db.participants.count_documents({"giveaway_id": ObjectId(giveaway_id)})

async def get_all_participants(giveaway_id):
    db = get_db()
    cursor = db.participants.find({"giveaway_id": ObjectId(giveaway_id)}).sort("joined_at", 1)
    return await cursor.to_list(length=None)
