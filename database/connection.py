from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME

client = None
db = None

async def init_db():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    try:
        await db.channels.drop_indexes()
    except Exception:
        pass

    await db.channels.create_index(
        [("owner_id", 1), ("channel_id", 1)],
        unique=True,
        name="owner_channel_unique"
    )

    print(f"✅ Connected to MongoDB: {DB_NAME}")
    print(f"✅ Database indexes configured")
    return db

def get_db():
    global db
    return db
