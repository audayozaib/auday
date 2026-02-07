import random
from pyrogram import Client
from database.giveaways import get_giveaway, update_giveaway_status
from database.participants import get_all_participants
from database.winners import save_winners, mark_prize_delivered
from utils.flood_control import clear_cache

async def end_giveaway_and_select_winners(client: Client, giveaway_id: str):
    giveaway = await get_giveaway(giveaway_id)

    if not giveaway or giveaway["status"] != "active":
        return None

    await update_giveaway_status(giveaway_id, "ending")

    participants = await get_all_participants(giveaway_id)

    if not participants:
        await update_giveaway_status(giveaway_id, "ended")
        await edit_giveaway_message_to_ended(client, giveaway, [])
        return []

    winner_count = min(giveaway["winner_count"], len(participants))
    winner_type = giveaway["winner_type"]

    if winner_type == "random":
        selected_participants = random.sample(participants, winner_count)
    else:
        selected_participants = participants[:winner_count]

    winners_list = [p["user_id"] for p in selected_participants]

    await save_winners(giveaway_id, winners_list)

    await update_giveaway_status(giveaway_id, "ended")

    # Clear flood control cache when giveaway ends
    clear_cache(giveaway_id)

    await edit_giveaway_message_to_ended(client, giveaway, winners_list)

    await dm_prizes_to_winners(client, giveaway, winners_list)

    return winners_list

async def edit_giveaway_message_to_ended(client: Client, giveaway: dict, winners_list: list):
    channel_id = giveaway["channel_id"]
    message_id = giveaway.get("message_id")

    if not message_id:
        return

    winner_type_emoji = "🎲" if giveaway.get("winner_type") == "random" else "⚡"
    winner_type_text = "Random Selection" if giveaway.get("winner_type") == "random" else "First Come First Served"

    if not winners_list:
        text = (
            f"🏁 **GIVEAWAY ENDED**\n\n"
            f"🎁 **{giveaway['title']}**\n\n"
            f"📝 {giveaway.get('description', 'No description')}\n\n"
            f"👥 **Total Participants:** 0\n"
            f"{winner_type_emoji} **Selection Type:** {winner_type_text}\n\n"
            f"❌ No participants joined this giveaway."
        )
    else:
        winner_mentions = []
        max_display = 10

        for idx, user_id in enumerate(winners_list[:max_display], 1):
            try:
                user = await client.get_users(user_id)
                mention = f"@{user.username}" if user.username else f"User {user.id}"
                winner_mentions.append(f"{idx}. {mention}")
            except:
                winner_mentions.append(f"{idx}. User {user_id}")

        winners_text = "\n".join(winner_mentions)

        if len(winners_list) > max_display:
            remaining = len(winners_list) - max_display
            winners_text += f"\n... and **{remaining}** more winner{'s' if remaining > 1 else ''}!"

        text = (
            f"🏁 **GIVEAWAY ENDED**\n\n"
            f"🎁 **{giveaway['title']}**\n\n"
            f"📝 **Description:**{giveaway.get('description', 'No description')}\n\n"
            f"👥 **Total Participants:** {len(await get_all_participants(str(giveaway['_id'])))}\n"
            f"{winner_type_emoji} **Selection Type:** {winner_type_text}\n"
            f"🏆 **Total Winners:** {len(winners_list)}\n\n"
            f"🏅 **Winners:**\n{winners_text}\n\n"
            f"🎉 **Congratulations to all winners!**"
        )

    try:
        await client.edit_message_text(
            chat_id=channel_id,
            message_id=message_id,
            text=text
        )
    except Exception as e:
        print(f"Error editing message: {e}")

async def dm_prizes_to_winners(client: Client, giveaway: dict, winners_list: list):
    prize_lines = giveaway["prize_lines"]
    giveaway_id = str(giveaway["_id"])
    channel_id = giveaway["channel_id"]
    message_id = giveaway.get("message_id")

    if len(prize_lines) == 1:
        prize_text = prize_lines[0]
        for user_id in winners_list:
            try:
                await client.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉🎉🎉 **CONGRATULATIONS!** 🎉🎉🎉\n\n"
                        f"🏆 You are a **WINNER** of the giveaway:\n"
                        f"**{giveaway['title']}**\n\n"
                        f"🎁 **Your Prize:**\n"
                        f"```\n{prize_text}\n```\n\n"
                        f"✨ **Please share a screenshot in the giveaway chat!**\n\n"
                        f"💝 Enjoy your reward!"
                    )
                )
                await mark_prize_delivered(giveaway_id, user_id)
            except Exception as e:
                print(f"Failed to send prize to {user_id}: {e}")

    else:
        for idx, user_id in enumerate(winners_list):
            if idx < len(prize_lines):
                prize_text = prize_lines[idx]
            else:
                prize_text = prize_lines[-1]

            try:
                await client.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉🎉🎉 **CONGRATULATIONS!** 🎉🎉🎉\n\n"
                        f"🏆 You are a **WINNER** of the giveaway:\n"
                        f"**{giveaway['title']}**\n\n"
                        f"🎁 **Your Prize:**\n"
                        f"```\n{prize_text}\n```\n\n"
                        f"✨ **Please share a screenshot in the giveaway chat**\n\n"
                        f"💝 Enjoy your reward!"
                    )
                )
                await mark_prize_delivered(giveaway_id, user_id)
            except Exception as e:
                print(f"Failed to send prize to {user_id}: {e}")
