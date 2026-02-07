from datetime import datetime
from database.connection import get_db
from bson import ObjectId
from typing import List, Optional, Dict

async def create_template(
    user_id: int,
    name: str,
    title: str = None,
    description: str = None,
    image_file_id: str = None,
    duration_seconds: int = None,
    winners_count: int = None,
    winner_type: str = None,
    required_channels: List[int] = None
) -> Optional[str]:
    db = get_db()

    template_doc = {
        "user_id": user_id,
        "name": name,
        "title": title,
        "description": description,
        "image_file_id": image_file_id,
        "duration_seconds": duration_seconds,
        "winners_count": winners_count,
        "winner_type": winner_type,
        "required_channels": required_channels or [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.templates.insert_one(template_doc)
    return str(result.inserted_id)

async def get_user_templates(user_id: int) -> List[Dict]:
    db = get_db()
    templates = await db.templates.find({"user_id": user_id}).sort("created_at", -1).to_list(length=None)

    for template in templates:
        template['id'] = str(template['_id'])

    return templates

async def get_template_by_id(template_id: str, user_id: int) -> Optional[Dict]:
    db = get_db()
    template = await db.templates.find_one({
        "_id": ObjectId(template_id),
        "user_id": user_id
    })

    if template:
        template['id'] = str(template['_id'])

    return template

async def update_template(
    template_id: str,
    user_id: int,
    name: str,
    title: str = None,
    description: str = None,
    image_file_id: str = None,
    duration_seconds: int = None,
    winners_count: int = None,
    winner_type: str = None,
    required_channels: List[int] = None
) -> bool:
    db = get_db()
    result = await db.templates.update_one(
        {"_id": ObjectId(template_id), "user_id": user_id},
        {"$set": {
            "name": name,
            "title": title,
            "description": description,
            "image_file_id": image_file_id,
            "duration_seconds": duration_seconds,
            "winners_count": winners_count,
            "winner_type": winner_type,
            "required_channels": required_channels or [],
            "updated_at": datetime.utcnow()
        }}
    )
    return result.modified_count > 0

async def delete_template(template_id: str, user_id: int) -> bool:
    db = get_db()
    result = await db.templates.delete_one({
        "_id": ObjectId(template_id),
        "user_id": user_id
    })
    return result.deleted_count > 0

async def count_user_templates(user_id: int) -> int:
    db = get_db()
    return await db.templates.count_documents({"user_id": user_id})
