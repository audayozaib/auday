class YouTubeBotError(Exception):
    """الفئة الأساسية لأخطاء البوت"""
    pass

class DownloadError(YouTubeBotError):
    def __init__(self, message, error_type="unknown"):
        self.error_type = error_type
        self.message = message
        super().__init__(message)

class ValidationError(YouTubeBotError):
    pass

class RateLimitExceeded(YouTubeBotError):
    pass

class FileTooLargeError(YouTubeBotError):
    def __init__(self, size, max_size):
        self.size = size
        self.max_size = max_size
        super().__init__(f"File size {size} exceeds limit {max_size}")

class CancelledError(YouTubeBotError):
    pass
