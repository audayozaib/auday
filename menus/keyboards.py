from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def build_main_menu():
    keyboard = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("🗂 Manage Channels")],
        [KeyboardButton("🎁 Create Giveaway"), KeyboardButton("📊 Dashboard")],
        [KeyboardButton("📝 Templates"), KeyboardButton("❓ Help & Support")],
        [KeyboardButton("ℹ️ About")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_manage_channels_menu():
    keyboard = [
        [KeyboardButton("🔍 View All Channels"), KeyboardButton("❌ Remove Channel")],
        [KeyboardButton("🔙 Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_channel_selection_inline(channels: list, selected_ids: list = None):
    if selected_ids is None:
        selected_ids = []

    keyboard = []
    row = []

    for i, channel in enumerate(channels):
        channel_id = channel['channel_id']
        title = channel['title']
        is_selected = channel_id in selected_ids
        checkmark = "✅ " if is_selected else ""

        row.append(
            InlineKeyboardButton(
                f"{checkmark}{title}",
                callback_data=f"togglech_{channel_id}"
            )
        )

        # Add row when we have 2 buttons or reached the last channel
        if len(row) == 2 or i == len(channels) - 1:
            keyboard.append(row)
            row = []

    keyboard.append([
        InlineKeyboardButton("✅ Confirm Selection", callback_data="confirm_channels")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_channels")
    ])

    return InlineKeyboardMarkup(keyboard)

def build_winner_type_menu():
    keyboard = [
        [InlineKeyboardButton("🎲 Random", callback_data="winner_random")],
        [InlineKeyboardButton("🏃 First X Participants", callback_data="winner_first_x")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_template_winner_type_menu():
    keyboard = [
        [InlineKeyboardButton("🎲 Random", callback_data="winner_random")],
        [InlineKeyboardButton("🏃 First X Participants", callback_data="winner_first_x")],
        [InlineKeyboardButton("⏭️ Skip", callback_data="skip_template_step")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_skip_button():
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip", callback_data="skip_step")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_template_skip_button():
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip", callback_data="skip_template_step")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_confirm_cancel_buttons():
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_giveaway")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_giveaway")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_giveaway_inline_buttons(giveaway_id: str, bot_username: str):
    keyboard = [
        [
            InlineKeyboardButton("🎉 Join Giveaway", url=f"https://t.me/{bot_username}?start=join_{giveaway_id}")
        ],
        [
            InlineKeyboardButton("🔄 Reload Status", callback_data=f"reload_{giveaway_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_dashboard_menu():
    keyboard = [
        [KeyboardButton("🟢 Active Giveaways")],
        [KeyboardButton("⚫️ Expired Giveaways")],
        [KeyboardButton("📈 Analytics")],
        [KeyboardButton("🔙 Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_templates_list(templates: list):
    keyboard = []
    for template in templates:
        keyboard.append([
            InlineKeyboardButton(
                f"📝 {template['name']}",
                callback_data=f"viewtemplate_{template['id']}"
            )
        ])
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(keyboard)

def build_template_actions_menu(template_id: str):
    keyboard = [
        [InlineKeyboardButton("✅ Use Template", callback_data=f"usetemplate_{template_id}")],
        [InlineKeyboardButton("🗑️ Delete Template", callback_data=f"deltemplate_{template_id}")],
        [InlineKeyboardButton("🔙 Back to Templates", callback_data="back_to_templates")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_back_button():
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_templates")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_template_menu():
    keyboard = [
        [InlineKeyboardButton("📋 View Templates", callback_data="view_templates")],
        [InlineKeyboardButton("➕ Create Template", callback_data="create_template")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
