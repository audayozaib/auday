from config import DEFAULT_LANG, SUPPORTED_LANGS

MESSAGES = {
    'ar': {
        'start': '👋 أهلاً بك *{name}*!\n\n🤖 بوت تحميل يوتيوب المتقدم v3.0\n\n✨ المميزات:\n• تحميل الفيديوهات بجودة حتى 4K\n• استخراج الصوت بجودة 320kbps\n• دعم قوائم التشغيل\n• فيديوهات Shorts',
        'choose_format': '📥 اختر نوع التحميل:',
        'choose_quality': '📊 اختر جودة الفيديو:',
        'send_url': '🔗 أرسل رابط الفيديو من يوتيوب:',
        'downloading': '⏳ جاري التحميل...\n*{title}*\n\n{percent} | ⚡️ {speed} | ⏱ {eta}',
        'sending': '📤 جاري إرسال الملف...',
        'success': '✅ تم التحميل بنجاح',
        'cancelled': '❌ تم إلغاء التحميل',
        'error_copyright': '❌ الفيديو محمي بحقوق الطبع',
        'error_private': '🔒 الفيديو خاص',
        'error_unavailable': '📛 الفيديو غير متاح في منطقتك',
        'error_network': '🌐 مشكلة في الاتصال، جرب مرة أخرى',
        'error_large': '❌ حجم الملف كبير جداً (>2GB)',
        'error_duration': '❌ الفيديو طويل جداً ({duration} دقيقة)',
        'stats': '📊 *إحصائياتك:*\n✅ ناجحة: `{success}`\n❌ فاشلة: `{failed}`\n📥 الإجمالي: `{total}`',
        'cancel_button': '❌ إلغاء التحميل',
        'back': '🔙 رجوع',
    },
    'en': {
        'start': '👋 Welcome *{name}*!\n\n🤖 YouTube Downloader Bot v3.0\n\n✨ Features:\n• Download videos up to 4K\n• Extract audio at 320kbps\n• Playlist support\n• Shorts support',
        'choose_format': '📥 Choose download format:',
        'choose_quality': '📊 Choose video quality:',
        'send_url': '🔗 Send YouTube video URL:',
        'downloading': '⏳ Downloading...\n*{title}*\n\n{percent} | ⚡️ {speed} | ⏱ {eta}',
        'sending': '📤 Sending file...',
        'success': '✅ Download completed successfully',
        'cancelled': '❌ Download cancelled',
        'error_copyright': '❌ Video is copyright protected',
        'error_private': '🔒 Video is private',
        'error_unavailable': '📛 Video not available in your region',
        'error_network': '🌐 Network error, please try again',
        'error_large': '❌ File too large (>2GB)',
        'error_duration': '❌ Video too long ({duration} minutes)',
        'stats': '📊 *Your Stats:*\n✅ Success: `{success}`\n❌ Failed: `{failed}`\n📥 Total: `{total}`',
        'cancel_button': '❌ Cancel Download',
        'back': '🔙 Back',
    }
}

def get_text(lang_code: str, key: str, **kwargs) -> str:
    """الحصول على النص حسب لغة المستخدم"""
    lang = lang_code if lang_code in SUPPORTED_LANGS else DEFAULT_LANG
    text = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG]).get(key, key)
    return text.format(**kwargs) if kwargs else text
