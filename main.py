import os
import asyncio
import logging
import uuid
from io import BytesIO
from datetime import datetime
from telegram import InputFile  # <-- تأكد من وجوده
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
from validators import validate_youtube_url, extract_video_id
from exceptions import DownloadError, ValidationError, CancelledError, FileTooLargeError
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
    await db.init_indexes()
    logger.info("Bot initialized")

def get_user_lang(update: Update) -> str:
    """الحصول على لغة المستخدم"""
    lang = update.effective_user.language_code
    return lang if lang in ['ar', 'en'] else 'ar'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت"""
    user = update.effective_user
    lang = get_user_lang(update)
    
    # التحقق من الحظر
    if await db.is_banned(user.id):
        await update.message.reply_text("⛔️ You are banned.")
        return ConversationHandler.END
    
    await db.update_user(
        user.id, 
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    keyboard = [
        [InlineKeyboardButton("🎵 " + get_text(lang, 'audio'), callback_data="fmt_audio"),
         InlineKeyboardButton("🎬 " + get_text(lang, 'video'), callback_data="fmt_video")],
        [InlineKeyboardButton("📊 " + get_text(lang, 'stats'), callback_data="my_stats")]
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
                [InlineKeyboardButton(get_text(lang, 'back'), callback_data="back_start")]
            ]
            await safe_edit_message(
                query, get_text(lang, 'choose_quality'),
                InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING_QUALITY
        else:
            await safe_edit_message(
                query,
                get_text(lang, 'send_url'),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'back'), callback_data="back_start")]])
            )
            return WAITING_URL
    
    elif data.startswith("q_"):
        quality = data.replace("q_", "")
        context.user_data["quality"] = quality
        await safe_edit_message(
            query,
            get_text(lang, 'send_url'),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'back'), callback_data="back_start")]])
        )
        return WAITING_URL
    
    elif data == "my_stats":
        stats = await db.get_user_stats(user_id)
        success_rate = round((stats['successful']/stats['total']*100), 1) if stats['total'] > 0 else 0
        
        text = get_text(
            lang, 'stats',
            success=stats['successful'],
            failed=stats['failed'],
            total=stats['total']
        ) + f"\n🎯 {success_rate}%"
        
        await safe_edit_message(
            query, text,
            InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'back'), callback_data="back_start")]])
        )
        return CHOOSING_FORMAT
    
    elif data == "back_start":
        return await start(update, context)
    
    elif data.startswith("cancel_dl:"):
        # إلغاء التحميل
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
    if not await db.check_rate_limit(user_id):
        await update.message.reply_text("⏳ Rate limit exceeded. Please wait.")
        return WAITING_URL
    
    # التحقق من الرابط
    if not validate_youtube_url(url):
        await update.message.reply_text("❌ Invalid URL")
        return WAITING_URL
    
    format_type = context.user_data.get("format", "video")
    quality = context.user_data.get("quality", "best")
    
    # إنشاء معرف للإلغاء
    download_id = str(uuid.uuid4())[:8]
    cancel_event = asyncio.Event()
    active_downloads[download_id] = cancel_event
    
    # رسالة مع زر إلغاء
    keyboard = [[InlineKeyboardButton(get_text(lang, 'cancel_button'), callback_data=f"cancel_dl:{download_id}")]]
    processing_msg = await update.message.reply_text(
        "⏳ " + get_text(lang, 'downloading', title="Preparing...", percent="0%", speed="N/A", eta="N/A"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # استخراج المعلومات أولاً
        info = await dl_manager.extract_info(url)
        if not info:
            await processing_msg.edit_text("❌ Failed to get video info")
            return ConversationHandler.END
        
        # التحقق من المدة
        duration_min = info.get('duration', 0) / 60
        if duration_min > 120:
            await processing_msg.edit_text(get_text(lang, 'error_duration', duration=int(duration_min)))
            return ConversationHandler.END
        
        title = info.get('title', 'Unknown')
        
        # دالة تحديث التقدم
        last_update = [0]
        async def progress(percent, speed, eta):
            if int(percent.replace('%', '')) - last_update[0] >= 10:
                last_update[0] = int(percent.replace('%', ''))
                try:
                    await processing_msg.edit_text(
                        get_text(lang, 'downloading', title=title, percent=percent, speed=speed, eta=eta),
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.MARKDOWN
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
        await processing_msg.edit_text(get_text(lang, 'sending'))
        
        if result.get("is_playlist"):
            # معالجة قائمة التشغيل
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
            
            # إرسال الصورة المصغرة أولاً
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
                    caption=get_text(lang, 'success')
                )
            else:
                await update.message.reply_video(
                    InputFile(file_obj),
                    supports_streaming=True,
                    caption=get_text(lang, 'success')
                )
            
            await db.log_download(
                user_id, url, "success",
                {"title": result["title"], "size": result["file_size"], "format": format_type}
            )
            
            await cleanup_file(file_path)
        
        await processing_msg.delete()
        
    except CancelledError:
        await processing_msg.edit_text(get_text(lang, 'cancelled'))
    except FileTooLargeError:
        await processing_msg.edit_text(get_text(lang, 'error_large'))
        await db.log_download(user_id, url, "failed", error="File too large")
    except DownloadError as e:
        error_key = f"error_{e.error_type}"
        await processing_msg.edit_text(get_text(lang, error_key, default=e.message))
        await db.log_download(user_id, url, "failed", error=e.message)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await processing_msg.edit_text("❌ Error occurred")
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
        logger.error("No token provided!")
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
        per_message=True
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(lambda u, c: logger.error(f"Error: {c.error}", exc_info=True))
    
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
