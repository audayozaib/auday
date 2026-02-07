from datetime import datetime
from database.connection import get_db
from bson import ObjectId

async def save_winners(giveaway_id, winners_list: list):
    db = get_db()

    winner_docs = []
    for rank, user_id in enumerate(winners_list, start=1):
        winner_docs.append({
            "giveaway_id": ObjectId(giveaway_id),
            "user_id": user_id,
            "rank": rank,
            "delivered": False,
            "delivered_at": None
        })

    if winner_docs:
        await db.winners.insert_many(winner_docs)

async def mark_prize_delivered(giveaway_id, user_id: int):
    db = get_db()
    await db.winners.update_one(
        {"giveaway_id": ObjectId(giveaway_id), "user_id": user_id},
        {"$set": {"delivered": True, "delivered_at": datetime.utcnow()}}
    )

async def get_winners(giveaway_id):
    db = get_db()
    return await db.winners.find({"giveaway_id": ObjectId(giveaway_id)}).sort("rank", 1).to_list(length=None)
