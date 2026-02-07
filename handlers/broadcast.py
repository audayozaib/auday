from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from config import BOT_OWNER_ID
from database.users import get_all_users, get_total_users_count
import asyncio

async def broadcast_handler(client: Client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return

    if not message.reply_to_message:
        total = await get_total_users_count()
        await message.reply_text(
            "❌ **How to Broadcast:**\n\n"
            "Reply to any message with `/broadcast` to send it to all bot users.\n\n"
            f"📊 **Total Users:** {total}"
        )
        return

    users = await get_all_users()
    total = len(users)

    if total == 0:
        await message.reply_text("❌ No users to broadcast to.")
        return

    status_msg = await message.reply_text(
        f"📡 **Broadcasting...**\n\n"
        f"Total Users: {total}\n"
        f"Sent: 0\n"
        f"Failed: 0"
    )

    sent = 0
    failed = 0
    blocked = 0

    for idx, user in enumerate(users, 1):
        try:
            await message.reply_to_message.copy(user["user_id"])
            sent += 1
        except Exception as e:
            failed += 1
            if "blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                blocked += 1

        if idx % 10 == 0 or idx == total:
            try:
                await status_msg.edit_text(
                    f"📡 **Broadcasting...**\n\n"
                    f"Total Users: {total}\n"
                    f"✅ Sent: {sent}\n"
                    f"❌ Failed: {failed}\n"
                    f"🚫 Blocked: {blocked}\n\n"
                    f"Progress: {idx}/{total} ({int(idx/total*100)}%)"
                )
            except:
                pass

        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"Total Users: {total}\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"🚫 Blocked: {blocked}"
    )

async def stats_handler(client: Client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return

    from database.giveaways import get_db

    db = get_db()
    total_users = await get_total_users_count()
    total_giveaways = db.giveaways.count_documents({})
    active_giveaways = db.giveaways.count_documents({"status": "active"})
    total_participants = db.participants.count_documents({})

    await message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"👥 **Total Users:** {total_users}\n"
        f"🎁 **Total Giveaways:** {total_giveaways}\n"
        f"🟢 **Active Giveaways:** {active_giveaways}\n"
        f"🎯 **Total Participants:** {total_participants}"
    )

def register_broadcast_handlers(app: Client):
    app.add_handler(MessageHandler(
        broadcast_handler,
        filters.command("broadcast") & filters.private & filters.user(BOT_OWNER_ID)
    ))
    app.add_handler(MessageHandler(
        stats_handler,
        filters.command("stats") & filters.private & filters.user(BOT_OWNER_ID)
    ))
