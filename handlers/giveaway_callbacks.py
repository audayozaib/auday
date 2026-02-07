from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.handlers import CallbackQueryHandler
from database.giveaways import get_giveaway
from database.participants import count_participants
from services.giveaway_post import update_giveaway_post
from utils.flood_control import should_update_message, get_next_update_time

async def reload_status_callback(client: Client, callback_query: CallbackQuery):
    try:
        giveaway_id = callback_query.data.split("_")[1]

        giveaway = await get_giveaway(giveaway_id)

        if not giveaway:
            try:
                await callback_query.answer("❌ Giveaway not found.", show_alert=True)
            except:
                pass
            return

        participant_count = await count_participants(giveaway_id)

        if giveaway["status"] == "active":
            # Check if we should update the message (flood control)
            if should_update_message(giveaway_id, participant_count):
                await update_giveaway_post(client, giveaway, participant_count)
                try:
                    await callback_query.answer(f"🔄 Updated! Participants: {participant_count}", show_alert=False)
                except:
                    pass
            else:
                # Too soon to update, show cooldown message
                next_update = get_next_update_time(giveaway_id)
                try:
                    await callback_query.answer(
                        f"⏱️ Please wait {next_update}s before refreshing again.\nCurrent participants: {participant_count}",
                        show_alert=False
                    )
                except:
                    pass
        else:
            from database.winners import get_winners
            winners = await get_winners(giveaway_id)

            if winners:
                winner_names = []
                for winner in winners:
                    try:
                        user = await client.get_users(winner["user_id"])
                        winner_names.append(f"@{user.username}" if user.username else f"User {user.id}")
                    except:
                        winner_names.append(f"User {winner['user_id']}")

                winners_text = "\n".join([f"{i}. {name}" for i, name in enumerate(winner_names, 1)])

                try:
                    await callback_query.answer(
                        f"🏁 Giveaway Ended\n\nWinners:\n{winners_text}",
                        show_alert=True
                    )
                except:
                    pass
            else:
                try:
                    await callback_query.answer("🏁 Giveaway ended with no winners.", show_alert=True)
                except:
                    pass
    except Exception as e:
        print(f"Error in reload_status_callback: {e}")

def register_giveaway_callback_handlers(app: Client):
    app.add_handler(CallbackQueryHandler(
        reload_status_callback,
        filters.create(lambda _, __, q: q.data.startswith("reload_"))
    ))
