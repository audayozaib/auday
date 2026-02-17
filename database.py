from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import MONGO_URI, ADMIN_ID, RATE_LIMIT_PER_MINUTE

class AsyncDatabase:
    def __init__(self, uri: str = MONGO_URI):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client["youtube_bot_db"]
        self.users = self.db["users"]
        self.downloads = self.db["downloads"]
        self.cookies = self.db["cookies"]
        self.settings = self.db["settings"]
        self.banned = self.db["banned"]
        
    async def init_indexes(self):
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
            {"user_id": user_id}, {"$set": doc}, upsert=True
        )
    
    async def is_admin(self, user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return True
        config = await self.settings.find_one({"key": "admin_ids"})
        return user_id in config.get("value", []) if config else False
    
    async def check_rate_limit(self, user_id: int) -> bool:
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        count = await self.downloads.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": one_minute_ago}
        })
        return count < RATE_LIMIT_PER_MINUTE
    
    async def log_download(self, user_id: int, url: str, status: str, 
                          metadata: dict = None, error: str = None):
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
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {**kwargs, "last_visit": datetime.now()}},
            upsert=True
        )
    
    async def get_user_stats(self, user_id: int):
        total = await self.downloads.count_documents({"user_id": user_id})
        successful = await self.downloads.count_documents({
            "user_id": user_id, 
            "status": {"$in": ["success", "success_playlist"]}
        })
        recent = await self.downloads.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(5).to_list(length=5)
        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "recent": recent
        }

db = AsyncDatabase()
