from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.enums import ChatType, ChatMemberStatus
from database.user_state import set_user_state, get_user_state, clear_user_state
from database.channels import save_channel
from menus.keyboards import build_main_menu
from utils.validators import ensure_chat_type_channel
from utils.filters import user_state_filter

async def add_channel_menu_handler(client: Client, message: Message):
    await set_user_state(message.from_user.id, "awaiting_channel_id")

    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_channel")]
    ])

    await message.reply_text(
        "📢 **Add a New Channel**\n\n"
        "Send the Channel ID or @username.\n\n"
        "Make sure the bot is an admin in that channel with proper permissions.\n\n"
        "📋 **Format Example:**\n"
        "• -1001234567890\n\n"
        "💡 **How to find Chat ID:**\n"
        "🤖 Use the @username_to_id_bot to get chat ID",
        reply_markup=cancel_keyboard
    )

async def add_channel_input_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if not user_state or user_state.get("state") != "awaiting_channel_id":
        return

    if message.text and message.text.startswith("/"):
        return

    channel_input = message.text.strip()

    try:
        chat = await client.get_chat(channel_input)
        ensure_chat_type_channel(chat)

        # Check if the user is an admin in the channel
        try:
            user_member = await client.get_chat_member(chat.id, message.from_user.id)
            if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(
                    "❌ **Failed to link channel**\n\n"
                    "You must be an admin in this channel to add it to the bot.",
                    reply_markup=build_main_menu()
                )
                await clear_user_state(message.from_user.id)
                return
        except Exception as e:
            await message.reply_text(
                "❌ **Failed to verify your admin status**\n\n"
                "Make sure you are an admin in this channel.",
                reply_markup=build_main_menu()
            )
            await clear_user_state(message.from_user.id)
            return

        bot_member = await client.get_chat_member(chat.id, "me")

        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text(
                "❌ **Failed to link channel**\n\n"
                "I'm not an admin in this channel. Please add me as an admin and try again.",
                reply_markup=build_main_menu()
            )
            await clear_user_state(message.from_user.id)
            return

        if not (bot_member.privileges.can_post_messages and
                bot_member.privileges.can_edit_messages and
                bot_member.privileges.can_delete_messages):
            await message.reply_text(
                "❌ **Insufficient Permissions**\n\n"
                "I need the following admin permissions:\n"
                "- Post messages\n"
                "- Edit messages\n"
                "- Delete messages\n\n"
                "Please grant these permissions and try again.",
                reply_markup=build_main_menu()
            )
            await clear_user_state(message.from_user.id)
            return

        await save_channel(
            owner_id=message.from_user.id,
            channel_id=chat.id,
            title=chat.title,
            username=chat.username
        )

        channel_name = f"{chat.title} (@{chat.username})" if chat.username else chat.title

        await message.reply_text(
            f"✅ **Channel Linked Successfully!**\n\n"
            f"📢 {channel_name}\n"
            f"🆔 Channel ID: `{chat.id}`\n\n"
            f"You can now create giveaways in this channel.",
            reply_markup=build_main_menu()
        )

        await clear_user_state(message.from_user.id)

    except ValueError as e:
        await message.reply_text(
            f"❌ **Error:** {str(e)}",
            reply_markup=build_main_menu()
        )
        await clear_user_state(message.from_user.id)
    except Exception as e:
        await message.reply_text(
            "❌ **Failed to link channel**\n\n"
            "Make sure:\n"
            "- The channel exists\n"
            "- The ID/username is correct\n"
            "- I'm an admin in the channel\n\n"
            f"Error: {str(e)}",
            reply_markup=build_main_menu()
        )
        await clear_user_state(message.from_user.id)

async def cancel_add_channel_callback(client: Client, callback_query: CallbackQuery):
    await clear_user_state(callback_query.from_user.id)
    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "❌ Channel addition cancelled.",
        reply_markup=build_main_menu()
    )
    await callback_query.answer()

def register_add_channel_handlers(app: Client):
    app.add_handler(
        MessageHandler(
            add_channel_menu_handler,
            filters.create(lambda _, __, m: m.text == "➕ Add Channel") & filters.private
        )
    )
    app.add_handler(
        MessageHandler(
            add_channel_input_handler,
            user_state_filter(state_value="awaiting_channel_id") &
            filters.private & filters.text
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            cancel_add_channel_callback,
            filters.create(lambda _, __, q: q.data == "cancel_add_channel")
        )
    )
