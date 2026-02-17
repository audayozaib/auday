"""
ملف الإعدادات والثوابت
"""
import os
import tempfile
from pathlib import Path

# ==================== متغيرات البيئة ====================

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# ==================== الحدود والقيود ====================

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB - حد تيليجرام
MAX_PLAYLIST_ITEMS = 5  # عدد الفيديوهات من قائمة التشغيل
MAX_DURATION_MINUTES = 120  # الحد الأقصى للمدة بالدقائق
RATE_LIMIT_PER_MINUTE = 5  # عدد الطلبات المسموح بها في الدقيقة
MAX_CONCURRENT_DOWNLOADS = 3  # عدد التحميلات المتزامنة

# ==================== المسارات ====================

# المجلد المؤقت للتحميلات
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
