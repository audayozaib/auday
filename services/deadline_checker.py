import asyncio
from pyrogram import Client
from database.giveaways import get_expired_giveaways
from services.winner_selection import end_giveaway_and_select_winners

async def check_and_end_expired_giveaways(client: Client):
    expired = await get_expired_giveaways()

    for giveaway in expired:
        giveaway_id = str(giveaway["_id"])
        print(f"⏰ Ending giveaway: {giveaway['title']} (ID: {giveaway_id})")

        try:
            await end_giveaway_and_select_winners(client, giveaway_id)
            print(f"✅ Giveaway ended successfully: {giveaway_id}")
        except Exception as e:
            print(f"❌ Error ending giveaway {giveaway_id}: {e}")

async def start_deadline_checker(client: Client):
    print("🚀 Started deadline checker task")

    while True:
        try:
            await check_and_end_expired_giveaways(client)
        except Exception as e:
            print(f"❌ Error in deadline checker: {e}")

        await asyncio.sleep(30)
