import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("DB_NAME", "giveaway")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "778375826"))

if not BOT_TOKEN or not API_ID or not API_HASH:
    raise ValueError("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")
