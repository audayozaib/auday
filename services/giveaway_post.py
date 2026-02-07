from pyrogram import Client
from menus.keyboards import build_giveaway_inline_buttons
from utils.formatters import format_time_remaining, format_prize_display

async def post_giveaway_message(client: Client, giveaway: dict):
    channel_id = giveaway["channel_id"]
    giveaway_id = str(giveaway["_id"])

    bot_me = await client.get_me()
    bot_username = bot_me.username

    required_subs_text = ""
    if giveaway.get("required_channels"):
        required_subs_text = "\n📢 Required Subscriptions:\n"
        for channel_id_req in giveaway["required_channels"]:
            try:
                chat = await client.get_chat(channel_id_req)
                channel_mention = f"@{chat.username}" if chat.username else f"Channel ID: {chat.id}"
                required_subs_text += f"   - {channel_mention}\n"
            except:
                required_subs_text += f"   - Channel ID: {channel_id_req}\n"

    prize_display = format_prize_display(giveaway["prize_lines"])

    text = (
        f"✅ **GIVEAWAY STARTED**\n\n"
        f"🎁 **{giveaway['title']}**\n\n"
        f"📝 **Description:**\n{giveaway['description']}"
        f"{required_subs_text}\n"
        f"🏆 **Prize:** {prize_display}\n"
        f"⏳ **Deadline:** {format_time_remaining(giveaway['ends_at'])} remaining\n"
        f"🏅 **Winner Selection:** {giveaway['winner_type'].replace('_', ' ').title()}\n"
        f"👥 **Total Participants:** 0\n"
        f"👥 **Total Winners:** {giveaway['winner_count']}\n\n"
        f"🎯 Tap below to participate!"
    )

    image_file_id = giveaway.get("image_file_id")

    if image_file_id:
        msg = await client.send_photo(
            chat_id=channel_id,
            photo=image_file_id,
            caption=text,
            reply_markup=build_giveaway_inline_buttons(giveaway_id, bot_username)
        )
    else:
        msg = await client.send_message(
            chat_id=channel_id,
            text=text,
            reply_markup=build_giveaway_inline_buttons(giveaway_id, bot_username)
        )

    return msg

async def update_giveaway_post(client: Client, giveaway: dict, participant_count: int):
    channel_id = giveaway["channel_id"]
    message_id = giveaway.get("message_id")
    giveaway_id = str(giveaway["_id"])

    bot_me = await client.get_me()
    bot_username = bot_me.username

    if not message_id:
        return

    required_subs_text = ""
    if giveaway.get("required_channels"):
        required_subs_text = "\n📢 Required Subscriptions:\n"
        for channel_id_req in giveaway["required_channels"]:
            try:
                chat = await client.get_chat(channel_id_req)
                channel_mention = f"@{chat.username}" if chat.username else f"Channel ID: {chat.id}"
                required_subs_text += f"   - {channel_mention}\n"
            except:
                required_subs_text += f"   - Channel ID: {channel_id_req}\n"

    prize_display = format_prize_display(giveaway["prize_lines"])

    time_remaining = format_time_remaining(giveaway['ends_at'])

    text = (
        f"✅ **GIVEAWAY STARTED**\n\n"
        f"🎁 **{giveaway['title']}**\n\n"
        f"📝 **Description:**\n{giveaway['description']}"
        f"{required_subs_text}\n"
        f"🏆 **Prize:** {prize_display}\n"
        f"⏳ **Deadline:** {time_remaining} remaining\n"
        f"🏅 **Winner Selection:** {giveaway['winner_type'].replace('_', ' ').title()}\n"
        f"👥 **Total Participants:** {participant_count}\n"
        f"👥 **Total Winners:** {giveaway['winner_count']}\n\n"
        f"🎯 Tap below to participate!"
    )

    image_file_id = giveaway.get("image_file_id")

    try:
        if image_file_id:
            await client.edit_message_caption(
                chat_id=channel_id,
                message_id=message_id,
                caption=text,
                reply_markup=build_giveaway_inline_buttons(giveaway_id, bot_username)
            )
        else:
            await client.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=text,
                reply_markup=build_giveaway_inline_buttons(giveaway_id, bot_username)
            )
    except:
        pass
