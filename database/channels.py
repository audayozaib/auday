from datetime import datetime
from database.connection import get_db

async def save_channel(owner_id: int, channel_id: int, title: str, username: str = None):
    db = get_db()

    existing = await db.channels.find_one({"owner_id": owner_id, "channel_id": channel_id})
    if existing:
        return existing

    has_default = await db.channels.find_one({"owner_id": owner_id, "default": True})

    channel_doc = {
        "owner_id": owner_id,
        "channel_id": channel_id,
        "title": title,
        "username": username,
        "status": "active",
        "default": False if has_default else True,
        "added_at": datetime.utcnow()
    }

    try:
        result = await db.channels.insert_one(channel_doc)
        channel_doc["_id"] = result.inserted_id
        return channel_doc
    except Exception as e:
        if "E11000" in str(e) and "duplicate key" in str(e):
            raise ValueError("You have already added this channel.")
        raise

async def list_channels(owner_id: int):
    db = get_db()
    return await db.channels.find({"owner_id": owner_id}).sort("added_at", -1).to_list(length=None)

async def get_default_channel(owner_id: int):
    db = get_db()
    return await db.channels.find_one({"owner_id": owner_id, "default": True})

async def set_default_channel(owner_id: int, channel_id: int):
    db = get_db()
    await db.channels.update_many(
        {"owner_id": owner_id},
        {"$set": {"default": False}}
    )
    await db.channels.update_one(
        {"owner_id": owner_id, "channel_id": channel_id},
        {"$set": {"default": True}}
    )

async def update_channel_status(owner_id: int, channel_id: int, status: str):
    db = get_db()
    await db.channels.update_one(
        {"owner_id": owner_id, "channel_id": channel_id},
        {"$set": {"status": status}}
    )

async def remove_channel(owner_id: int, channel_id: int):
    db = get_db()
    await db.channels.delete_one({"owner_id": owner_id, "channel_id": channel_id})

async def get_channel(owner_id: int, channel_id: int):
    db = get_db()
    return await db.channels.find_one({"owner_id": owner_id, "channel_id": channel_id})
