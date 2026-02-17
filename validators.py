import re
from urllib.parse import urlparse
from exceptions import ValidationError

YOUTUBE_PATTERNS = [
    r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}(?:&.*)?$',
    r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]{11}$',
    r'^https?://youtu\.be/[\w-]{11}(?:\?.*)?$',
    r'^https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+$',
    r'^https?://(?:www\.)?youtube\.com/embed/[\w-]{11}$'
]

def validate_youtube_url(url: str) -> bool:
    """التحقق الصارم من روابط يوتيوب"""
    if not url or len(url) > 2000:
        return False
    
    parsed = urlparse(url.strip())
    
    if parsed.scheme not in ['http', 'https']:
        return False
    
    if not any(domain in parsed.netloc for domain in ['youtube.com', 'youtu.be', 'www.youtube.com']):
        return False
    
    return any(re.match(pattern, url.strip()) for pattern in YOUTUBE_PATTERNS)

def sanitize_filename(filename: str) -> str:
    """تنظيف أسماء الملفات من المحارف الخطرة"""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename[:100]  # تقصير الاسم

def extract_video_id(url: str) -> str:
    """استخراج معرف الفيديو"""
    patterns = [
        r'(?:v=|\/)([\w-]{11}).*',
        r'(?:embed\/)([\w-]{11})',
        r'(?:youtu\.be\/)([\w-]{11})',
        r'(?:shorts\/)([\w-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""
