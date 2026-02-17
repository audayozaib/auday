"""
التحقق من الروابط - بدون أي إشارة لـ aria2
"""
import re
from urllib.parse import urlparse

YOUTUBE_PATTERNS = [
    r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}',
    r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]{11}',
    r'^https?://youtu\.be/[\w-]{11}',
    r'^https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
]

def validate_youtube_url(url: str) -> bool:
    if not url or len(url) > 2000:
        return False
    
    parsed = urlparse(url.strip())
    
    if parsed.scheme not in ['http', 'https']:
        return False
    
    if not any(domain in parsed.netloc for domain in ['youtube.com', 'youtu.be']):
        return False
    
    return any(re.match(pattern, url.strip()) for pattern in YOUTUBE_PATTERNS)

def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename[:100]
