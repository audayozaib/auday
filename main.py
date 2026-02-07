import asyncio
from pyrogram import Client, idle
from config import BOT_TOKEN, API_ID, API_HASH
from database.connection import init_db
from handlers import register_handlers
from services.deadline_checker import start_deadline_checker

async def main():
    await init_db()

    app = Client(
        "giveaway_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    register_handlers(app)

    await app.start()
    print("✅ Bot started successfully!")

    asyncio.create_task(start_deadline_checker(app))

    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
