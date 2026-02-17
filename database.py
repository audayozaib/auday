import ssl
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import MONGO_URI, ADMIN_ID, RATE_LIMIT_PER_MINUTE

class AsyncDatabase:
    def __init__(self, uri: str = MONGO_URI):
        # إعدادات SSL لـ MongoDB Atlas
        if "mongodb+srv://" in uri:
            # MongoDB Atlas - استخدام TLS
            self.client = AsyncIOMotorClient(
                uri,
                tls=True,
                tlsAllowInvalidCertificates=False,
                serverSelectionTimeoutMS=30000,
                retryWrites=True,
                w='majority'
            )
        else:
            # MongoDB محلي
            self.client = AsyncIOMotorClient(uri)
            
        self.db = self.client["youtube_bot_db"]
        self.users = self.db["users"]
        self.downloads = self.db["downloads"]
        self.cookies = self.db["cookies"]
        self.settings = self.db["settings"]
        self.banned = self.db["banned"]
        
    async def init_indexes(self):
        try:
            await self.users.create_index("user_id", unique=True)
            await self.downloads.create_index([("user_id", 1), ("created_at", -1)])
            await self.downloads.create_index("status")
            await self.cookies.create_index("name", unique=True)
            await self.banned.create_index("user_id", unique=True)
            await self.banned.create_index("expires_at", expireAfterSeconds=0)
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise
