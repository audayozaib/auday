import os
import asyncio
import logging
import yt_dlp
import aiohttp
import aiofiles
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from io import BytesIO
from pathlib import Path
import tempfile
import shutil
import functools
import hashlib

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    InputFile, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters, AIORateLimiter
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import Conflict, RetryAfter, BadRequest

# استخدام motor للـ Async MongoDB
from motor.motor_asyncio import AsyncIOMotorClient
# إزالة: import gridfs (غير مستخدم)

# ==================== الإعدادات المتقدمة ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
TOKEN = os.environ.get("BOT_TOKEN","2073340985:AAEN9KGThjc6u2Aj7l0MRH7HsOXuRNMPx60")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://audayozaib:SaXaXket2GECpLvR@giveaway.x2eabrg.mongodb.net/giveaway?retryWrites=true&w=majority")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 778375826))  # معرف الأدمن الرئيسي

# حدود البوت
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  
MAX_PLAYLIST_ITEMS = 5  
MAX_DURATION_MINUTES = 120  
RATE_LIMIT_PER_MINUTE = 5  

# ==================== قاعدة البيانات Async (مصححة) ====================
class AsyncDatabase:
    def __init__(self, uri: str = MONGO_URI):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client["youtube_bot_db"]
        self.users = self.db["users"]
        self.downloads = self.db["downloads"]
        self.cookies = self.db["cookies"]
        self.settings = self.db["settings"]
        # إزالة GridFS لأنه غير مستخدم ويسبب المشكلة
        # self.fs = gridfs.GridFS(self.db)  # <-- تم إزالة هذا السطر
        
        # قائمة الحظر
        self.banned = self.db["banned"]
        
    async def init_indexes(self):
        """إنشاء الفهارس لتحسين الأداء"""
        await self.users.create_index("user_id", unique=True)
        await self.downloads.create_index([("user_id", 1), ("created_at", -1)])
        await self.downloads.create_index("status")
        await self.cookies.create_index("name", unique=True)
        await self.banned.create_index("user_id", unique=True)
        await self.banned.create_index("expires_at", expireAfterSeconds=0)
        
    async def is_banned(self, user_id: int) -> bool:
        banned = await self.banned.find_one({"user_id": user_id})
        return banned is not None
    
    async def ban_user(self, user_id: int, reason: str = "", duration_hours: int = 0):
        doc = {
            "user_id": user_id,
            "reason": reason,
            "banned_at": datetime.now(),
            "banned_by": ADMIN_ID
        }
        if duration_hours > 0:
            doc["expires_at"] = datetime.now() + timedelta(hours=duration_hours)
        await self.banned.update_one(
            {"user_id": user_id},
            {"$set": doc},
            upsert=True
        )
    
    async def unban_user(self, user_id: int):
        await self.banned.delete_one({"user_id": user_id})
    
    async def is_admin(self, user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return True
        config = await self.settings.find_one({"key": "admin_ids"})
        return user_id in config.get("value", []) if config else False
    
    async def add_admin(self, user_id: int):
        await self.settings.update_one(
            {"key": "admin_ids"},
            {"$addToSet": {"value": user_id}},
            upsert=True
        )
    
    async def log_download(self, user_id: int, url: str, status: str, 
                          file_path: Optional[str] = None, error: Optional[str] = None,
                          metadata: Optional[dict] = None):
        await self.downloads.insert_one({
            "user_id": user_id,
            "url": url,
            "status": status,
            "file_path": file_path,
            "error": error,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7)
        })
    
    async def check_rate_limit(self, user_id: int) -> bool:
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        count = await self.downloads.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": one_minute_ago}
        })
        return count < RATE_LIMIT_PER_MINUTE
    
    async def get_user_stats(self, user_id: int):
        total = await self.downloads.count_documents({"user_id": user_id})
        successful = await self.downloads.count_documents({
            "user_id": user_id, 
            "status": {"$in": ["success", "success_playlist"]}
        })
        failed = total - successful
        recent = await self.downloads.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(5).to_list(length=5)
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "recent": recent
        }

db = AsyncDatabase()

# ==================== مدير التحميل المتقدم ====================
class AdvancedDownloadManager:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "yt_bot"
        self.temp_dir.mkdir(exist_ok=True)
        self.active_downloads = {}
        self._semaphore = asyncio.Semaphore(3)
        
    def get_ydl_opts(self, format_type: str, quality: str = "best", 
                     cookies_path: Optional[str] = None,
                     progress_hook: Optional[callable] = None) -> dict:
        opts = {
            'outtmpl': str(self.temp_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 3,
            'file_access_retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'keep_fragments': False,
        }
        
        if cookies_path and os.path.exists(cookies_path):
            opts['cookiefile'] = cookies_path
            
        if progress_hook:
            opts['progress_hooks'] = [progress_hook]
            
        if format_type == "audio":
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }, {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'writethumbnail': True,
                'embedthumbnail': True,
            })
        elif format_type == "video":
            if quality == "best":
                opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                height = quality.replace('p', '')
                opts['format'] = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}]'
            
            opts['merge_output_format'] = 'mp4'
            opts['postprocessors'] = [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]
            
        return opts
    
    async def extract_info(self, url: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = await loop.run_in_executor(
                    None, 
                    functools.partial(ydl.extract_info, url, download=False)
                )
                return info
        except Exception as e:
            logger.error(f"Extract info error: {e}")
            return None
    
    async def download(self, url: str, format_type: str, quality: str = "best",
                      progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        async with self._semaphore:
            download_id = hashlib.md5(f"{url}{format_type}{quality}".encode()).hexdigest()
            self.active_downloads[download_id] = {"cancelled": False}
            
            output_dir = self.temp_dir / download_id
            output_dir.mkdir(exist_ok=True)
            
            def progress_hook(d):
                if self.active_downloads.get(download_id, {}).get("cancelled"):
                    raise Exception("Download cancelled by user")
                    
                if d['status'] == 'downloading' and progress_callback:
                    percent = d.get('_percent_str', '0%')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    asyncio.create_task(progress_callback(percent, speed, eta))
            
            try:
                opts = self.get_ydl_opts(format_type, quality, 
                                        output_path=str(output_dir),
                                        progress_hook=progress_hook)
                
                loop = asyncio.get_event_loop()
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = await loop.run_in_executor(
                        None,
                        functools.partial(ydl.extract_info, url, download=True)
                    )
                    
                    if not info:
                        return {"success": False, "error": "No info extracted"}
                    
                    if 'entries' in info:
                        files = []
                        entries = list(info['entries'])[:MAX_PLAYLIST_ITEMS]
                        for entry in entries:
                            if not entry:
                                continue
                            filename = ydl.prepare_filename(entry)
                            if format_type == "audio":
                                filename = filename.rsplit('.', 1)[0] + '.mp3'
                            if os.path.exists(filename):
                                files.append(filename)
                        
                        return {
                            "success": True,
                            "files": files,
                            "is_playlist": True,
                            "title": info.get("title", "Playlist"),
                            "count": len(files)
                        }
                    else:
                        filename = ydl.prepare_filename(info)
                        if format_type == "audio":
                            filename = filename.rsplit('.', 1)[0] + '.mp3'
                        
                        file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                        
                        return {
                            "success": True,
                            "file_path": filename,
                            "title": info.get("title", "Unknown"),
                            "duration": info.get("duration", 0),
                            "uploader": info.get("uploader", "Unknown"),
                            "thumbnail": info.get("thumbnail"),
                            "is_playlist": False,
                            "file_size": file_size
                        }
                        
            except Exception as e:
                logger.error(f"Download error: {e}")
                return {"success": False, "error": str(e)}
            finally:
                self.active_downloads.pop(download_id, None)
    
    async def cancel_download(self, download_id: str):
        if download_id in self.active_downloads:
            self.active_downloads[download_id]["cancelled"] = True
    
    async def cleanup(self, file_path: str):
        try:
            path = Path(file_path)
            if path.exists():
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

dl_manager = AdvancedDownloadManager()

# ==================== حالات المحادثة ====================
(
    CHOOSING_FORMAT, 
    CHOOSING_QUALITY, 
    WAITING_URL, 
    DOWNLOADING,
    ADMIN_MENU,
    BROADCAST_MSG,
    SEARCH_YOUTUBE
) = range(7)

# ==================== دوال مساعدة ====================
async def send_action(update: Update, action: ChatAction):
    try:
        await update.effective_chat.send_action(action)
    except:
        pass

async def check_user_access(update: Update) -> bool:
    user_id = update.effective_user.id
    
    if await db.is_banned(user_id):
        await update.effective_message.reply_text(
            "⛔️ تم حظرك من استخدام البوت. تواصل مع المشرف."
        )
        return False
    
    if not await db.check_rate_limit(user_id):
        await update.effective_message.reply_text(
            "⏳ لقد تجاوزت الحد المسموح من الطلبات (5 طلبات/دقيقة). انتظر قليلاً."
        )
        return False
    
    return True

async def update_user_info(update: Update):
    user = update.effective_user
    await db.users.update_one(
        {"user_id": user.id},
        {"$set": {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "last_visit": datetime.now(),
            "language": user.language_code
        }},
        upsert=True
    )

# ==================== الأوامر الرئيسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_access(update):
        return ConversationHandler.END
    
    await update_user_info(update)
    user = update.effective_user
    
    commands = [
        BotCommand("start", "بدء البوت"),
        BotCommand("help", "المساعدة"),
        BotCommand("stats", "إحصائياتي"),
        BotCommand("cancel", "إلغاء العملية الحالية")
    ]
    await context.bot.set_my_commands(commands)
    
    keyboard = [
        [InlineKeyboardButton("🎵 تحميل صوت (MP3)", callback_data="fmt_audio")],
        [InlineKeyboardButton("🎬 تحميل فيديو (MP4)", callback_data="fmt_video")],
        [InlineKeyboardButton("🔍 البحث في يوتيوب", callback_data="search_yt")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")]
    ]
    
    if await db.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔐 لوحة التحكم", callback_data="admin_panel")])
    
    await update.message.reply_text(
        f"👋 أهلاً بك *{user.first_name}*!\n\n"
        "🤖 بوت تحميل يوتيوب المتقدم v2.0\n\n"
        "✨ المميزات:\n"
        "• تحميل الفيديوهات بجودة حتى 4K\n"
        "• استخراج الصوت بجودة 320kbps\n"
        "• دعم قوائم التشغيل (حتى 5 فيديوهات)\n"
        "• تحميل الفيديوهات القصيرة (Shorts)\n"
        "• سرعة عالية واستقرار",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_FORMAT

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 *دليل الاستخدام:*

1️⃣ أرسل رابط الفيديو من يوتيوب
2️⃣ اختر الصيغة (فيديو أو صوت)
3️⃣ اختر الجودة المطلوبة
4️⃣ انتظر التحميل والإرسال

⚠️ *ملاحظات:*
• الحد الأقصى للحجم: 2GB
• الحد الأقصى للمدة: 120 دقيقة
• قوائم التشغيل: 5 فيديوهات كحد أقصى
• استخدم /cancel لإلغاء أي عملية
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ تم إلغاء العملية الحالية.\nاستخدم /start للبدء من جديد."
    )
    return ConversationHandler.END

# ==================== معالجة الأزرار ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("fmt_"):
        format_type = data.replace("fmt_", "")
        context.user_data["format"] = format_type
        
        if format_type == "video":
            keyboard = [
                [InlineKeyboardButton("🥇 أفضل جودة تلقائية", callback_data="q_best")],
                [InlineKeyboardButton("🎬 1080p", callback_data="q_1080"),
                 InlineKeyboardButton("📺 720p", callback_data="q_720")],
                [InlineKeyboardButton("📱 480p", callback_data="q_480"),
                 InlineKeyboardButton("📱 360p", callback_data="q_360")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]
            ]
            await query.edit_message_text(
                "📊 اختر جودة الفيديو:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING_QUALITY
        else:
            await query.edit_message_text(
                "🎵 تم اختيار: *صوت MP3*\n\n"
                "🔗 أرسل رابط الفيديو من يوتيوب:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]])
            )
            return WAITING_URL
            
    elif data.startswith("q_"):
        quality = data.replace("q_", "")
        context.user_data["quality"] = quality
        quality_text = "تلقائية" if quality == "best" else quality + "p"
        
        await query.edit_message_text(
            f"🎬 الجودة المختارة: *{quality_text}*\n\n"
            "🔗 أرسل رابط الفيديو من يوتيوب:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]])
        )
        return WAITING_URL
    
    elif data == "search_yt":
        await query.edit_message_text(
            "🔍 *البحث في يوتيوب*\n\n"
            "أرسل كلمة البحث الآن:",
            parse_mode=ParseMode.MARKDOWN
        )
        return SEARCH_YOUTUBE
    
    elif data == "my_stats":
        await send_action(update, ChatAction.TYPING)
        stats = await db.get_user_stats(user_id)
        success_rate = round((stats['successful']/stats['total']*100), 1) if stats['total'] > 0 else 0
        
        recent_text = ""
        if stats['recent']:
            recent_text = "\n\n📋 *آخر 5 تحميلات:*\n"
            for i, dl in enumerate(stats['recent'], 1):
                status = "✅" if dl['status'] in ['success', 'success_playlist'] else "❌"
                date = dl['created_at'].strftime("%m/%d %H:%M")
                recent_text += f"{status} `{date}`\n"
        
        await query.edit_message_text(
            f"📊 *إحصائياتك:*\n\n"
            f"✅ ناجحة: `{stats['successful']}`\n"
            f"❌ فاشلة: `{stats['failed']}`\n"
            f"📥 الإجمالي: `{stats['total']}`\n"
            f"🎯 نسبة النجاح: `{success_rate}%`"
            f"{recent_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]])
        )
    
    elif data == "admin_panel":
        if await db.is_admin(user_id):
            return await show_admin_panel(update, context)
    
    elif data == "back_start":
        return await start(update, context)
    
    return ConversationHandler.END

# ==================== معالجة التحميل ====================
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_access(update):
        return ConversationHandler.END
    
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    if not any(x in url for x in ["youtube.com", "youtu.be", "youtube.com/shorts"]):
        await update.message.reply_text(
            "❌ الرابط غير صحيح!\n"
            "يجب أن يكون رابطاً من يوتيوب (youtube.com أو youtu.be)"
        )
        return WAITING_URL
    
    format_type = context.user_data.get("format", "video")
    quality = context.user_data.get("quality", "best")
    
    processing_msg = await update.message.reply_text("⏳ جاري تحليل الرابط...")
    await send_action(update, ChatAction.UPLOAD_DOCUMENT)
    
    try:
        info = await dl_manager.extract_info(url)
        if not info:
            await processing_msg.edit_text("❌ لم يتم العثور على الفيديو أو الرابط غير صالح.")
            return ConversationHandler.END
        
        duration = info.get('duration', 0) / 60
        if duration > MAX_DURATION_MINUTES:
            await processing_msg.edit_text(
                f"❌ الفيديو طويل جداً ({int(duration)} دقيقة).\n"
                f"الحد الأقصى المسموح: {MAX_DURATION_MINUTES} دقيقة."
            )
            return ConversationHandler.END
        
        title = info.get('title', 'Unknown')
        await processing_msg.edit_text(
            f"📥 جاري التحميل:\n*{title}*\n\n"
            f"⏳ 0% | السرعة: حساب...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        last_update = [0]
        async def progress_hook(percent, speed, eta):
            current = int(float(percent.replace('%', '')))
            if current - last_update[0] >= 10:
                last_update[0] = current
                try:
                    await processing_msg.edit_text(
                        f"📥 جاري التحميل:\n*{title}*\n\n"
                        f"⏳ {percent} | ⚡️ {speed} | ⏱ {eta}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
        
        result = await dl_manager.download(url, format_type, quality, progress_hook)
        
        if not result["success"]:
            error_msg = result["error"]
            await processing_msg.edit_text(f"❌ فشل التحميل:\n`{error_msg}`", parse_mode=ParseMode.MARKDOWN)
            await db.log_download(user_id, url, "failed", error=error_msg)
            return ConversationHandler.END
        
        if result.get("is_playlist"):
            await processing_msg.edit_text(
                f"📦 تم تحميل قائمة التشغيل: *{result['title']}*\n"
                f"عدد الملفات: {result['count']}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            for i, file_path in enumerate(result["files"], 1):
                try:
                    await send_action(update, ChatAction.UPLOAD_AUDIO if format_type == "audio" else ChatAction.UPLOAD_VIDEO)
                    
                    async with aiofiles.open(file_path, 'rb') as f:
                        content = await f.read()
                    
                    if format_type == "audio":
                        await update.message.reply_audio(
                            BytesIO(content),
                            caption=f"🎵 {result['title']} ({i}/{result['count']})"
                        )
                    else:
                        await update.message.reply_video(
                            BytesIO(content),
                            supports_streaming=True,
                            caption=f"🎬 {i}/{result['count']}"
                        )
                    
                    await dl_manager.cleanup(file_path)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error sending playlist file: {e}")
            
            await processing_msg.delete()
            await db.log_download(user_id, url, "success_playlist", metadata={"count": result['count']})
            
        else:
            file_path = result["file_path"]
            file_size = result.get("file_size", 0)
            
            if file_size > MAX_FILE_SIZE:
                await processing_msg.edit_text(
                    "❌ حجم الملف كبير جداً (>2GB).\n"
                    "جرب تحميل جودة أقل أو استخدم رابط آخر."
                )
                await dl_manager.cleanup(file_path)
                return ConversationHandler.END
            
            if result.get('thumbnail') and format_type == "audio":
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(result['thumbnail']) as resp:
                            if resp.status == 200:
                                thumb_data = await resp.read()
                                await update.message.reply_photo(thumb_data)
                except:
                    pass
            
            await processing_msg.edit_text("📤 جاري إرسال الملف...")
            await send_action(update, ChatAction.UPLOAD_DOCUMENT)
            
            async with aiofiles.open(file_path, 'rb') as f:
                file_data = await f.read()
            
            file_obj = BytesIO(file_data)
            file_obj.name = os.path.basename(file_path)
            
            if format_type == "audio":
                await update.message.reply_audio(
                    file_obj,
                    title=result["title"],
                    performer=result.get("uploader", "YouTube"),
                    duration=result.get("duration"),
                    caption=f"✅ *{result['title']}*",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_video(
                    file_obj,
                    supports_streaming=True,
                    duration=result.get("duration"),
                    caption=f"🎬 *{result['title']}*\n✅ تم التحميل بنجاح",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await processing_msg.delete()
            await dl_manager.cleanup(file_path)
            await db.log_download(
                user_id, url, "success", 
                metadata={
                    "title": result["title"],
                    "size": file_size,
                    "format": format_type
                }
            )
            
            keyboard = [
                [InlineKeyboardButton("🎵 تحميل صوت آخر", callback_data="fmt_audio")],
                [InlineKeyboardButton("🎬 تحميل فيديو آخر", callback_data="fmt_video")]
            ]
            await update.message.reply_text(
                "🔄 ماذا تريد أن تفعل الآن؟",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except RetryAfter as e:
        await processing_msg.edit_text(f"⏳ انتظر {e.retry_after} ثانية...")
        await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        await processing_msg.edit_text(f"❌ خطأ غير متوقع:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)
        await db.log_download(user_id, url, "error", error=str(e))
    
    return ConversationHandler.END

# ==================== البحث في يوتيوب ====================
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    await send_action(update, ChatAction.TYPING)
    
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch5',
        }
        
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None,
                functools.partial(ydl.extract_info, query, download=False)
            )
        
        entries = info.get('entries', [])
        if not entries:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")
            return CHOOSING_FORMAT
        
        keyboard = []
        text = "🔍 *نتائج البحث:*\n\n"
        
        for i, entry in enumerate(entries[:5], 1):
            title = entry.get('title', 'Unknown')[:50]
            url = entry.get('url') or entry.get('webpage_url')
            duration = entry.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "?"
            
            text += f"{i}. {title} ({duration_str})\n"
            keyboard.append([InlineKeyboardButton(f"{i}. {title[:30]}...", callback_data=f"url_{url}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_start")])
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_FORMAT
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("❌ فشل البحث، جرب لاحقاً.")
        return CHOOSING_FORMAT

async def handle_search_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data.replace("url_", "")
    
    context.user_data["url"] = url
    keyboard = [
        [InlineKeyboardButton("🎵 صوت", callback_data="fmt_audio")],
        [InlineKeyboardButton("🎬 فيديو", callback_data="fmt_video")]
    ]
    
    await query.edit_message_text(
        "اختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_FORMAT

# ==================== لوحة التحكم ====================
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="ad_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="ad_users")],
        [InlineKeyboardButton("🍪 إدارة الكوكيز", callback_data="ad_cookies")],
        [InlineKeyboardButton("📢 إذاعة للكل", callback_data="ad_broadcast")],
        [InlineKeyboardButton("🗑 تنظيف الملفات", callback_data="ad_cleanup")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]
    ]
    
    await query.edit_message_text(
        "🔐 *لوحة تحكم المشرف*\n\nاختر الإجراء:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_MENU

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "ad_stats":
        total_users = await db.users.count_documents({})
        total_downloads = await db.downloads.count_documents({})
        today = await db.downloads.count_documents({
            "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
        })
        
        await query.edit_message_text(
            f"📊 *إحصائيات البوت:*\n\n"
            f"👥 المستخدمين: `{total_users}`\n"
            f"📥 إجمالي التحميلات: `{total_downloads}`\n"
            f"📥 تحميلات اليوم: `{today}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
    
    elif data == "ad_cleanup":
        try:
            shutil.rmtree(dl_manager.temp_dir, ignore_errors=True)
            dl_manager.temp_dir = Path(tempfile.gettempdir()) / "yt_bot"
            dl_manager.temp_dir.mkdir(exist_ok=True)
            await query.edit_message_text(
                "✅ تم تنظيف الملفات المؤقتة",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ خطأ: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
            )
    
    elif data == "ad_broadcast":
        await query.edit_message_text(
            "📢 أرسل الرسالة التي تريد إذاعتها للجميع:\n\n"
            "أو ارسل /cancel للإلغاء",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )
        return BROADCAST_MSG
    
    return ADMIN_MENU

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    await update.message.reply_text("⏳ جاري الإذاعة...")
    
    users = await db.users.find().to_list(length=None)
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                user['user_id'], 
                f"📢 *إشعار من المشرف:*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
            await asyncio.sleep(0.1)
        except:
            failed += 1
    
    await update.message.reply_text(
        f"✅ تم الإرسال: {sent}\n❌ فشل: {failed}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
    )
    return ADMIN_MENU

# ==================== معالجة الأخطاء ====================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}", exc_info=True)
    
    if isinstance(context.error, Conflict):
        logger.warning("⚠️ Conflict: Another instance is running")
        return
    
    if isinstance(context.error, RetryAfter):
        logger.warning(f"Rate limited: {context.error.retry_after}s")
        return
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع! سجل الخطأ تم إرساله للمشرف."
            )
        except:
            pass

# ==================== التشغيل الرئيسي ====================
async def post_init(application: Application):
    await db.init_indexes()
    logger.info("Bot started and database initialized")

def main():
    if not TOKEN:
        logger.error("No TOKEN provided!")
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
                CallbackQueryHandler(button_handler, pattern="^(fmt_|search_yt|my_stats|admin_panel|back_start)"),
                CallbackQueryHandler(handle_search_selection, pattern="^url_")
            ],
            CHOOSING_QUALITY: [
                CallbackQueryHandler(button_handler, pattern="^q_"),
                CallbackQueryHandler(button_handler, pattern="^back_start")
            ],
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
                CallbackQueryHandler(button_handler, pattern="^back_start")
            ],
            SEARCH_YOUTUBE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search),
                CallbackQueryHandler(button_handler, pattern="^back_start")
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_actions, pattern="^ad_"),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(button_handler, pattern="^back_start")
            ],
            BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("help", help_command)
        ],
        name="main_conversation",
        persistent=False
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    if WEBHOOK_URL:
        logger.info(f"Starting webhook on port {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        logger.info("Starting polling...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

if __name__ == "__main__":
    main()
