from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatMemberStatus
from menus.keyboards import build_main_menu
from database.user_state import clear_user_state
from database.giveaways import get_giveaway
from database.participants import add_participant, is_participant
from database.users import save_user

async def check_required_subscriptions(client: Client, user_id: int, channel_ids: list) -> tuple[bool, list]:
    not_joined = []

    for channel_id in channel_ids:
        try:
            member = await client.get_chat_member(channel_id, user_id)
            chat = await client.get_chat(channel_id)

            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                if chat.username:
                    not_joined.append(f"**{chat.title}** [ @{chat.username} ]")
                else:
                    not_joined.append(f"**{chat.title}** [ `{chat.id}` ]")

        except Exception:
            try:
                chat = await client.get_chat(channel_id)
                if chat.username:
                    not_joined.append(f"**{chat.title}** [ @{chat.username} ]")
                else:
                    not_joined.append(f"**{chat.title}** [ `{chat.id}` ]")
            except:
                not_joined.append(f"Channel ID: `{channel_id}`")

    return len(not_joined) == 0, not_joined

async def start_handler(client: Client, message: Message):
    await save_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    await clear_user_state(message.from_user.id)

    args = message.text.split()

    if len(args) > 1 and args[1].startswith("join_"):
        giveaway_id = args[1].replace("join_", "")

        giveaway = await get_giveaway(giveaway_id)

        if not giveaway:
            await message.reply_text(
                "❌ **Giveaway Not Found**\n\n"
                "This giveaway may have been deleted or expired.",
                reply_markup=build_main_menu()
            )
            return

        if giveaway["status"] != "active":
            await message.reply_text(
                "❌ **Giveaway Ended**\n\n"
                "This giveaway has already ended.",
                reply_markup=build_main_menu()
            )
            return

        user_id = message.from_user.id

        if await is_participant(giveaway_id, user_id):
            await message.reply_text(
                "✅ **Already Joined!**\n\n"
                f"You're already participating in: **{giveaway['title']}**",
                reply_markup=build_main_menu()
            )
            return

        if giveaway.get("required_channels"):
            all_joined, not_joined_list = await check_required_subscriptions(
                client, user_id, giveaway["required_channels"]
            )

            if not all_joined:
                channels_text = "\n".join([f"- {ch}" for ch in not_joined_list])
                await message.reply_text(
                    f"⚠️ **Please Join Required Channels First**\n\n"
                    f"{channels_text}\n\n"
                    f"After joining, click the button again.",
                    reply_markup=build_main_menu()
                )
                return

        success = await add_participant(giveaway_id, user_id)

        if success:
            await message.reply_text(
                "🎉 **Successfully Joined!**\n\n"
                f"You're now participating in: **{giveaway['title']}**\n\n"
                f"Good luck! Winners will be announced automatically when the giveaway ends.",
                reply_markup=build_main_menu()
            )
        else:
            await message.reply_text(
                "✅ **Already Joined!**\n\n"
                f"You're already participating in: **{giveaway['title']}**",
                reply_markup=build_main_menu()
            )
        return

    welcome_text = """
🤖 **Welcome to Giveaway Bot!**

This bot helps you create and manage giveaways in your Telegram channels.

**Main Features:**
➕ Add and manage your channels
🎁 Create engaging giveaways
📊 Track analytics and results
🏆 Automatic winner selection

Choose an option from the menu below to get started.
"""

    await message.reply_text(
        welcome_text,
        reply_markup=build_main_menu()
    )

def register_start_handlers(app: Client):
    app.add_handler(MessageHandler(start_handler, filters.command("start") & filters.private))
