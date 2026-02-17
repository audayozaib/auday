"""
مدير التحميل - بدون أي إشارة لـ aria2
"""
import os
import asyncio
import functools
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Callable

import yt_dlp

from exceptions import DownloadError, CancelledError, FileTooLargeError
from config import TEMP_DIR, MAX_PLAYLIST_ITEMS, MAX_FILE_SIZE
from validators import sanitize_filename


class AdvancedDownloadManager:
    def __init__(self):
        self.temp_dir = Path(TEMP_DIR)
        self.temp_dir.mkdir(exist_ok=True)
        self.active_downloads = {}
        self._semaphore = asyncio.Semaphore(3)
        
    def get_ydl_opts(self, format_type: str, quality: str = "best", 
                     output_path: str = None, 
                     progress_hook: Callable = None) -> dict:
        opts = {
            'outtmpl': str(output_path or self.temp_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
        }
        
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
            
        return opts
    
    async def extract_info(self, url: str) -> Optional[dict]:
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return await loop.run_in_executor(
                    None, 
                    functools.partial(ydl.extract_info, url, download=False)
                )
        except Exception as e:
            error_msg = str(e).lower()
            if "copyright" in error_msg:
                raise DownloadError("Copyright protected", "copyright")
            elif "private" in error_msg:
                raise DownloadError("Private video", "private")
            elif "unavailable" in error_msg:
                raise DownloadError("Not available", "unavailable")
            return None
    
    async def download(self, url: str, format_type: str, quality: str = "best",
                      cancel_event: asyncio.Event = None,
                      progress_callback: Callable = None) -> Dict[str, Any]:
        async with self._semaphore:
            download_id = hashlib.md5(f"{url}{format_type}{quality}".encode()).hexdigest()[:8]
            output_dir = self.temp_dir / download_id
            output_dir.mkdir(exist_ok=True)
            
            def progress_hook(d):
                if cancel_event and cancel_event.is_set():
                    raise CancelledError()
                
                if d['status'] == 'downloading' and progress_callback:
                    percent = d.get('_percent_str', '0%')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    asyncio.create_task(progress_callback(percent, speed, eta))
            
            try:
                opts = self.get_ydl_opts(format_type, quality, str(output_dir), progress_hook)
                loop = asyncio.get_event_loop()
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = await loop.run_in_executor(
                        None,
                        functools.partial(ydl.extract_info, url, download=True)
                    )
                    
                    if not info:
                        raise DownloadError("Failed to extract info")
                    
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
                            "title": sanitize_filename(info.get("title", "Playlist")),
                            "count": len(files)
                        }
                    else:
                        filename = ydl.prepare_filename(info)
                        if format_type == "audio":
                            filename = filename.rsplit('.', 1)[0] + '.mp3'
                        
                        if not os.path.exists(filename):
                            raise DownloadError("File not created")
                        
                        file_size = os.path.getsize(filename)
                        if file_size > MAX_FILE_SIZE:
                            os.remove(filename)
                            raise FileTooLargeError(file_size, MAX_FILE_SIZE)
                        
                        return {
                            "success": True,
                            "file_path": filename,
                            "title": sanitize_filename(info.get("title", "Unknown")),
                            "duration": info.get("duration", 0),
                            "uploader": info.get("uploader", "Unknown"),
                            "thumbnail": info.get("thumbnail"),
                            "is_playlist": False,
                            "file_size": file_size
                        }
                        
            except CancelledError:
                import shutil
                if output_dir.exists():
                    shutil.rmtree(output_dir, ignore_errors=True)
                raise
            except Exception as e:
                import shutil
                if output_dir.exists():
                    shutil.rmtree(output_dir, ignore_errors=True)
                if isinstance(e, (DownloadError, FileTooLargeError, CancelledError)):
                    raise
                raise DownloadError(str(e), "unknown")


dl_manager = AdvancedDownloadManager()
