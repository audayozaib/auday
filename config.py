import os
from pathlib import Path

# البيئة
TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# الحدود والثوابت
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_PLAYLIST_ITEMS = 5
MAX_DURATION_MINUTES = 120
RATE_LIMIT_PER_MINUTE = 5
MAX_CONCURRENT_DOWNLOADS = 3

# المسارات
TEMP_DIR = Path(tempfile.gettempdir()) / "yt_bot"
TEMP_DIR.mkdir(exist_ok=True)

# اللغات المدعومة
DEFAULT_LANG = 'ar'
SUPPORTED_LANGS = ['ar', 'en']
