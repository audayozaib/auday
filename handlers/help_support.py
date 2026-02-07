from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler
from menus.keyboards import build_main_menu

async def help_support_handler(client: Client, message: Message):
    help_text = """
🚀 **Quick Guide**
━━━━━━━━━━━━━━━━━
1️⃣ **Add Channel**
• Click ➕ Add Channel
• Send channel ID or @username
• Bot must be admin (Post/Edit/Delete)

2️⃣ **Create Giveaway**
• Click 🎁 Create Giveaway
• Follow steps (title, time, winners, prize)

3️⃣ **Monitor**
• 📊 Dashboard → active & ended giveaways

📋 **Tips**
• Time: 5m | 1h | 2d
• Single prize = one line
• Multiple prizes = one per line
• Subscriptions are optional

🔧 **Common Issues**
• Channel not linked → bot/user not admin
• Missing permissions → allow Post/Edit/Delete
• Channel not found → check ID/username

📞 **Support:** @iSmartDev
"""

    inline_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Update Channel", url="https://t.me/itsSmartDev")]
    ])

    await message.reply_text(help_text, reply_markup=inline_keyboard)

async def about_handler(client: Client, message: Message):
    about_text = """
ℹ️ **About**
━━━━━━━━━━━━━━━━━
**Name:** Give Mint
**Version:** v2.0 (Beta) 🛠

**Development Team:**
- Creator: [Bisnu Ray 👨‍💻](https://t.me/TheSmartBisnu)

**Technical Stack:**
- Language: Python 🐍
- Libraries: Pyrogram 📚
- Database: MongoDB 🗄

**About:** Automated giveaway management for Telegram channels.
"""

    await message.reply_text(about_text, disable_web_page_preview=True)

def register_help_handlers(app: Client):
    app.add_handler(MessageHandler(
        help_support_handler,
        filters.create(lambda _, __, m: m.text == "❓ Help & Support") & filters.private
    ))
    app.add_handler(MessageHandler(
        about_handler,
        filters.create(lambda _, __, m: m.text == "ℹ️ About") & filters.private
    ))
