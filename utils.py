import os
import asyncio
from pathlib import Path
from telegram import InputFile

async def cleanup_file(file_path: str):
    """تنظيف ملف أو مجلد"""
    try:
        path = Path(file_path)
        if path.exists():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil
                shutil.rmtree(path, ignore_errors=True)
    except Exception as e:
        print(f"Cleanup error: {e}")

async def safe_edit_message(query, text: str, reply_markup=None, parse_mode="Markdown"):
    """تعديل رسالة بأمان"""
    try:
        from telegram.error import BadRequest
        current = query.message.text
        if current != text or (reply_markup and query.message.reply_markup != reply_markup):
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise
    except Exception:
        pass

def format_duration(seconds: int) -> str:
    """تنسيق المدة"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
