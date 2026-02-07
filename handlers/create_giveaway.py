from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.enums import ChatType
from database.user_state import set_user_state, get_user_state, clear_user_state, update_user_state_data
from database.channels import list_channels, get_default_channel
from database.giveaways import create_giveaway, update_giveaway_message_id
from menus.keyboards import build_main_menu, build_winner_type_menu, build_channel_selection_inline, build_skip_button, build_confirm_cancel_buttons
from utils.validators import (
    validate_positive_int, validate_winner_type,
    parse_duration_to_seconds, parse_prize_block, ensure_chat_type_channel
)
from utils.formatters import format_prize_display
from services.giveaway_post import post_giveaway_message
from utils.filters import user_state_filter

async def advance_template_flow(user_id, data, message_obj, is_callback=False):
    """Helper function to advance template giveaway creation to the next step"""
    template_data = data.get("template_data", {})
    current_step = data.get("current_step", 2)
    total_steps = data.get("total_steps", 2)

    # Check what's next in order
    if not template_data.get("duration_seconds"):
        await set_user_state(user_id, "giveaway_template_duration", {**data, "template_data": template_data, "current_step": current_step + 1})
        text = f"**Step {current_step + 1}/{total_steps}:** Enter giveaway duration.\n\nFormat: 5m, 1h, 2d (m=minutes, h=hours, d=days)"
    elif not template_data.get("winners_count"):
        await set_user_state(user_id, "giveaway_template_winners", {**data, "template_data": template_data, "current_step": current_step + 1})
        text = f"**Step {current_step + 1}/{total_steps}:** Enter the number of winners."
    elif not template_data.get("winner_type"):
        await set_user_state(user_id, "giveaway_template_winner_type", {**data, "template_data": template_data, "current_step": current_step + 1})
        text = f"**Step {current_step + 1}/{total_steps}:** Choose winner selection type:"
        if is_callback:
            try:
                await message_obj.edit_message_text(text, reply_markup=build_winner_type_menu())
            except:
                await message_obj.message.reply_text(text, reply_markup=build_winner_type_menu())
        else:
            await message_obj.reply_text(text, reply_markup=build_winner_type_menu())
        return
    elif not template_data.get("required_channels") or len(template_data.get("required_channels", [])) == 0:
        await set_user_state(user_id, "giveaway_template_channels", {**data, "template_data": template_data, "current_step": current_step + 1})
        text = f"**Step {current_step + 1}/{total_steps}:** Send one or more channel IDs or @usernames that participants must join (optional).\n\nYou can separate multiple channels with spaces or newlines."
        if is_callback:
            try:
                await message_obj.edit_message_text(text, reply_markup=build_skip_button())
            except:
                await message_obj.message.reply_text(text, reply_markup=build_skip_button())
        else:
            await message_obj.reply_text(text, reply_markup=build_skip_button())
        return
    else:
        await set_user_state(user_id, "giveaway_template_prize", {**data, "template_data": template_data, "current_step": current_step + 1})
        text = (f"**Step {current_step + 1}/{total_steps}:** Send the giveaway prize details\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "Prize Formats:\n"
                "• user:pass → johndoe:12345\n"
                "• email:pass → test@gmail.com:1234\n"
                "• code/key → ABC1-DEF2-GHI3\n\n"
                "Note: One prize per line. Auto-detected.")

    if is_callback:
        try:
            await message_obj.edit_message_text(text)
        except:
            await message_obj.message.reply_text(text)
    else:
        await message_obj.reply_text(text)

async def create_giveaway_menu_handler(client: Client, message: Message):
    channels = await list_channels(message.from_user.id)

    if not channels:
        await message.reply_text(
            "📭 **No Channels Available**\n\n"
            "Please add a channel first using '➕ Add Channel'.",
            reply_markup=build_main_menu()
        )
        return

    await set_user_state(message.from_user.id, "giveaway_channel_select", {"selected_channels": []})
    await message.reply_text(
        "🎁 **Create Giveaway**\n\n"
        "**Step 1/8:** Select one or more channels for this giveaway.\n\n"
        "Tap to toggle selection, then confirm.",
        reply_markup=build_channel_selection_inline(channels, [])
    )

async def channel_toggle_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_channel_select":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    channel_id = int(callback_query.data.replace("togglech_", ""))
    data = user_state.get("data", {})
    selected = data.get("selected_channels", [])

    if channel_id in selected:
        selected.remove(channel_id)
    else:
        selected.append(channel_id)

    await update_user_state_data(callback_query.from_user.id, {"selected_channels": selected})

    channels = await list_channels(callback_query.from_user.id)

    try:
        await callback_query.edit_message_reply_markup(
            reply_markup=build_channel_selection_inline(channels, selected)
        )
        await callback_query.answer()
    except:
        await callback_query.answer()

async def channel_confirm_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_channel_select":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    data = user_state.get("data", {})
    selected = data.get("selected_channels", [])

    if not selected:
        await callback_query.answer("⚠️ Please select at least one channel!", show_alert=True)
        return

    await callback_query.message.delete()

    from_template = data.get("from_template", False)

    if from_template:
        template_data = data.get("template_data", {})

        # Calculate missing steps for proper step numbering
        missing_steps = []
        if not template_data.get("image_file_id"):
            missing_steps.append("image")
        if not template_data.get("duration_seconds"):
            missing_steps.append("duration")
        if not template_data.get("winners_count"):
            missing_steps.append("winners")
        if not template_data.get("winner_type"):
            missing_steps.append("winner_type")
        if not template_data.get("required_channels") or len(template_data.get("required_channels", [])) == 0:
            missing_steps.append("channels")
        missing_steps.append("prize")  # Prize is always required

        total_steps = len(missing_steps) + 1  # +1 for channel selection
        current_step = 2  # We're past channel selection (step 1)

        if not template_data.get("image_file_id"):
            await set_user_state(callback_query.from_user.id, "giveaway_template_image", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Send a giveaway image (Optional)\n\n"
                "🖼️ Upload an image for your giveaway post.\n\n"
                "Send /cancel to abort.",
                reply_markup=build_skip_button()
            )
        elif not template_data.get("duration_seconds"):
            await set_user_state(callback_query.from_user.id, "giveaway_template_duration", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Enter giveaway duration.\n\n"
                "Format: 5m, 1h, 2d (m=minutes, h=hours, d=days)"
            )
        elif not template_data.get("winners_count"):
            await set_user_state(callback_query.from_user.id, "giveaway_template_winners", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Enter the number of winners."
            )
        elif not template_data.get("winner_type"):
            from menus.keyboards import build_winner_type_menu
            await set_user_state(callback_query.from_user.id, "giveaway_template_winner_type", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Choose winner selection type:",
                reply_markup=build_winner_type_menu()
            )
        elif not template_data.get("required_channels") or len(template_data.get("required_channels", [])) == 0:
            await set_user_state(callback_query.from_user.id, "giveaway_template_channels", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Send one or more channel IDs or @usernames that participants must join (optional).\n\n"
                "You can separate multiple channels with spaces or newlines.",
                reply_markup=build_skip_button()
            )
        else:
            await set_user_state(callback_query.from_user.id, "giveaway_template_prize", {
                "channel_ids": selected,
                "from_template": True,
                "template_data": template_data,
                "current_step": current_step,
                "total_steps": total_steps
            })
            await callback_query.message.reply_text(
                f"**Step {current_step}/{total_steps}:** Send the giveaway prize details\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "Prize Formats:\n"
                "• user:pass → johndoe:12345\n"
                "• email:pass → test@gmail.com:1234\n"
                "• code/key → ABC1-DEF2-GHI3\n\n"
                "Note: One prize per line. Auto-detected."
            )
    else:
        await set_user_state(callback_query.from_user.id, "giveaway_image", {"channel_ids": selected})
        await callback_query.message.reply_text(
            "**Step 2/8:** Send a giveaway image (Optional)\n\n"
            "🖼️ Upload an image for your giveaway post.\n\n"
            "Send /cancel to abort.",
            reply_markup=build_skip_button()
        )

async def channel_cancel_callback(client: Client, callback_query: CallbackQuery):
    await clear_user_state(callback_query.from_user.id)
    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "❌ Giveaway creation cancelled.",
        reply_markup=build_main_menu()
    )

async def giveaway_wizard_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if not user_state or not user_state.get("state", "").startswith("giveaway_"):
        return

    if message.text and message.text.startswith("/"):
        return

    state = user_state.get("state")
    data = user_state.get("data", {})

    try:
        if state == "giveaway_channel_select":
            await message.reply_text("❌ Please use the buttons above to select channels.")

        elif state == "giveaway_template_prize":
            prize_lines = parse_prize_block(message.text.strip())
            prize_display = format_prize_display(prize_lines)

            template_data = data.get("template_data", {})

            giveaway_data = {
                "channel_ids": data.get("channel_ids"),
                "image_file_id": template_data.get("image_file_id"),
                "title": template_data.get("title", "Giveaway"),
                "description": template_data.get("description", "Join to win!"),
                "duration_seconds": template_data.get("duration_seconds", 86400),
                "prize_lines": prize_lines,
                "winner_count": template_data.get("winners_count", 1),
                "winner_type": template_data.get("winner_type", "random"),
                "required_channels": template_data.get("required_channels", [])
            }

            prize_display = format_prize_display(prize_lines)
            duration_seconds = template_data.get("duration_seconds", 86400)
            duration_hours = duration_seconds / 3600
            from utils.formatters import format_duration_from_hours
            duration_text = format_duration_from_hours(duration_hours)

            winner_type = giveaway_data.get('winner_type')
            if winner_type == "random":
                winner_type_display = "Random"
            elif winner_type == "first_x_participants":
                winner_type_display = "First-X Participants"
            else:
                winner_type_display = "Random (Default)"

            preview = (
                f"📋 **Giveaway Preview**\n\n"
                f"🎁 **Title:** {giveaway_data['title']}\n"
                f"📝 **Description:** {giveaway_data['description']}\n"
                f"🏆 **Prize:** {prize_display}\n"
                f"⏳ **Duration:** {duration_text}\n"
                f"👥 **Winners:** {giveaway_data['winner_count']}\n"
                f"🎯 **Winner Type:** {winner_type_display}\n"
                f"📢 **Required Subs:** {len(giveaway_data['required_channels'])}"
            )

            await set_user_state(message.from_user.id, "giveaway_confirm", giveaway_data)
            await message.reply_text(preview, reply_markup=build_confirm_cancel_buttons())

        elif state == "giveaway_template_image":
            template_data = data.get("template_data", {})

            if message.photo:
                image_file_id = message.photo.file_id
                template_data["image_file_id"] = image_file_id
                await message.reply_text("✅ Image uploaded!")

            await advance_template_flow(message.from_user.id, {**data, "template_data": template_data}, message)

        elif state == "giveaway_template_duration":
            duration_text = message.text.strip()

            try:
                duration_seconds = parse_duration_to_seconds(duration_text)

                template_data = data.get("template_data", {})
                template_data["duration_seconds"] = duration_seconds

                await advance_template_flow(message.from_user.id, {**data, "template_data": template_data}, message)
            except:
                await message.reply_text("❌ Invalid duration format. Use: 5m, 1h, 2d")

        elif state == "giveaway_template_winners":
            winner_count_text = message.text.strip()

            try:
                winner_count = validate_positive_int(winner_count_text)

                template_data = data.get("template_data", {})
                template_data["winners_count"] = winner_count

                await advance_template_flow(message.from_user.id, {**data, "template_data": template_data}, message)
            except:
                await message.reply_text("❌ Please enter a valid number.")

        elif state == "giveaway_template_channels":
            template_data = data.get("template_data", {})
            required_channels = []

            if message.text.strip().lower() != "skip":
                lines = message.text.replace('\n', ' ').split()
                lines = [line.strip() for line in lines if line.strip()]

                for line in lines:
                    try:
                        chat = await client.get_chat(line)
                        required_channels.append(chat.id)
                    except Exception as e:
                        await message.reply_text(f"❌ Invalid channel: {line}\n{str(e)}")
                        return

            template_data["required_channels"] = required_channels

            await advance_template_flow(message.from_user.id, {**data, "template_data": template_data}, message)

        elif state == "giveaway_image":
            text_lower = message.text.strip().lower() if message.text else ""
            from_template = data.get("from_template", False)

            if text_lower == "skip":
                if from_template:
                    await set_user_state(message.from_user.id, "giveaway_title", {**data, "image_file_id": None})
                    await message.reply_text("**Step 3/3:** Enter the giveaway title.\n\nSend /cancel to abort.")
                else:
                    await set_user_state(message.from_user.id, "giveaway_title", {**data, "image_file_id": None})
                    await message.reply_text("**Step 3/8:** Enter the giveaway title.\n\nSend /cancel to abort.")
            elif message.photo:
                image_file_id = message.photo.file_id
                await update_user_state_data(message.from_user.id, {"image_file_id": image_file_id})
                if from_template:
                    await set_user_state(message.from_user.id, "giveaway_title", {**data, "image_file_id": image_file_id})
                    await message.reply_text("✅ Image uploaded!\n\n**Step 3/3:** Enter the giveaway title.\n\nSend /cancel to abort.")
                else:
                    await set_user_state(message.from_user.id, "giveaway_title", {**data, "image_file_id": image_file_id})
                    await message.reply_text("✅ Image uploaded!\n\n**Step 3/8:** Enter the giveaway title.\n\nSend /cancel to abort.")
            else:
                await message.reply_text("❌ Please send an image or type 'skip' to continue.")

        elif state == "giveaway_title":
            title = message.text.strip()
            if not title:
                await message.reply_text("❌ Title cannot be empty.")
                return

            await update_user_state_data(message.from_user.id, {"title": title})

            from_template = data.get("from_template", False)

            if from_template:
                await set_user_state(message.from_user.id, "giveaway_description_template", {**data, "title": title})
                await message.reply_text("Enter a short description for this giveaway:")
            else:
                await set_user_state(message.from_user.id, "giveaway_description", {**data, "title": title})
                await message.reply_text("**Step 4/8:** Enter a short description.")

        elif state == "giveaway_description":
            description = message.text.strip()
            if not description:
                await message.reply_text("❌ Description cannot be empty.")
                return

            await update_user_state_data(message.from_user.id, {"description": description})
            await set_user_state(message.from_user.id, "giveaway_duration", {**data, "description": description})

            await message.reply_text(
                "**Step 5/8:** Enter giveaway duration.\n\n"
                "Format: 5m, 1h, 2d (m=minutes, h=hours, d=days)"
            )

        elif state == "giveaway_description_template":
            description = message.text.strip()
            if not description:
                await message.reply_text("❌ Description cannot be empty.")
                return

            template_data = data.get("template_data", {})

            duration_seconds = template_data.get("duration_seconds", 86400)
            prize_text = template_data.get("prize", "")
            prize_lines = prize_text.split('\n')
            winner_count = template_data.get("winners_count", 1)
            required_channels = template_data.get("required_channels", [])

            preview_data = {
                **data,
                "description": description,
                "duration_seconds": duration_seconds,
                "prize_lines": prize_lines,
                "winner_count": winner_count,
                "winner_type": template_data.get("winner_type", "random"),
                "required_channels": required_channels
            }

            prize_display = format_prize_display(prize_lines)

            duration_hours = duration_seconds / 3600
            from utils.formatters import format_duration_from_hours
            duration_text = format_duration_from_hours(duration_hours)

            winner_type = preview_data.get('winner_type')
            if winner_type == "random":
                winner_type_display = "Random"
            elif winner_type == "first_x_participants":
                winner_type_display = "First-X Participants"
            else:
                winner_type_display = "Random (Default)"

            preview = (
                f"📋 **Giveaway Preview**\n\n"
                f"🎁 **Title:** {preview_data['title']}\n"
                f"📝 **Description:** {description}\n"
                f"🏆 **Prize:** {prize_display}\n"
                f"⏳ **Duration:** {duration_text}\n"
                f"👥 **Winners:** {winner_count}\n"
                f"🎯 **Winner Type:** {winner_type_display}\n"
                f"📢 **Required Subs:** {len(required_channels)}"
            )

            await set_user_state(message.from_user.id, "giveaway_confirm", preview_data)
            await message.reply_text(preview, reply_markup=build_confirm_cancel_buttons())

        elif state == "giveaway_duration":
            duration_seconds = parse_duration_to_seconds(message.text.strip())

            await update_user_state_data(message.from_user.id, {"duration_seconds": duration_seconds})
            await set_user_state(message.from_user.id, "giveaway_winner_count", {**data, "duration_seconds": duration_seconds})

            await message.reply_text("**Step 6/8:** Enter the number of winners.")

        elif state == "giveaway_winner_count":
            winner_count = validate_positive_int(message.text.strip())

            await update_user_state_data(message.from_user.id, {"winner_count": winner_count})
            await set_user_state(message.from_user.id, "giveaway_winner_type", {**data, "winner_count": winner_count})

            await message.reply_text(
                "**Step 7/8:** Choose winner selection type:",
                reply_markup=build_winner_type_menu()
            )

        elif state == "giveaway_winner_type":
            await message.reply_text("❌ Please use the buttons above to select winner type.")

        elif state == "giveaway_prize":
            prize_lines = parse_prize_block(message.text.strip())
            prize_display = format_prize_display(prize_lines)

            await update_user_state_data(message.from_user.id, {"prize_lines": prize_lines})
            await set_user_state(message.from_user.id, "giveaway_required_subs", {**data, "prize_lines": prize_lines})

            await message.reply_text(
                f"✅ **Prize Received!**\n\n"
                f"🎁 **Detected Prize Type:** {prize_display}\n"
                f"📦 **Total Items:** {len(prize_lines)}\n\n"
                f"**Step 7/8:** Send one or more channel IDs or @usernames that participants must join (optional).\n\n"
                "You can separate multiple channels with spaces or newlines.\n\n",
                reply_markup=build_skip_button()
            )

        elif state == "giveaway_required_subs":
            text = message.text.strip().lower()

            if text == "skip":
                required_channels = []
            else:
                lines = message.text.replace('\n', ' ').split()
                lines = [line.strip() for line in lines if line.strip()]
                required_channels = []

                for line in lines:
                    try:
                        chat = await client.get_chat(line)
                        ensure_chat_type_channel(chat)
                        required_channels.append(chat.id)
                    except Exception as e:
                        await message.reply_text(f"❌ Invalid channel: {line}\n{str(e)}")
                        return

            await update_user_state_data(message.from_user.id, {"required_channels": required_channels})

            data = (await get_user_state(message.from_user.id)).get("data", {})

            prize_display = format_prize_display(data['prize_lines'])

            winner_type = data.get('winner_type')
            if winner_type == "random":
                winner_type_display = "Random"
            elif winner_type == "first_x_participants":
                winner_type_display = "First-X Participants"
            else:
                winner_type_display = "Random (Default)"

            preview = (
                f"📋 **Giveaway Preview**\n\n"
                f"🎁 **Title:** {data['title']}\n"
                f"📝 **Description:** {data['description']}\n"
                f"🏆 **Prize:** {prize_display}\n"
                f"⏳ **Duration:** {message.text if state != 'giveaway_required_subs' else 'Set'}\n"
                f"👥 **Winners:** {data['winner_count']}\n"
                f"🎯 **Winner Type:** {winner_type_display}\n"
                f"📢 **Required Subs:** {len(required_channels)}"
            )

            await set_user_state(message.from_user.id, "giveaway_confirm", {**data, "required_channels": required_channels})
            await message.reply_text(preview, reply_markup=build_confirm_cancel_buttons())

        elif state == "giveaway_confirm":
            await message.reply_text("❌ Please use the buttons above to confirm or cancel.")

    except ValueError as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")
    except Exception as e:
        await message.reply_text(f"❌ **Unexpected Error:** {str(e)}")
        await clear_user_state(message.from_user.id)

async def skip_step_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state:
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    state = user_state.get("state")
    data = user_state.get("data", {})

    if state == "giveaway_template_image":
        template_data = data.get("template_data", {})
        await advance_template_flow(callback_query.from_user.id, {**data, "template_data": template_data}, callback_query, is_callback=True)

    elif state == "giveaway_template_channels":
        template_data = data.get("template_data", {})
        template_data["required_channels"] = []
        await advance_template_flow(callback_query.from_user.id, {**data, "template_data": template_data}, callback_query, is_callback=True)

    elif state == "giveaway_image":
        await set_user_state(callback_query.from_user.id, "giveaway_title", {**data, "image_file_id": None})
        try:
            await callback_query.edit_message_text("**Step 3/8:** Enter the giveaway title.\n\nSend /cancel to abort.")
        except:
            await callback_query.message.reply_text("**Step 3/8:** Enter the giveaway title.\n\nSend /cancel to abort.")
    elif state == "giveaway_required_subs":
        await update_user_state_data(callback_query.from_user.id, {"required_channels": []})
        data = (await get_user_state(callback_query.from_user.id)).get("data", {})

        prize_display = format_prize_display(data['prize_lines'])

        winner_type = data.get('winner_type')
        if winner_type == "random":
            winner_type_display = "Random"
        elif winner_type == "first_x_participants":
            winner_type_display = "First-X Participants"
        else:
            winner_type_display = "Random (Default)"

        preview = (
            f"📋 **Giveaway Preview**\n\n"
            f"🎁 **Title:** {data['title']}\n"
            f"📝 **Description:** {data['description']}\n"
            f"🏆 **Prize:** {prize_display}\n"
            f"⏳ **Duration:** Set\n"
            f"👥 **Winners:** {data['winner_count']}\n"
            f"🎯 **Winner Type:** {winner_type_display}\n"
            f"📢 **Required Subs:** 0"
        )

        await set_user_state(callback_query.from_user.id, "giveaway_confirm", {**data, "required_channels": []})
        try:
            await callback_query.edit_message_text(preview, reply_markup=build_confirm_cancel_buttons())
        except:
            await callback_query.message.reply_text(preview, reply_markup=build_confirm_cancel_buttons())

    await callback_query.answer()

async def winner_type_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_winner_type":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    data = user_state.get("data", {})

    if callback_query.data == "winner_random":
        winner_type = "random"
    elif callback_query.data == "winner_first_x":
        winner_type = "first_x_participants"
    else:
        await callback_query.answer("Invalid selection", show_alert=True)
        return

    await update_user_state_data(callback_query.from_user.id, {"winner_type": winner_type})
    await set_user_state(callback_query.from_user.id, "giveaway_prize", {**data, "winner_type": winner_type})

    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "**Step 8/8:** Send the giveaway prize details\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Prize Formats:\n"
        "• user:pass → johndoe:12345\n"
        "• email:pass → test@gmail.com:1234\n"
        "• code/key → ABC1-DEF2-GHI3\n\n"
        "Note: One prize per line. Auto-detected."
    )
    await callback_query.answer()

async def template_winner_type_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_template_winner_type":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    data = user_state.get("data", {})
    template_data = data.get("template_data", {})

    if callback_query.data == "winner_random":
        winner_type = "random"
    elif callback_query.data == "winner_first_x":
        winner_type = "first_x_participants"
    else:
        await callback_query.answer("Invalid selection", show_alert=True)
        return

    template_data["winner_type"] = winner_type

    await callback_query.message.delete()
    await advance_template_flow(callback_query.from_user.id, {**data, "template_data": template_data}, callback_query.message, is_callback=False)
    await callback_query.answer()

async def confirm_giveaway_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_confirm":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    data = (await get_user_state(callback_query.from_user.id)).get("data", {})
    channel_ids = data.get("channel_ids", [data.get("channel_id")])

    # Default winner_type to "random" if not set
    winner_type = data.get("winner_type", "random")

    await callback_query.message.delete()

    try:
        for channel_id in channel_ids:
            giveaway = await create_giveaway(
                owner_id=callback_query.from_user.id,
                channel_id=channel_id,
                title=data["title"],
                description=data["description"],
                prize_lines=data["prize_lines"],
                winner_type=winner_type,
                winner_count=data["winner_count"],
                required_channels=data["required_channels"],
                duration_seconds=data["duration_seconds"],
                image_file_id=data.get("image_file_id")
            )

            msg = await post_giveaway_message(client, giveaway)
            await update_giveaway_message_id(str(giveaway["_id"]), msg.id)

        # Get channel names
        channel_names = []
        for ch_id in channel_ids:
            try:
                ch = await client.get_chat(ch_id)
                if ch.username:
                    channel_names.append(f"@{ch.username}")
                else:
                    channel_names.append(ch.title)
            except:
                channel_names.append(f"Channel ID: {ch_id}")

        channels_text = "\n".join([f"  • {name}" for name in channel_names])

        await callback_query.message.reply_text(
            "✅ **Giveaway Created Successfully!**\n\n"
            f"🎉 Your giveaway has been posted to:\n\n{channels_text}\n\n"
            f"📊 Winners will be selected automatically when the deadline is reached.",
            reply_markup=build_main_menu()
        )

        await clear_user_state(callback_query.from_user.id)
    except Exception as e:
        await callback_query.message.reply_text(f"❌ **Error:** {str(e)}", reply_markup=build_main_menu())
        await clear_user_state(callback_query.from_user.id)

    await callback_query.answer()

async def cancel_giveaway_callback(client: Client, callback_query: CallbackQuery):
    await clear_user_state(callback_query.from_user.id)
    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "❌ Giveaway creation cancelled.",
        reply_markup=build_main_menu()
    )
    await callback_query.answer()

async def cancel_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if user_state:
        state = user_state.get("state", "")
        await clear_user_state(message.from_user.id)

        if state.startswith("giveaway_"):
            await message.reply_text("❌ Giveaway creation cancelled.", reply_markup=build_main_menu())
        elif state == "awaiting_channel_id":
            await message.reply_text("❌ Add channel cancelled.", reply_markup=build_main_menu())
        else:
            await message.reply_text("❌ Action cancelled.", reply_markup=build_main_menu())

def register_create_giveaway_handlers(app: Client):
    app.add_handler(MessageHandler(
        cancel_handler,
        filters.command("cancel") & filters.private
    ), group=0)
    app.add_handler(MessageHandler(
        create_giveaway_menu_handler,
        filters.create(lambda _, __, m: m.text == "🎁 Create Giveaway") & filters.private
    ), group=1)
    app.add_handler(MessageHandler(
        giveaway_wizard_handler,
        user_state_filter(state_prefix="giveaway_") &
        filters.private & (filters.text | filters.photo)
    ), group=1)
    app.add_handler(CallbackQueryHandler(
        channel_toggle_callback,
        filters.create(lambda _, __, q: q.data.startswith("togglech_"))
    ))
    app.add_handler(CallbackQueryHandler(
        channel_confirm_callback,
        filters.create(lambda _, __, q: q.data == "confirm_channels")
    ))
    app.add_handler(CallbackQueryHandler(
        channel_cancel_callback,
        filters.create(lambda _, __, q: q.data == "cancel_channels")
    ))
    app.add_handler(CallbackQueryHandler(
        skip_step_callback,
        filters.create(lambda _, __, q: q.data == "skip_step")
    ))
    async def is_giveaway_winner_type(_, __, query):
        from database.user_state import get_user_state
        user_state = await get_user_state(query.from_user.id)
        if not user_state:
            return False
        state = user_state.get("state")
        return query.data.startswith("winner_") and state == "giveaway_winner_type"

    app.add_handler(CallbackQueryHandler(
        winner_type_callback,
        filters.create(is_giveaway_winner_type)
    ))

    async def is_template_winner_type(_, __, query):
        from database.user_state import get_user_state
        user_state = await get_user_state(query.from_user.id)
        if not user_state:
            return False
        state = user_state.get("state")
        return query.data.startswith("winner_") and state == "giveaway_template_winner_type"

    app.add_handler(CallbackQueryHandler(
        template_winner_type_callback,
        filters.create(is_template_winner_type)
    ))

    app.add_handler(CallbackQueryHandler(
        confirm_giveaway_callback,
        filters.create(lambda _, __, q: q.data == "confirm_giveaway")
    ))
    app.add_handler(CallbackQueryHandler(
        cancel_giveaway_callback,
        filters.create(lambda _, __, q: q.data == "cancel_giveaway")
    ))
