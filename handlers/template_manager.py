from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from database.user_state import set_user_state, get_user_state, clear_user_state, update_user_state_data
from database.templates import (
    create_template, get_user_templates, get_template_by_id, delete_template, count_user_templates
)
from menus.keyboards import (
    build_main_menu, build_templates_list, build_template_actions_menu,
    build_back_button, build_template_menu, build_template_skip_button,
    build_template_winner_type_menu
)
from utils.formatters import format_duration_from_hours
from utils.filters import user_state_filter
from utils.validators import validate_positive_int, parse_duration_to_seconds

async def templates_menu_handler(client: Client, message: Message):
    await message.reply_text(
        "📝 **Template Manager**\n\n"
        "Templates help you quickly create giveaways with pre-configured settings.\n\n"
        "Choose an option:",
        reply_markup=build_template_menu()
    )

async def view_templates_callback(client: Client, callback_query: CallbackQuery):
    templates = await get_user_templates(callback_query.from_user.id)

    if not templates:
        try:
            await callback_query.edit_message_text(
                "📝 **Template Library**\n\n"
                "You haven't created any templates yet.\n\n"
                "💡 Create a template to quickly reuse giveaway configurations!",
                reply_markup=build_template_menu()
            )
        except:
            pass
        await callback_query.answer()
        return

    try:
        await callback_query.edit_message_text(
            f"📝 **Template Library**\n\n"
            f"You have **{len(templates)}** saved template(s).\n\n"
            "Tap a template to view or use it:",
            reply_markup=build_templates_list(templates)
        )
    except:
        pass
    await callback_query.answer()

async def create_template_callback(client: Client, callback_query: CallbackQuery):
    await set_user_state(callback_query.from_user.id, "template_create_name", {})

    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "➕ **Create New Template**\n\n"
        "**Step 1/8:** Enter a name for this template.\n\n"
        "Example: 'Weekly Discord Nitro', 'Monthly Premium Keys', etc.\n\n"
        "Send /cancel to abort."
    )
    await callback_query.answer()

async def template_view_callback(client: Client, callback_query: CallbackQuery):
    template_id = callback_query.data.replace("viewtemplate_", "")
    template = await get_template_by_id(template_id, callback_query.from_user.id)

    if not template:
        await callback_query.answer("Template not found!", show_alert=True)
        return

    preview = f"📝 **Template: {template['name']}**\n\n"

    if template.get('title'):
        preview += f"🎁 **Title:** {template['title']}\n"
    if template.get('description'):
        preview += f"📝 **Description:** {template['description'][:50]}...\n"
    if template.get('duration_seconds'):
        duration_hours = template['duration_seconds'] / 3600
        duration_text = format_duration_from_hours(duration_hours)
        preview += f"⏱️ **Duration:** {duration_text}\n"
    if template.get('winners_count'):
        preview += f"👥 **Winners:** {template['winners_count']}\n"
    if template.get('winner_type'):
        winner_type_text = "Random" if template['winner_type'] == "random" else "First-X Participants"
        preview += f"🎯 **Winner Type:** {winner_type_text}\n"
    if template.get('required_channels'):
        preview += f"📢 **Required Channels:** {len(template['required_channels'])}\n"
    if template.get('image_file_id'):
        preview += f"🖼️ **Has Image:** Yes\n"

    try:
        await callback_query.edit_message_text(
            preview,
            reply_markup=build_template_actions_menu(template_id)
        )
    except:
        pass

    await callback_query.answer()

async def template_use_callback(client: Client, callback_query: CallbackQuery):
    template_id = callback_query.data.replace("usetemplate_", "")
    template = await get_template_by_id(template_id, callback_query.from_user.id)

    if not template:
        await callback_query.answer("Template not found!", show_alert=True)
        return

    from database.channels import list_channels
    channels = await list_channels(callback_query.from_user.id)

    if not channels:
        await callback_query.answer(
            "No channels available! Please add a channel first.",
            show_alert=True
        )
        return

    from menus.keyboards import build_channel_selection_inline

    # Calculate total steps based on missing data
    missing_steps = []
    if not template.get("image_file_id"):
        missing_steps.append("image")
    if not template.get("duration_seconds"):
        missing_steps.append("duration")
    if not template.get("winners_count"):
        missing_steps.append("winners")
    if not template.get("winner_type"):
        missing_steps.append("winner_type")
    if not template.get("required_channels") or len(template.get("required_channels", [])) == 0:
        missing_steps.append("channels")
    missing_steps.append("prize")  # Prize is always required

    total_steps = len(missing_steps) + 1  # +1 for channel selection

    await set_user_state(
        callback_query.from_user.id,
        "giveaway_channel_select",
        {
            "selected_channels": [],
            "from_template": True,
            "template_id": template_id,
            "template_data": template,
            "total_steps": total_steps
        }
    )

    await callback_query.message.delete()
    await callback_query.message.reply_text(
        f"🎁 **Creating Giveaway from Template**\n\n"
        f"📝 **Template:** {template['name']}\n\n"
        f"**Step 1/{total_steps}:** Select one or more channels for this giveaway.\n\n"
        "Tap to toggle selection, then confirm.",
        reply_markup=build_channel_selection_inline(channels, [])
    )

    await callback_query.answer()

async def template_delete_callback(client: Client, callback_query: CallbackQuery):
    template_id = callback_query.data.replace("deltemplate_", "")
    template = await get_template_by_id(template_id, callback_query.from_user.id)

    if not template:
        await callback_query.answer("Template not found!", show_alert=True)
        return

    success = await delete_template(template_id, callback_query.from_user.id)

    if success:
        await callback_query.message.delete()
        await callback_query.message.reply_text(
            f"✅ Template **{template['name']}** deleted successfully!",
            reply_markup=build_main_menu()
        )
    else:
        await callback_query.answer("Failed to delete template!", show_alert=True)

    await callback_query.answer()

async def template_back_callback(client: Client, callback_query: CallbackQuery):
    templates = await get_user_templates(callback_query.from_user.id)

    try:
        await callback_query.edit_message_text(
            f"📝 **Template Library**\n\n"
            f"You have **{len(templates)}** saved template(s).\n\n"
            "Tap a template to view or use it:",
            reply_markup=build_templates_list(templates)
        )
    except:
        pass

    await callback_query.answer()

async def save_as_template_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "giveaway_confirm":
        await callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    data = user_state.get("data", {})

    await set_user_state(
        callback_query.from_user.id,
        "template_save_name_input",
        {"giveaway_data": data}
    )

    await callback_query.message.reply_text(
        "📝 **Save as Template**\n\n"
        "Enter a name for this template:\n\n"
        "Example: 'Weekly Discord Nitro', 'Monthly Premium Keys', etc."
    )

    await callback_query.answer()

async def template_save_name_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if not user_state or user_state.get("state") != "template_save_name_input":
        return

    template_name = message.text.strip()

    if not template_name or len(template_name) < 3:
        await message.reply_text("❌ Template name must be at least 3 characters long.")
        return

    if len(template_name) > 50:
        await message.reply_text("❌ Template name must be less than 50 characters.")
        return

    data = user_state.get("data", {}).get("giveaway_data", {})

    duration_seconds = data.get("duration_seconds", 86400)

    template_id = await create_template(
        user_id=message.from_user.id,
        name=template_name,
        title=data.get("title"),
        description=data.get("description"),
        image_file_id=data.get("image_file_id"),
        duration_seconds=duration_seconds,
        winners_count=data.get("winner_count", 1),
        winner_type=data.get("winner_type"),
        required_channels=data.get("required_channels", [])
    )

    if template_id:
        await set_user_state(message.from_user.id, "giveaway_confirm", data)

        await message.reply_text(
            f"✅ **Template Saved!**\n\n"
            f"📝 **Name:** {template_name}\n\n"
            "You can now use this template to quickly create similar giveaways in the future!"
        )
    else:
        await message.reply_text("❌ Failed to save template. Please try again.")

async def template_create_handler(client: Client, message: Message):
    user_state = await get_user_state(message.from_user.id)

    if not user_state:
        return

    state = user_state.get("state")
    data = user_state.get("data", {})

    if message.text and message.text.lower() == "/cancel":
        await clear_user_state(message.from_user.id)
        await message.reply_text("❌ Template creation cancelled.", reply_markup=build_main_menu())
        return

    if state == "template_create_name":
        template_name = message.text.strip()

        if len(template_name) < 3:
            await message.reply_text("❌ Template name must be at least 3 characters long.")
            return

        if len(template_name) > 50:
            await message.reply_text("❌ Template name must be less than 50 characters.")
            return

        await update_user_state_data(message.from_user.id, {"template_name": template_name})
        await set_user_state(message.from_user.id, "template_create_title", {**data, "template_name": template_name})

        await message.reply_text(
            "**Step 2/8:** Enter the giveaway title.\n\n"
            "This will be used as the default title when you use this template."
        )

    elif state == "template_create_title":
        title = message.text.strip()

        if len(title) < 3:
            await message.reply_text("❌ Title must be at least 3 characters long.")
            return

        await update_user_state_data(message.from_user.id, {"title": title})
        await set_user_state(message.from_user.id, "template_create_description", {**data, "title": title})

        await message.reply_text("**Step 3/8:** Enter a short description.")

    elif state == "template_create_description":
        description = message.text.strip()

        if len(description) < 5:
            await message.reply_text("❌ Description must be at least 5 characters long.")
            return

        await update_user_state_data(message.from_user.id, {"description": description})
        await set_user_state(message.from_user.id, "template_create_image", {**data, "description": description})

        await message.reply_text(
            "**Step 4/8:** Send a giveaway image (Optional)\n\n"
            "🖼️ Upload an image for your giveaway post.\n\n"
            "Send /cancel to abort.",
            reply_markup=build_template_skip_button()
        )

    elif state == "template_create_image":
        if message.photo:
            image_file_id = message.photo.file_id
            await update_user_state_data(message.from_user.id, {"image_file_id": image_file_id})
            await set_user_state(message.from_user.id, "template_create_duration", {**data, "image_file_id": image_file_id})

            await message.reply_text(
                "✅ Image uploaded!\n\n"
                "**Step 5/8:** Enter giveaway duration (Optional)\n\n"
                "Format: 5m, 1h, 2d (m=minutes, h=hours, d=days)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )
        else:
            await message.reply_text("❌ Please send an image or skip this step.")

    elif state == "template_create_duration":
        duration_text = message.text.strip()

        try:
            duration_seconds = parse_duration_to_seconds(duration_text)

            await update_user_state_data(message.from_user.id, {"duration_seconds": duration_seconds})
            await set_user_state(message.from_user.id, "template_create_winners", {**data, "duration_seconds": duration_seconds})

            await message.reply_text(
                "**Step 6/8:** Enter the number of winners (Optional)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )
        except:
            await message.reply_text("❌ Invalid duration format. Use: 5m, 1h, 2d")

    elif state == "template_create_winners":
        winner_count_text = message.text.strip()

        try:
            winner_count = validate_positive_int(winner_count_text)

            await update_user_state_data(message.from_user.id, {"winner_count": winner_count})
            await set_user_state(message.from_user.id, "template_create_winner_type", {**data, "winner_count": winner_count})

            await message.reply_text(
                "**Step 7/8:** Choose winner selection type (Optional):",
                reply_markup=build_template_winner_type_menu()
            )
        except:
            await message.reply_text("❌ Please enter a valid number.")

    elif state == "template_create_winner_type":
        await message.reply_text("❌ Please use the buttons above to select winner type.")

    elif state == "template_create_channels":
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

        template_id = await create_template(
            user_id=message.from_user.id,
            name=data.get("template_name"),
            title=data.get("title"),
            description=data.get("description"),
            image_file_id=data.get("image_file_id"),
            duration_seconds=data.get("duration_seconds"),
            winners_count=data.get("winner_count"),
            winner_type=data.get("winner_type"),
            required_channels=required_channels
        )

        if template_id:
            await clear_user_state(message.from_user.id)
            await message.reply_text(
                f"✅ **Template Created Successfully!**\n\n"
                f"📝 **Name:** {data.get('template_name')}\n\n"
                "You can now use this template to quickly create giveaways!",
                reply_markup=build_main_menu()
            )
        else:
            await message.reply_text("❌ Failed to create template. Please try again.")

async def skip_template_step_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state:
        await callback_query.answer("Session expired.", show_alert=True)
        return

    state = user_state.get("state")
    data = user_state.get("data", {})

    if state not in ["template_create_image", "template_create_duration", "template_create_winners", "template_create_winner_type", "template_create_channels"]:
        await callback_query.answer("Invalid state.", show_alert=True)
        return

    if state == "template_create_image":
        await set_user_state(callback_query.from_user.id, "template_create_duration", data)
        try:
            await callback_query.edit_message_text(
                "**Step 5/8:** Enter giveaway duration (Optional)\n\n"
                "Format: 5m, 1h, 2d (m=minutes, h=hours, d=days)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )
        except:
            await callback_query.message.reply_text(
                "**Step 5/8:** Enter giveaway duration (Optional)\n\n"
                "Format: 5m, 1h, 2d (m=minutes, h=hours, d=days)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )

    elif state == "template_create_duration":
        await set_user_state(callback_query.from_user.id, "template_create_winners", data)
        try:
            await callback_query.edit_message_text(
                "**Step 6/8:** Enter the number of winners (Optional)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )
        except:
            await callback_query.message.reply_text(
                "**Step 6/8:** Enter the number of winners (Optional)\n\n"
                "Or skip to use default.",
                reply_markup=build_template_skip_button()
            )

    elif state == "template_create_winners":
        await set_user_state(callback_query.from_user.id, "template_create_winner_type", data)
        try:
            await callback_query.edit_message_text(
                "**Step 7/8:** Choose winner selection type (Optional):",
                reply_markup=build_template_winner_type_menu()
            )
        except:
            await callback_query.message.reply_text(
                "**Step 7/8:** Choose winner selection type (Optional):",
                reply_markup=build_template_winner_type_menu()
            )

    elif state == "template_create_winner_type":
        await set_user_state(callback_query.from_user.id, "template_create_channels", data)
        try:
            await callback_query.edit_message_text(
                "**Step 8/8:** Send one or more channel IDs or @usernames that participants must join (Optional)\n\n"
                "You can separate multiple channels with spaces or newlines.\n\n"
                "Or skip this step.",
                reply_markup=build_template_skip_button()
            )
        except:
            await callback_query.message.reply_text(
                "**Step 8/8:** Send one or more channel IDs or @usernames that participants must join (Optional)\n\n"
                "You can separate multiple channels with spaces or newlines.\n\n"
                "Or skip this step.",
                reply_markup=build_template_skip_button()
            )

    elif state == "template_create_channels":
        template_id = await create_template(
            user_id=callback_query.from_user.id,
            name=data.get("template_name"),
            title=data.get("title"),
            description=data.get("description"),
            image_file_id=data.get("image_file_id"),
            duration_seconds=data.get("duration_seconds"),
            winners_count=data.get("winner_count"),
            winner_type=data.get("winner_type"),
            required_channels=[]
        )

        if template_id:
            await clear_user_state(callback_query.from_user.id)
            try:
                await callback_query.message.delete()
            except:
                pass
            await callback_query.message.reply_text(
                f"✅ **Template Created Successfully!**\n\n"
                f"📝 **Name:** {data.get('template_name')}\n\n"
                "You can now use this template to quickly create giveaways!",
                reply_markup=build_main_menu()
            )
        else:
            await callback_query.message.reply_text(
                "❌ Failed to create template. Please try again."
            )

    await callback_query.answer()

async def template_winner_type_callback(client: Client, callback_query: CallbackQuery):
    user_state = await get_user_state(callback_query.from_user.id)

    if not user_state or user_state.get("state") != "template_create_winner_type":
        await callback_query.answer("Session expired.", show_alert=True)
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
    await set_user_state(callback_query.from_user.id, "template_create_channels", {**data, "winner_type": winner_type})

    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "**Step 8/8:** Send one or more channel IDs or @usernames that participants must join (Optional)\n\n"
        "You can separate multiple channels with spaces or newlines.\n\n"
        "Or skip this step.",
        reply_markup=build_template_skip_button()
    )
    await callback_query.answer()

async def back_to_main_callback(client: Client, callback_query: CallbackQuery):
    await clear_user_state(callback_query.from_user.id)
    await callback_query.message.delete()
    await callback_query.message.reply_text(
        "🏠 **Main Menu**",
        reply_markup=build_main_menu()
    )
    await callback_query.answer()

def register_template_handlers(app: Client):
    app.add_handler(MessageHandler(
        templates_menu_handler,
        filters.create(lambda _, __, m: m.text == "📝 Templates") & filters.private
    ), group=1)

    app.add_handler(MessageHandler(
        template_save_name_handler,
        user_state_filter(state_value="template_save_name_input") &
        filters.private & filters.text
    ), group=1)

    app.add_handler(MessageHandler(
        template_create_handler,
        user_state_filter(state_value=[
            "template_create_name",
            "template_create_title",
            "template_create_description",
            "template_create_image",
            "template_create_duration",
            "template_create_winners",
            "template_create_winner_type",
            "template_create_channels"
        ]) & filters.private
    ), group=1)

    app.add_handler(CallbackQueryHandler(
        view_templates_callback,
        filters.create(lambda _, __, q: q.data == "view_templates")
    ))

    app.add_handler(CallbackQueryHandler(
        create_template_callback,
        filters.create(lambda _, __, q: q.data == "create_template")
    ))

    app.add_handler(CallbackQueryHandler(
        template_view_callback,
        filters.create(lambda _, __, q: q.data.startswith("viewtemplate_"))
    ))

    app.add_handler(CallbackQueryHandler(
        template_use_callback,
        filters.create(lambda _, __, q: q.data.startswith("usetemplate_"))
    ))

    app.add_handler(CallbackQueryHandler(
        template_delete_callback,
        filters.create(lambda _, __, q: q.data.startswith("deltemplate_"))
    ))

    app.add_handler(CallbackQueryHandler(
        template_back_callback,
        filters.create(lambda _, __, q: q.data == "back_to_templates")
    ))

    app.add_handler(CallbackQueryHandler(
        save_as_template_callback,
        filters.create(lambda _, __, q: q.data == "save_as_template")
    ))

    app.add_handler(CallbackQueryHandler(
        skip_template_step_callback,
        filters.create(lambda _, __, q: q.data == "skip_template_step")
    ))

    async def is_template_winner_type(_, __, query):
        from database.user_state import get_user_state
        user_state = await get_user_state(query.from_user.id)
        if not user_state:
            return False
        state = user_state.get("state")
        return query.data.startswith("winner_") and state == "template_create_winner_type"

    app.add_handler(CallbackQueryHandler(
        template_winner_type_callback,
        filters.create(is_template_winner_type)
    ))

    app.add_handler(CallbackQueryHandler(
        back_to_main_callback,
        filters.create(lambda _, __, q: q.data == "back_to_main")
    ))
