import os
import tempfile
from pathlib import Path
import urllib.parse

# ==================== متغيرات البيئة ====================

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

# معالجة MONGO_URI
raw_mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

# إضافة خيارات TLS إذا كانت Atlas ولا تحتوي على خيارات
if "mongodb+srv://" in raw_mongo_uri and "tls=" not in raw_mongo_uri:
    # إضافة معلمات TLS افتراضية
    separator = "&" if "?" in raw_mongo_uri else "?"
    MONGO_URI = f"{raw_mongo_uri}{separator}tls=true&retryWrites=true&w=majority"
else:
    MONGO_URI = raw_mongo_uri

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# ==================== الحدود والقيود ====================

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_PLAYLIST_ITEMS = 5
MAX_DURATION_MINUTES = 120
RATE_LIMIT_PER_MINUTE = 5
MAX_CONCURRENT_DOWNLOADS = 3

# ==================== المسارات ====================

TEMP_DIR = Path(tempfile.gettempdir()) / "yt_bot"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ==================== إعدادات اللغة ====================

DEFAULT_LANG = 'ar'
SUPPORTED_LANGS = ['ar', 'en']

# ==================== إعدادات yt-dlp ====================

YDL_DEFAULT_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
}
