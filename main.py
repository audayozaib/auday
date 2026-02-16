import os
import asyncio
import logging
import yt_dlp
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
import aiohttp
from io import BytesIO

# إعدادات Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== إعدادات قاعدة البيانات ====================

class Database:
    def __init__(self, uri: str = "mongodb+srv://audayozaib:SaXaXket2GECpLvR@giveaway.x2eabrg.mongodb.net/giveaway?retryWrites=true&w=majority"):
        self.client = MongoClient(uri)
        self.db = self.client["youtube_bot_db"]
        
        # Collections
        self.users = self.db["users"]
        self.downloads = self.db["downloads"]
        self.cookies = self.db["cookies"]
        self.settings = self.db["settings"]
        
        # إنشاء الفهارس
        self.users.create_index("user_id", unique=True)
        self.downloads.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
        self.cookies.create_index("name", unique=True)
        
        # إعدادات افتراضية
        self._init_default_settings()
    
    def _init_default_settings(self):
        default_admin = {
            "key": "admin_ids",
            "value": [778375826]  # أضف معرفات المشرفين هنا
        }
        if not self.settings.find_one({"key": "admin_ids"}):
            self.settings.insert_one(default_admin)
    
    def is_admin(self, user_id: int) -> bool:
        admin_config = self.settings.find_one({"key": "admin_ids"})
        return user_id in admin_config.get("value", []) if admin_config else False
    
    def add_admin(self, user_id: int):
        self.settings.update_one(
            {"key": "admin_ids"},
            {"$addToSet": {"value": user_id}},
            upsert=True
        )
    
    def save_cookies(self, name: str, content: str, uploaded_by: int):
        self.cookies.update_one(
            {"name": name},
            {"$set": {
                "content": content,
                "uploaded_by": uploaded_by,
                "updated_at": datetime.now(),
                "active": True
            }},
            upsert=True
        )
    
    def get_active_cookies(self) -> Optional[str]:
        cookie = self.cookies.find_one({"active": True}, sort=[("updated_at", -1)])
        return cookie["content"] if cookie else None
    
    def log_download(self, user_id: int, url: str, status: str, file_path: Optional[str] = None, error: Optional[str] = None):
        self.downloads.insert_one({
            "user_id": user_id,
            "url": url,
            "status": status,
            "file_path": file_path,
            "error": error,
            "created_at": datetime.now()
        })
    
    def get_user_stats(self, user_id: int):
        total = self.downloads.count_documents({"user_id": user_id})
        successful = self.downloads.count_documents({"user_id": user_id, "status": "success"})
        return {"total": total, "successful": successful}

db = Database()

# ==================== إعدادات yt-dlp ====================

class YouTubeDownloader:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
    
    def get_ydl_opts(self, format_type: str, quality: str = "best") -> dict:
        cookies_content = db.get_active_cookies()
        cookies_path = None
        
        if cookies_content:
            cookies_path = os.path.join(self.download_path, "cookies.txt")
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_content)
        
        opts = {
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'cookiefile': cookies_path if cookies_path else None,
            'quiet': True,
            'no_warnings': True,
        }
        
        if format_type == "audio":
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        elif format_type == "video":
            if quality == "best":
                opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]'
        elif format_type == "playlist_audio":
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
                'playliststart': 1,
                'playlistend': 10,  # تحميل أول 10 فقط لتجنب الحظر
            })
        elif format_type == "playlist_video":
            opts['format'] = 'best[ext=mp4]'
            opts['playlistend'] = 5  # تحميل أول 5 فيديوهات
        
        return opts
    
    async def download(self, url: str, format_type: str, quality: str = "best") -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        
        def _download():
            try:
                opts = self.get_ydl_opts(format_type, quality)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if 'entries' in info:  # Playlist
                        files = []
                        for entry in info['entries'][:5]:  # أول 5 فقط
                            filename = ydl.prepare_filename(entry)
                            if format_type.startswith("playlist_audio"):
                                filename = filename.replace(".webm", ".mp3").replace(".m4a", ".mp3")
                            if os.path.exists(filename):
                                files.append(filename)
                        return {"success": True, "files": files, "is_playlist": True, "title": info.get("title", "Playlist")}
                    else:
                        filename = ydl.prepare_filename(info)
                        if format_type == "audio":
                            filename = filename.replace(".webm", ".mp3").replace(".m4a", ".mp3")
                        return {"success": True, "file_path": filename, "title": info.get("title", "Unknown"), "is_playlist": False}
                        
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return await loop.run_in_executor(None, _download)
    
    def cleanup(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up {file_path}: {e}")

downloader = YouTubeDownloader()

# ==================== حالات المحادثة ====================
(
    WAITING_FOR_URL,
    WAITING_FOR_QUALITY,
    WAITING_FOR_COOKIES,
    ADMIN_PANEL
) = range(4)

# ==================== الأوامر الأساسية ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # تسجيل المستخدم
    db.users.update_one(
        {"user_id": user.id},
        {"$set": {
            "username": user.username,
            "first_name": user.first_name,
            "last_visit": datetime.now()
        }},
        upsert=True
    )
    
    keyboard = [
        [InlineKeyboardButton("🎵 تحميل صوت", callback_data="format_audio"),
         InlineKeyboardButton("🎬 تحميل فيديو", callback_data="format_video")],
        [InlineKeyboardButton("📋 قائمة تشغيل", callback_data="format_playlist")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
         InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")]
    ]
    
    if db.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔐 لوحة التحكم", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}!\n\n"
        "🤖 بوت تحميل يوتيوب المتقدم\n"
        "• تحميل الفيديوهات بجودة عالية\n"
        "• تحميل الصوت بصيغة MP3\n"
        "• دعم قوائم التشغيل\n\n"
        "اختر نوع التحميل:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *أوامر البوت:*

/start - بدء البوت
/help - عرض المساعدة
/stats - إحصائيات التحميل (للمشرفين)

*طريقة الاستخدام:*
1. أرسل رابط الفيديو من يوتيوب
2. اختر نوع التحميل (صوت/فيديو)
3. انتظر اكتمال التحميل

*ملاحظات:*
- يدعم روابط الفيديوهات الفردية وقوائم التشغيل
- يمكن تحميل فيديوهات حتى 2GB
- للمحتوى المحدود، يحتاج المشرف لتحديث الكوكيز
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ==================== معالج الأزرار ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("format_"):
        format_type = data.replace("format_", "")
        context.user_data["format"] = format_type
        
        if format_type in ["video", "playlist_video"]:
            keyboard = [
                [InlineKeyboardButton("🥇 4K (أفضل جودة)", callback_data="quality_best"),
                 InlineKeyboardButton("📺 1080p", callback_data="quality_1080")],
                [InlineKeyboardButton("📱 720p", callback_data="quality_720"),
                 InlineKeyboardButton("📱 480p", callback_data="quality_480")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
            ]
            await query.edit_message_text(
                "📊 اختر جودة الفيديو:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                "📝 أرسل الآن رابط الفيديو من يوتيوب:\n\n"
                "يمكنك إرسال روابط:\n"
                "• فيديو واحد\n"
                "• قائمة تشغيل (Playlist)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]])
            )
            return WAITING_FOR_URL
    
    elif data.startswith("quality_"):
        quality = data.replace("quality_", "")
        context.user_data["quality"] = quality
        await query.edit_message_text(
            "📝 أرسل الآن رابط الفيديو من يوتيوب:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]])
        )
        return WAITING_FOR_URL
    
    elif data == "back_to_main":
        await start(update, context)
        return ConversationHandler.END
    
    elif data == "my_stats":
        stats = db.get_user_stats(update.effective_user.id)
        await query.edit_message_text(
            f"📊 *إحصائياتك:*\n\n"
            f"✅ عمليات ناجحة: {stats['successful']}\n"
            f"📥 إجمالي المحاولات: {stats['total']}\n"
            f"🎯 نسبة النجاح: {round((stats['successful']/stats['total']*100) if stats['total'] > 0 else 0, 1)}%",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]])
        )
    
    elif data == "admin_panel" and db.is_admin(update.effective_user.id):
        await show_admin_panel(update, context)
        return ADMIN_PANEL

# ==================== معالجة الروابط ====================

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # التحقق من الرابط
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("❌ الرابط غير صحيح! يرجى إرسال رابط يوتيوب صالح.")
        return WAITING_FOR_URL
    
    format_type = context.user_data.get("format", "video")
    quality = context.user_data.get("quality", "best")
    
    # إرسال رسالة المعالجة
    processing_msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")
    
    try:
        # التحميل
        result = await downloader.download(url, format_type, quality)
        
        if not result["success"]:
            error_msg = result["error"]
            if "Sign in to confirm" in error_msg or "age-restricted" in error_msg:
                await processing_msg.edit_text(
                    "⚠️ هذا الفيديو محمي أو محدود العمر!\n"
                    "سيتم المحاولة باستخدام الكوكيز..."
                )
                # إعادة المحاولة (yt-dlp سيستخدم الكوكيز تلقائياً إذا موجودة)
                result = await downloader.download(url, format_type, quality)
                
                if not result["success"]:
                    await processing_msg.edit_text(
                        f"❌ فشل التحميل: {error_msg}\n\n"
                        f"يرجى إبلاغ المشرف لتحديث الكوكيز."
                    )
                    db.log_download(user_id, url, "failed_cookies", error=error_msg)
                    return ConversationHandler.END
            
            if not result["success"]:
                await processing_msg.edit_text(f"❌ خطأ: {error_msg}")
                db.log_download(user_id, url, "failed", error=error_msg)
                return ConversationHandler.END
        
        # إرسال الملفات
        if result.get("is_playlist"):
            await processing_msg.edit_text(
                f"✅ تم العثور على قائمة التشغيل: {result['title']}\n"
                f"📦 عدد الملفات: {len(result['files'])}\n"
                f"⏳ جاري الإرسال..."
            )
            
            for i, file_path in enumerate(result["files"], 1):
                try:
                    with open(file_path, 'rb') as f:
                        if format_type.startswith("playlist_audio"):
                            await update.message.reply_audio(f, title=f"Track {i}")
                        else:
                            await update.message.reply_video(f)
                    downloader.cleanup(file_path)
                except Exception as e:
                    logger.error(f"Error sending file {file_path}: {e}")
            
            await processing_msg.edit_text("✅ تم إرسال قائمة التشغيل بنجاح!")
            db.log_download(user_id, url, "success_playlist")
            
        else:
            file_path = result["file_path"]
            file_size = os.path.getsize(file_path)
            
            # التحقق من حجم الملف (تيليجرام 2GB للملفات العادية)
            if file_size > 2 * 1024 * 1024 * 1024:
                await processing_msg.edit_text("❌ حجم الملف كبير جداً (أكبر من 2GB)")
                downloader.cleanup(file_path)
                return ConversationHandler.END
            
            await processing_msg.edit_text("📤 جاري إرسال الملف...")
            
            with open(file_path, 'rb') as f:
                if format_type == "audio":
                    await update.message.reply_audio(f, title=result["title"])
                else:
                    await update.message.reply_video(f, supports_streaming=True)
            
            downloader.cleanup(file_path)
            await processing_msg.delete()
            db.log_download(user_id, url, "success", file_path)
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        await processing_msg.edit_text(f"❌ حدث خطأ غير متوقع: {str(e)}")
        db.log_download(user_id, url, "error", error=str(e))
    
    return ConversationHandler.END

# ==================== لوحة التحكم Admin ====================

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍪 إضافة/تحديث الكوكيز", callback_data="admin_cookies")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 إدارة المشرفين", callback_data="admin_admins")],
        [InlineKeyboardButton("🗑 تنظيف الملفات المؤقتة", callback_data="admin_cleanup")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
    ]
    
    await update.callback_query.edit_message_text(
        "🔐 *لوحة تحكم المشرف*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if not db.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return ConversationHandler.END
    
    if data == "admin_cookies":
        await query.edit_message_text(
            "🍪 *إدارة الكوكيز*\n\n"
            "الكوكيز ضرورية لتحميل:\n"
            "• الفيديوهات محدودة العمر (+18)\n"
            "• المحتوى الخاص\n"
            "• لتجنب حظر IP\n\n"
            "أرسل الآن ملف الكوكيز (cookies.txt)\n"
            "الصيغة المدعومة: Netscape format\n\n"
            "_للحصول على الكوكيز استخدم إضافة:_\n"
            "_Get cookies.txt LOCALLY للمتصفح_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
        return WAITING_FOR_COOKIES
    
    elif data == "admin_stats":
        total_users = db.users.count_documents({})
        total_downloads = db.downloads.count_documents({})
        successful = db.downloads.count_documents({"status": "success"})
        failed = total_downloads - successful
        
        await query.edit_message_text(
            f"📊 *إحصائيات البوت:*\n\n"
            f"👥 إجمالي المستخدمين: {total_users}\n"
            f"📥 إجمالي التحميلات: {total_downloads}\n"
            f"✅ ناجحة: {successful}\n"
            f"❌ فاشلة: {failed}\n"
            f"🎯 نسبة النجاح: {round((successful/total_downloads*100) if total_downloads > 0 else 0, 1)}%",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
        return ADMIN_PANEL
    
    elif data == "admin_cleanup":
        count = 0
        for f in os.listdir("downloads"):
            if f != "cookies.txt":
                try:
                    os.remove(os.path.join("downloads", f))
                    count += 1
                except:
                    pass
        
        await query.edit_message_text(
            f"🗑 تم حذف {count} ملف مؤقت\n\n"
            f"✅ تم التنظيف بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
        return ADMIN_PANEL
    
    elif data == "admin_panel":
        await show_admin_panel(update, context)
        return ADMIN_PANEL

async def handle_cookies_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ ليس لديك صلاحية!")
        return ConversationHandler.END
    
    if not update.message.document:
        await update.message.reply_text("❌ يرجى إرسال ملف cookies.txt")
        return WAITING_FOR_COOKIES
    
    file = update.message.document
    
    if not file.file_name.endswith('.txt'):
        await update.message.reply_text("❌ الملف يجب أن يكون بصيغة .txt")
        return WAITING_FOR_COOKIES
    
    try:
        # تحميل الملف
        file_obj = await context.bot.get_file(file.file_id)
        bio = BytesIO()
        await file_obj.download_to_memory(bio)
        content = bio.getvalue().decode('utf-8')
        
        # التحقق من صحة الملف (بسيط)
        if "youtube.com" not in content and "youtu.be" not in content:
            await update.message.reply_text(
                "⚠️ تحذير: الملف لا يبدو أنه يحتوي على كوكيز يوتيوب!\n"
                "هل تريد حفظه على أي حال؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ نعم، احفظ", callback_data="confirm_cookies"),
                     InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]
                ])
            )
            context.user_data["temp_cookies"] = content
            return ADMIN_PANEL
        
        # حفظ الكوكيز
        db.save_cookies("youtube_cookies", content, user_id)
        
        await update.message.reply_text(
            "✅ *تم حفظ الكوكيز بنجاح!*\n\n"
            "سيتم استخدامها تلقائياً في التحميلات القادمة.\n"
            "الفيديوهات المحمية الآن ستعمل مباشرة.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للوحة التحكم", callback_data="admin_panel")]])
        )
        return ADMIN_PANEL
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في معالجة الملف: {str(e)}")
        return WAITING_FOR_COOKIES

async def confirm_cookies_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    content = context.user_data.get("temp_cookies")
    if content:
        db.save_cookies("youtube_cookies", content, update.effective_user.id)
        await query.edit_message_text(
            "✅ تم حفظ الكوكيز!\n\n"
            "سيتم تجربتها في التحميل القادم.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
    
    return ADMIN_PANEL

# ==================== معالج الأخطاء ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")
    
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ حدث خطأ غير متوقع!\n"
            "يرجى المحاولة مرة أخرى أو التواصل مع المشرف."
        )

# ==================== التشغيل الرئيسي ====================

def main():
    # التوكن (احصل عليه من @BotFather)
    TOKEN = "2073340985:AAEN9KGThjc6u2Aj7l0MRH7HsOXuRNMPx60"
    
    application = Application.builder().token(TOKEN).build()
    
    # محادثة التحميل
    download_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^format_")],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)],
            WAITING_FOR_QUALITY: [CallbackQueryHandler(button_handler, pattern="^quality_")]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(button_handler, pattern="^back_to_main")]
    )
    
    # محادثة الأدمن
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^admin_panel$")],
        states={
            ADMIN_PANEL: [
                CallbackQueryHandler(admin_actions, pattern="^admin_"),
                CallbackQueryHandler(confirm_cookies_save, pattern="^confirm_cookies$"),
                MessageHandler(filters.Document.ALL, handle_cookies_file)
            ],
            WAITING_FOR_COOKIES: [
                MessageHandler(filters.Document.ALL, handle_cookies_file),
                CallbackQueryHandler(admin_actions, pattern="^admin_panel$")
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern="^back_to_main$")]
    )
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(download_conv)
    application.add_handler(admin_conv)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # معالج الأخطاء
    application.add_error_handler(error_handler)
    
    print("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
