from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from database.giveaways import list_active_giveaways, list_expired_giveaways
from database.participants import count_participants
from database.winners import get_winners
from menus.keyboards import build_dashboard_menu, build_main_menu
from utils.formatters import format_time_remaining

async def dashboard_menu_handler(client: Client, message: Message):
    await message.reply_text(
        "📊 **Dashboard**\n\n"
        "Choose an option:",
        reply_markup=build_dashboard_menu()
    )

async def active_giveaways_handler(client: Client, message: Message):
    giveaways = await list_active_giveaways(message.from_user.id)

    if not giveaways:
        await message.reply_text(
            "📭 **No Active Giveaways**\n\n"
            "Create one using '🎁 Create Giveaway'.",
            reply_markup=build_dashboard_menu()
        )
        return

    text = "🟢 **Active Giveaways:**\n\n"

    for idx, giveaway in enumerate(giveaways, 1):
        participant_count = await count_participants(str(giveaway["_id"]))
        time_left = format_time_remaining(giveaway["ends_at"])

        text += (
            f"{idx}. **{giveaway['title']}**\n"
            f"   👥 Participants: {participant_count}\n"
            f"   ⏳ Time Left: {time_left}\n"
            f"   🆔 ID: `{str(giveaway['_id'])}`\n\n"
        )

    await message.reply_text(text, reply_markup=build_dashboard_menu())

async def expired_giveaways_handler(client: Client, message: Message):
    giveaways = await list_expired_giveaways(message.from_user.id)

    if not giveaways:
        await message.reply_text(
            "📭 **No Expired Giveaways**",
            reply_markup=build_dashboard_menu()
        )
        return

    text = "⚫️ **Expired Giveaways:**\n\n"

    for idx, giveaway in enumerate(giveaways, 1):
        participant_count = await count_participants(str(giveaway["_id"]))
        winners = await get_winners(str(giveaway["_id"]))

        text += (
            f"{idx}. **{giveaway['title']}**\n"
            f"   👥 Participants: {participant_count}\n"
            f"   🏆 Winners: {len(winners)}\n"
            f"   🆔 ID: `{str(giveaway['_id'])}`\n\n"
        )

    await message.reply_text(text, reply_markup=build_dashboard_menu())

async def analytics_handler(client: Client, message: Message):
    active = await list_active_giveaways(message.from_user.id)
    expired = await list_expired_giveaways(message.from_user.id)

    total_giveaways = len(active) + len(expired)
    total_participants = 0
    total_winners = 0

    for giveaway in active + expired:
        total_participants += await count_participants(str(giveaway["_id"]))
        total_winners += len(await get_winners(str(giveaway["_id"])))

    avg_participants = total_participants / total_giveaways if total_giveaways > 0 else 0

    text = (
        f"📈 **Analytics**\n\n"
        f"📊 **Total Giveaways:** {total_giveaways}\n"
        f"🟢 **Active:** {len(active)}\n"
        f"⚫️ **Ended:** {len(expired)}\n\n"
        f"👥 **Total Participants:** {total_participants}\n"
        f"📊 **Average per Giveaway:** {avg_participants:.1f}\n\n"
        f"🏆 **Total Winners:** {total_winners}\n"
    )

    await message.reply_text(text, reply_markup=build_dashboard_menu())

async def back_to_main_from_dashboard_handler(client: Client, message: Message):
    await message.reply_text(
        "🏠 **Main Menu**",
        reply_markup=build_main_menu()
    )

def register_dashboard_handlers(app: Client):
    app.add_handler(MessageHandler(
        dashboard_menu_handler,
        filters.create(lambda _, __, m: m.text == "📊 Dashboard") & filters.private
    ))
    app.add_handler(MessageHandler(
        active_giveaways_handler,
        filters.create(lambda _, __, m: m.text == "🟢 Active Giveaways") & filters.private
    ))
    app.add_handler(MessageHandler(
        expired_giveaways_handler,
        filters.create(lambda _, __, m: m.text == "⚫️ Expired Giveaways") & filters.private
    ))
    app.add_handler(MessageHandler(
        analytics_handler,
        filters.create(lambda _, __, m: m.text == "📈 Analytics") & filters.private
    ))
