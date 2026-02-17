"""
بوت تحميل يوتيوب - الإصدار النهائي
"""
import os
import asyncio
import logging
import uuid
from io import BytesIO
from datetime import datetime

import aiohttp
import aiofiles
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    BotCommand, InputFile
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters, AIORateLimiter
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import RetryAfter, BadRequest

from config import TOKEN, WEBHOOK_URL, PORT, ADMIN_ID
from database import db
from downloader import dl_manager
from validators import validate_youtube_url
from exceptions import DownloadError, CancelledError, FileTooLargeError
from i18n import get_text
from utils import cleanup_file, safe_edit_message, format_duration

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
CHOOSING_FORMAT, CHOOSING_QUALITY, WAITING_URL, DOWNLOADING, ADMIN_MENU = range(5)

# Active downloads for cancellation
active_downloads = {}


async def post_init(app: Application):
    """تهيئة البوت"""
    try:
        await db.init_indexes()
        logger.info("✅ Bot initialized successfully")
    except Exception as e:
        logger.error(f"⚠️ Database init warning: {e}")
        # استمر حتى لو فشلت قاعدة البيانات


def get_user_lang(update: Update) -> str:
    """الحصول على لغة المستخدم"""
    lang = update.effective_user.language_code
    return lang if lang in ['ar', 'en'] else 'ar'


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت"""
    user = update.effective_user
    lang = get_user_lang(update)
    
    # التحقق من الحظر
    try:
        if await db.is_banned(user.id):
            await update.message.reply_text("⛔️ You are banned.")
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ban check error: {e}")
    
    # تحديث معلومات المستخدم
    try:
        await db.update_user(
            user.id, 
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
    except Exception as e:
        logger.error(f"User update error: {e}")
    
    keyboard = [
        [InlineKeyboardButton("🎵 " + "Audio MP3", callback_data="fmt_audio"),
         InlineKeyboardButton("🎬 " + "Video MP4", callback_data="fmt_video")],
        [InlineKeyboardButton("📊 " + "My Stats", callback_data="my_stats")]
    ]
    
    if await db.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
    
    await update.message.reply_text(
        get_text(lang, 'start', name=user.first_name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_FORMAT


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    lang = get_user_lang(update)
    
    if data.startswith("fmt_"):
        format_type = data.replace("fmt_", "")
        context.user_data["format"] = format_type
        
        if format_type == "video":
            keyboard = [
                [InlineKeyboardButton("🥇 Best Quality", callback_data="q_best")],
                [InlineKeyboardButton("🎬 1080p", callback_data="q_1080"),
                 InlineKeyboardButton("📺 720p", callback_data="q_720")],
                [InlineKeyboardButton("📱 480p", callback_data="q_480")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
            ]
            await safe_edit_message(
                query, "📊 Choose video quality:",
                InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING_QUALITY
        else:
            await safe_edit_message(
                query,
                get_text(lang, 'send_url'),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
            )
            return WAITING_URL
    
    elif data.startswith("q_"):
        quality = data.replace("q_", "")
        context.user_data["quality"] = quality
        await safe_edit_message(
            query,
            get_text(lang, 'send_url'),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
        )
        return WAITING_URL
    
    elif data == "my_stats":
        try:
            stats = await db.get_user_stats(user_id)
            success_rate = round((stats['successful']/stats['total']*100), 1) if stats['total'] > 0 else 0
            
            text = get_text(
                lang, 'stats',
                success=stats['successful'],
                failed=stats['failed'],
                total=stats['total']
            ) + f"\n🎯 {success_rate}%"
        except Exception as e:
            logger.error(f"Stats error: {e}")
            text = "❌ Error loading stats"
        
        await safe_edit_message(
            query, text,
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
        )
        return CHOOSING_FORMAT
    
    elif data == "back_start":
        return await start(update, context)
    
    elif data.startswith("cancel_dl:"):
        download_id = data.split(":")[1]
        if download_id in active_downloads:
            active_downloads[download_id].set()
            await query.edit_message_text(get_text(lang, 'cancelled'))
        return ConversationHandler.END
    
    return ConversationHandler.END


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرابط"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    lang = get_user_lang(update)
    
    # التحقق من Rate Limit
    try:
        if not await db.check_rate_limit(user_id):
            await update.message.reply_text("⏳ Rate limit exceeded. Please wait.")
            return WAITING_URL
    except Exception as e:
        logger.error(f"Rate limit check error: {e}")
    
    # التحقق من الرابط
    if not validate_youtube_url(url):
        await update.message.reply_text("❌ Invalid YouTube URL")
        return WAITING_URL
    
    format_type = context.user_data.get("format", "video")
    quality = context.user_data.get("quality", "best")
    
    # إنشاء معرف للإلغاء
    download_id = str(uuid.uuid4())[:8]
    cancel_event = asyncio.Event()
    active_downloads[download_id] = cancel_event
    
    # رسالة مع زر إلغاء
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_dl:{download_id}")]]
    processing_msg = await update.message.reply_text(
        "⏳ Preparing download...",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    try:
        # استخراج المعلومات
        info = await dl_manager.extract_info(url)
        if not info:
            await processing_msg.edit_text("❌ Failed to get video info")
            return ConversationHandler.END
        
        # التحقق من المدة
        duration_min = info.get('duration', 0) / 60
        if duration_min > 120:
            await processing_msg.edit_text(f"❌ Video too long ({int(duration_min)} min). Max: 120 min.")
            return ConversationHandler.END
        
        title = info.get('title', 'Unknown')
        
        # دالة تحديث التقدم
        last_update = [0]
        async def progress(percent, speed, eta):
            current = int(percent.replace('%', '').strip() or 0)
            if current - last_update[0] >= 10:
                last_update[0] = current
                try:
                    await processing_msg.edit_text(
                        f"⏳ Downloading: {title}\n{percent} | {speed} | {eta}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except:
                    pass
        
        # التحميل
        result = await dl_manager.download(
            url, format_type, quality,
            cancel_event=cancel_event,
            progress_callback=progress
        )
        
        if cancel_event.is_set():
            await processing_msg.delete()
            return ConversationHandler.END
        
        # إرسال الملف
        await processing_msg.edit_text("📤 Sending file...")
        
        if result.get("is_playlist"):
            # قائمة التشغيل
            for i, file_path in enumerate(result["files"], 1):
                if cancel_event.is_set():
                    break
                
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()
                
                if format_type == "audio":
                    await update.message.reply_audio(BytesIO(data), caption=f"🎵 {i}/{result['count']}")
                else:
                    await update.message.reply_video(BytesIO(data), supports_streaming=True)
                
                await cleanup_file(file_path)
                await asyncio.sleep(1)
            
            await db.log_download(user_id, url, "success_playlist", {"count": len(result["files"])})
        else:
            # ملف واحد
            file_path = result["file_path"]
            
            # إرسال الصورة المصغرة للصوت
            if result.get('thumbnail') and format_type == "audio":
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(result['thumbnail']) as resp:
                            if resp.status == 200:
                                await update.message.reply_photo(await resp.read())
                except:
                    pass
            
            # إرسال الملف
            async with aiofiles.open(file_path, 'rb') as f:
                file_data = await f.read()
            
            file_obj = BytesIO(file_data)
            file_obj.name = os.path.basename(file_path)
            
            if format_type == "audio":
                await update.message.reply_audio(
                    InputFile(file_obj),
                    title=result["title"],
                    performer=result.get("uploader", "YouTube"),
                    duration=result.get("duration"),
                    caption="✅ Downloaded successfully"
                )
            else:
                await update.message.reply_video(
                    InputFile(file_obj),
                    supports_streaming=True,
                    caption=f"🎬 {result['title']}\n✅ Downloaded successfully"
                )
            
            await db.log_download(
                user_id, url, "success",
                {"title": result["title"], "size": result["file_size"], "format": format_type}
            )
            
            await cleanup_file(file_path)
        
        await processing_msg.delete()
        
    except CancelledError:
        await processing_msg.edit_text("❌ Cancelled")
    except FileTooLargeError:
        await processing_msg.edit_text("❌ File too large (>2GB)")
        await db.log_download(user_id, url, "failed", error="File too large")
    except DownloadError as e:
        error_msg = {
            "copyright": "❌ Copyright protected",
            "private": "🔒 Private video",
            "unavailable": "📛 Not available in your region",
            "network": "🌐 Network error"
        }.get(e.error_type, f"❌ Error: {e.message}")
        await processing_msg.edit_text(error_msg)
        await db.log_download(user_id, url, "failed", error=e.message)
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        await processing_msg.edit_text("❌ Unexpected error occurred")
        await db.log_download(user_id, url, "error", error=str(e))
    finally:
        active_downloads.pop(download_id, None)
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text("❌ Cancelled. Use /start to restart.")
    return ConversationHandler.END


def main():
    if not TOKEN:
        logger.error("No BOT_TOKEN provided!")
        return
    
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .rate_limiter(AIORateLimiter(max_retries=3))
        .build()
    )
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(button_handler, pattern="^(fmt_|my_stats|admin_panel|back_start)")
            ],
            CHOOSING_QUALITY: [
                CallbackQueryHandler(button_handler, pattern="^q_"),
                CallbackQueryHandler(button_handler, pattern="^back_start")
            ],
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
                CallbackQueryHandler(button_handler, pattern="^cancel_dl:")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        per_chat=True,
        per_user=True
    )
    
    application.add_handler(conv_handler)
    
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception: {context.error}", exc_info=True)
    
    application.add_error_handler(error_handler)
    
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES, 
            drop_pending_updates=True
        )


if __name__ == "__main__":
    main()
