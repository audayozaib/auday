<h1 align="center">🎁 Give Mint Bot</h1>

<p align="center">
  <a href="https://github.com/bisnuray/givemint/stargazers">
    <img src="https://img.shields.io/github/stars/bisnuray/givemint?color=blue&style=flat" alt="GitHub Repo stars">
  </a>
  <a href="https://github.com/bisnuray/givemint/issues">
    <img src="https://img.shields.io/github/issues/bisnuray/givemint?style=flat" alt="GitHub issues">
  </a>
  <a href="https://github.com/bisnuray/givemint/pulls">
    <img src="https://img.shields.io/github/issues-pr/bisnuray/givemint?style=flat" alt="GitHub pull requests">
  </a>
  <a href="https://github.com/bisnuray/givemint/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/bisnuray/givemint?style=flat" alt="GitHub contributors">
  </a>
  <a href="https://github.com/bisnuray/givemint/network/members">
    <img src="https://img.shields.io/github/forks/bisnuray/givemint?style=flat" alt="GitHub forks">
  </a>
</p>

<p align="center">
  <em>
GiveMintBot: An advanced Telegram bot for creating, managing, and automating giveaways in Telegram channels. It supports multi-admin channel management, giveaway templates, automatic deadline handling, smart winner selection, and secure prize delivery via private messages.
  </em>
</p>

<hr>

## ✨ Features

- ➕ **Add & Manage Channels** - Link multiple channels with admin verification
- 🎁 **Create Giveaways** - Step-by-step wizard for easy setup
- 🏆 **Winner Selection** - Random or First-X participant selection
- 🎯 **Required Subscriptions** - Ensure participants join specific channels
- 📊 **Dashboard & Analytics** - Track active/expired giveaways and stats
- ⏰ **Automatic Deadline** - Background task checks and ends giveaways
- 💬 **Prize Distribution** - Automatic DM to winners with their prizes
- 📄 **Giveaway Templates** – Save pre-configured giveaway settings to create new giveaways faster

## 📋 Requirements

- Python 3.11+
- MongoDB (running locally or MongoDB Atlas)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Telegram API credentials (from [my.telegram.org](https://my.telegram.org))

## 🚀 Installation

1. **Clone or download this project**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Setup environment variables:**

Open `.env` and edit with your values:

```env
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id_here
API_HASH=your_api_hash_here
MONGODB_URI=mongodb://localhost:27017/
DB_NAME=giveaway
BOT_OWNER_ID=your_telegram_user_id
```

**How to get these values:**
- `BOT_TOKEN`: Message [@BotFather](https://t.me/botfather) on Telegram
- `API_ID` & `API_HASH`: Get from [my.telegram.org/apps](https://my.telegram.org/apps)
- `BOT_OWNER_ID`: Message [@userinfobot](https://t.me/username_to_id_bot) to get your user ID

4. **Run the bot:**
```bash
python main.py
```

## 📖 Usage

### Add a Channel

1. Click **➕ Add Channel**
2. Send the channel ID or @username
3. The bot verifies admin permissions
4. Channel is linked and ready for giveaways

### Create a Giveaway

1. Click **🎁 Create Giveaway**
2. Follow the wizard:
   - Select channel
   - Enter title
   - Enter description
   - Set duration (e.g., 5m, 1h, 2d)
   - Set winner count
   - Choose winner type (Random / First X)
   - Send prize(s)
   - Add required subscriptions (optional)
   - Confirm and publish

### Prize Format

**Single Prize (same for all winners):**
```
THM-PREMIUM-KEY-9A3X7B2
```

**Multiple Prizes (one per winner):**
```
johndoe:12345
janedoe:pass4321
THM-PREM-KEY-9Q2W
KEY-AAA1-BBB2-CCC3
```

Supported formats:
- `username:password`
- `email@example.com:password`
- `REDEEM-CODE-12345`
- `KEY-XXXX-YYYY-ZZZZ`
- `https://www.canva.com/join/abc-def-ghi` [ Link Suported ]

> **One prize per line.** Each line is treated as a separate prize. 

### Dashboard

Click **📊 Dashboard** to:
- View active giveaways
- View expired giveaways
- Check analytics (participants, winners, etc.)

## 🔐 Important Notes

- The bot must be an **admin** in every channel where giveaways are hosted
- The bot must be an admin in all channels used for forced subscriptions.
- Required permissions: **Post messages**, **Edit messages**, **Delete messages**
- Prizes are sent via private DM to winners only
- The bot verifies that users are channel admins before allowing them to add channels

## 🛠 Troubleshooting

**"Failed to link channel"**
- Ensure the bot is an admin in the channel
- Check that the channel ID/username is correct
- Verify you are an admin in the channel

**"Missing permissions"**
- Grant the bot: Post, Edit, Delete messages permissions

**"Giveaway not posting"**
- Verify bot is still an admin with proper permissions

## Author

- Name: Bisnu Ray
- Telegram: [@itsSmartDev](https://t.me/itsSmartDev)

> Feel free to reach out if you have any questions or feedback.
