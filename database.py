"""
قاعدة البيانات - Async MongoDB مع دعم Atlas و المحلي
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import MONGO_URI, ADMIN_ID, RATE_LIMIT_PER_MINUTE

logger = logging.getLogger(__name__)


class AsyncDatabase:
    def __init__(self, uri: str = MONGO_URI):
        # إعدادات الاتصال حسب نوع MongoDB
        if "mongodb+srv://" in uri:
            # MongoDB Atlas - إعدادات TLS
            self.client = AsyncIOMotorClient(
                uri,
                tls=True,
                tlsAllowInvalidCertificates=False,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
                retryWrites=True,
                w='majority'
            )
            logger.info("Connected to MongoDB Atlas")
        else:
            # MongoDB محلي
            self.client = AsyncIOMotorClient(uri)
            logger.info("Connected to local MongoDB")
            
        self.db = self.client["youtube_bot_db"]
        self.users = self.db["users"]
        self.downloads = self.db["downloads"]
        self.cookies = self.db["cookies"]
        self.settings = self.db["settings"]
        self.banned = self.db["banned"]
        
    async def init_indexes(self):
        """إنشاء الفهارس لتحسين الأداء"""
        try:
            # فهرس المستخدمين
            await self.users.create_index("user_id", unique=True)
            
            # فهارس التحميلات
            await self.downloads.create_index([("user_id", 1), ("created_at", -1)])
            await self.downloads.create_index("status")
            await self.downloads.create_index("created_at")
            
            # فهرس الكوكيز
            await self.cookies.create_index("name", unique=True)
            
            # فهارس الحظر
            await self.banned.create_index("user_id", unique=True)
            await self.banned.create_index("expires_at", expireAfterSeconds=0)
            
            logger.info("✅ Database indexes created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
            # لا نوقف البوت إذا فشل إنشاء الفهارس
            pass
        
    async def is_banned(self, user_id: int) -> bool:
        """التحقق إذا كان المستخدم محظور"""
        banned = await self.banned.find_one({"user_id": user_id})
        return banned is not None
    
    async def ban_user(self, user_id: int, reason: str = "", duration_hours: int = 0):
        """حظر مستخدم"""
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
        logger.info(f"User {user_id} banned. Reason: {reason}")
    
    async def unban_user(self, user_id: int):
        """إلغاء حظر مستخدم"""
        await self.banned.delete_one({"user_id": user_id})
        logger.info(f"User {user_id} unbanned")
    
    async def is_admin(self, user_id: int) -> bool:
        """التحقق إذا كان المستخدم أدمن"""
        if user_id == ADMIN_ID:
            return True
        config = await self.settings.find_one({"key": "admin_ids"})
        return user_id in config.get("value", []) if config else False
    
    async def add_admin(self, user_id: int):
        """إضافة أدمن جديد"""
        await self.settings.update_one(
            {"key": "admin_ids"},
            {"$addToSet": {"value": user_id}},
            upsert=True
        )
        logger.info(f"User {user_id} added as admin")
    
    async def check_rate_limit(self, user_id: int) -> bool:
        """التحقق من عدم تجاوز الحد المسموح"""
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        count = await self.downloads.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": one_minute_ago}
        })
        return count < RATE_LIMIT_PER_MINUTE
    
    async def log_download(self, user_id: int, url: str, status: str, 
                          metadata: dict = None, error: str = None):
        """تسجيل عملية تحميل"""
        await self.downloads.insert_one({
            "user_id": user_id,
            "url": url,
            "status": status,
            "error": error,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7)
        })
    
    async def update_user(self, user_id: int, **kwargs):
        """تحديث معلومات المستخدم"""
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {**kwargs, "last_visit": datetime.now()}},
            upsert=True
        )
    
    async def get_user_stats(self, user_id: int) -> dict:
        """الحصول على إحصائيات المستخدم"""
        total = await self.downloads.count_documents({"user_id": user_id})
        successful = await self.downloads.count_documents({
            "user_id": user_id, 
            "status": {"$in": ["success", "success_playlist"]}
        })
        
        # آخر 5 تحميلات
        recent = await self.downloads.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(5).to_list(length=5)
        
        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "recent": recent
        }
    
    async def get_bot_stats(self) -> dict:
        """إحصائيات البوت الكاملة"""
        total_users = await self.users.count_documents({})
        total_downloads = await self.downloads.count_documents({})
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_downloads = await self.downloads.count_documents({
            "created_at": {"$gte": today_start}
        })
        
        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "today_downloads": today_downloads
        }


# إنشاء instance واحد
db = AsyncDatabase()
