from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatMemberStatus
from database.channels import list_channels, set_default_channel, remove_channel, get_channel
from database.user_state import set_user_state, get_user_state, clear_user_state
from menus.keyboards import build_manage_channels_menu, build_main_menu
from utils.formatters import format_channel_name
from utils.filters import user_state_filter

async def manage_channels_menu_handler(client: Client, message: Message):
    await message.reply_text(
        "🗂 **Manage Channels**\n\n"
        "Choose an action:",
        reply_markup=build_manage_channels_menu()
    )

async def view_all_channels_handler(client: Client, message: Message):
    channels = await list_channels(message.from_user.id)

    if not channels:
        await message.reply_text(
            "📭 **No Channels Added**\n\n"
            "Use '➕ Add Channel' to add your first channel.",
            reply_markup=build_manage_channels_menu()
        )
        return

    text = "📋 **Your Channels:**\n\n"

    for idx, channel in enumerate(channels, 1):
        status_emoji = "✅" if channel.get("status") == "active" else "⚠️"
        default_marker = " 🏷 (Default)" if channel.get("default") else ""

        text += (
            f"{idx}. {status_emoji} {format_channel_name(channel['title'], channel.get('username'))}{default_marker}\n"
            f"   🆔 ID: `{channel['channel_id']}`\n\n"
        )

    await message.reply_text(text, reply_markup=build_manage_channels_menu())


async def remove_channel_menu_handler(client: Client, message: Message):
    channels = await list_channels(message.from_user.id)

    if not channels:
        await message.reply_text(
            "📭 **No Channels to Remove**",
            reply_markup=build_manage_channels_menu()
        )
        return

    text = "❌ **Remove Channel**\n\nSend the Channel ID to remove:\n\n"

    for idx, channel in enumerate(channels, 1):
        text += f"{idx}. {channel['title']} - `{channel['channel_id']}`\n"

    await message.reply_text(text, reply_markup=build_manage_channels_menu())
    await set_user_state(message.from_user.id, "awaiting_remove_channel_id")

async def remove_channel_input_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if not user_state or user_state.get("state") != "awaiting_remove_channel_id":
        return

    try:
        channel_id = int(message.text.strip())
        channel = await get_channel(message.from_user.id, channel_id)

        if not channel:
            await message.reply_text(
                "❌ Channel not found in your list.",
                reply_markup=build_manage_channels_menu()
            )
            await clear_user_state(message.from_user.id)
            return

        await remove_channel(message.from_user.id, channel_id)

        await message.reply_text(
            f"✅ **Channel Removed**\n\n"
            f"📢 {format_channel_name(channel['title'], channel.get('username'))}",
            reply_markup=build_manage_channels_menu()
        )

        await clear_user_state(message.from_user.id)

    except ValueError:
        await message.reply_text(
            "❌ Invalid Channel ID format.",
            reply_markup=build_manage_channels_menu()
        )
        await clear_user_state(message.from_user.id)

async def back_to_main_menu_handler(client: Client, message: Message):
    await clear_user_state(message.from_user.id)
    await message.reply_text(
        "🏠 **Main Menu**",
        reply_markup=build_main_menu()
    )

def register_manage_channels_handlers(app: Client):
    app.add_handler(MessageHandler(
        manage_channels_menu_handler,
        filters.create(lambda _, __, m: m.text == "🗂 Manage Channels") & filters.private
    ))
    app.add_handler(MessageHandler(
        view_all_channels_handler,
        filters.create(lambda _, __, m: m.text == "🔍 View All Channels") & filters.private
    ))
    app.add_handler(MessageHandler(
        remove_channel_menu_handler,
        filters.create(lambda _, __, m: m.text == "❌ Remove Channel") & filters.private
    ))
    app.add_handler(MessageHandler(
        back_to_main_menu_handler,
        filters.create(lambda _, __, m: m.text == "🔙 Back to Main Menu") & filters.private
    ))
    app.add_handler(MessageHandler(
        remove_channel_input_handler,
        user_state_filter(state_value="awaiting_remove_channel_id") &
        filters.private & filters.text
    ))
