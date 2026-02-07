from datetime import datetime, timedelta
from database.connection import get_db
from bson import ObjectId

async def create_giveaway(
    owner_id: int,
    channel_id: int,
    title: str,
    description: str,
    prize_lines: list,
    winner_type: str,
    winner_count: int,
    required_channels: list,
    duration_seconds: int,
    image_file_id: str = None
):
    db = get_db()

    starts_at = datetime.utcnow()
    ends_at = starts_at + timedelta(seconds=duration_seconds)

    giveaway_doc = {
        "owner_id": owner_id,
        "channel_id": channel_id,
        "title": title,
        "description": description,
        "prize_lines": prize_lines,
        "winner_type": winner_type,
        "winner_count": winner_count,
        "required_channels": required_channels,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "message_id": None,
        "status": "active",
        "image_file_id": image_file_id
    }

    result = await db.giveaways.insert_one(giveaway_doc)
    giveaway_doc["_id"] = result.inserted_id
    return giveaway_doc

async def update_giveaway_message_id(giveaway_id, message_id: int):
    db = get_db()
    await db.giveaways.update_one(
        {"_id": ObjectId(giveaway_id)},
        {"$set": {"message_id": message_id}}
    )

async def get_giveaway(giveaway_id):
    db = get_db()
    return await db.giveaways.find_one({"_id": ObjectId(giveaway_id)})

async def list_active_giveaways(owner_id: int):
    db = get_db()
    return await db.giveaways.find({
        "owner_id": owner_id,
        "status": "active"
    }).sort("starts_at", -1).to_list(length=None)

async def list_expired_giveaways(owner_id: int):
    db = get_db()
    return await db.giveaways.find({
        "owner_id": owner_id,
        "status": {"$in": ["ended", "completed"]}
    }).sort("ends_at", -1).to_list(length=None)

async def update_giveaway_status(giveaway_id, status: str):
    db = get_db()
    await db.giveaways.update_one(
        {"_id": ObjectId(giveaway_id)},
        {"$set": {"status": status}}
    )

async def get_expired_giveaways():
    db = get_db()
    now = datetime.utcnow()
    return await db.giveaways.find({
        "status": "active",
        "ends_at": {"$lte": now}
    }).to_list(length=None)
