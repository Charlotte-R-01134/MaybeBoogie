from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs
import yt_dlp
from django.conf import settings

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
MAX_VIDEO_DURATION = 10 * 60 # 10 minutes

def extract_youtube_id(url):
    url = urlparse(url)
    host = (url.hostname or "").lower().removeprefix("www.")
    vid = None
    if host == "youtu.be":
        vid = url.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if url.path == "/watch":
            vid = parse_qs(url.query).get("v", [None])[0]
        else:
            parts = url.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
                vid = parts[1]
    return vid if vid and ID_PATTERN.match(vid) else None

class VideoError(Exception):
    pass

def download_video(track, on_progress=None):
    vid = track.youtube_id
    out_dir = Path(settings.MEDIA_ROOT) / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={vid}"
    with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("is_live"):
        raise VideoError("Live videos are not supported.")
    duration = info.get("duration") or 0
    if duration > MAX_VIDEO_DURATION:
        raise VideoError("Video is too long. Maximum duration is 10 minutes.")

    track.title = info.get("title" or track.title)[:200]
    track.save(update_fields=["title"])

    def hook(d):
        if d["status"] == "downloading" and on_progress:
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total_bytes:
                on_progress(d["downloaded_bytes"] / total_bytes)

    ydl_opts = {
        "format": "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/b[height<=480]",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / f"{vid}.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    if not (out_dir / f"{vid}.mp4").exists():
        raise VideoError("Failed to download video.")

    track.video_file.name = f"videos/{vid}.mp4"
    track.save(update_fields=["video_file"])