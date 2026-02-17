"""
الترجمة - بدون أي إشارة لـ aria2
"""
from config import DEFAULT_LANG, SUPPORTED_LANGS

MESSAGES = {
    'ar': {
        'start': '👋 أهلاً بك *{name}*!\n\n🤖 بوت تحميل يوتيوب v3.0',
        'send_url': '🔗 أرسل رابط الفيديو:',
        'stats': '📊 إحصائياتك:\n✅ ناجحة: `{success}`\n❌ فاشلة: `{failed}`\n📥 إجمالي: `{total}`',
        'cancelled': '❌ تم الإلغاء',
    },
    'en': {
        'start': '👋 Welcome *{name}*!\n\n🤖 YouTube Downloader v3.0',
        'send_url': '🔗 Send video URL:',
        'stats': '📊 Your Stats:\n✅ Success: `{success}`\n❌ Failed: `{failed}`\n📥 Total: `{total}`',
        'cancelled': '❌ Cancelled',
    }
}

def get_text(lang_code: str, key: str, **kwargs) -> str:
    lang = lang_code if lang_code in SUPPORTED_LANGS else DEFAULT_LANG
    text = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG]).get(key, key)
    return text.format(**kwargs) if kwargs else text
