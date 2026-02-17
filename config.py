"""
الإعدادات - بدون أي إشارة لـ aria2
"""
import os
import tempfile
from pathlib import Path

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
MAX_PLAYLIST_ITEMS = 5
MAX_DURATION_MINUTES = 120
RATE_LIMIT_PER_MINUTE = 5
MAX_CONCURRENT_DOWNLOADS = 3

TEMP_DIR = Path(tempfile.gettempdir()) / "yt_bot"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_LANG = 'ar'
SUPPORTED_LANGS = ['ar', 'en']
