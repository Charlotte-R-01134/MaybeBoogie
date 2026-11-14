import json
import logging
import threading
from pathlib import Path

import yt_dlp
from django.conf import settings
from django.db import connection

from game.utils import VideoError, download_video
from .keypoints import extract_keypoints
from .models import Track, TrackStatus

log = logging.getLogger(__name__)


_one_at_a_time = threading.Semaphore(1)   # queue up track processing, one at a time
_active_lock = threading.Lock()
_active_track_ids = set()


def start_processing(track_id):
    with _active_lock:
        if track_id in _active_track_ids:
            return
        _active_track_ids.add(track_id)
    threading.Thread(target=_run, args=(track_id,), daemon=True).start()


def recover_interrupted_tracks():
    statuses = (
        TrackStatus.QUEUED,
        TrackStatus.DOWNLOADING,
        TrackStatus.ANALYSING,
        TrackStatus.SYNCING,
    )
    for track_id in Track.objects.filter(status__in=statuses).values_list("id", flat=True):
        start_processing(track_id)


def _set(track, status, progress):
    track.status, track.progress = status, progress
    track.save(update_fields=["status", "progress"])


def process_track(track):
    S = TrackStatus
    
    video_exists = bool(track.video_file and Path(track.video_file.path).exists())
    if not video_exists:
        _set(track, S.DOWNLOADING, 5)
        last = [5]

        def on_download_progress(frac): 
            pct = 5 + int(frac * 35)
            if pct >= last[0] + 3:             
                last[0] = pct  
                _set(track, S.DOWNLOADING, pct)

        download_video(track, on_download_progress)

    _set(track, S.ANALYSING, 40)
    last = [40]

    def on_pose_progress(frac):
        pct = 40 + int(frac * 50)
        if pct >= last[0] + 2:
            last[0] = pct
            _set(track, S.ANALYSING, pct)

    data = extract_keypoints(track.video_file.path, on_pose_progress)
    if not any(f["j"] for f in data["frames"]):
        raise VideoError("Couldn't find a dancer in that video. Try one with a clearly visible dancer.")

    # save file
    _set(track, S.SYNCING, 92)
    rel = f"keypoints/{track.youtube_id}.json"
    out = Path(settings.MEDIA_ROOT) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    track.keypoints_file.name = rel
    track.save(update_fields=["keypoints_file"])

    _set(track, S.READY, 100)


def _fail(track_id, message):
    t = Track.objects.filter(id=track_id).first()
    if not t:
        log.error("cannot mark missing track %s as failed: %s", track_id, message)
        return
    for f in (Path(settings.MEDIA_ROOT) / "videos").glob(f"{t.youtube_id}*"):
        f.unlink(missing_ok=True)                # remove partial or leftover files
    (Path(settings.MEDIA_ROOT) / "keypoints" / f"{t.youtube_id}.json").unlink(missing_ok=True)
    Track.objects.filter(id=track_id).update(
        status=TrackStatus.FAILED, error=message, video_file="", keypoints_file="")


def _run(track_id):
    with _one_at_a_time:
        try:
            process_track(Track.objects.get(id=track_id))
        except VideoError as e:
            _fail(track_id, str(e))
        except yt_dlp.utils.DownloadError:
            log.exception("download failed for track %s", track_id)
            _fail(track_id, "Couldn't download that video. It may be private, age-restricted or unavailable.")
        except Exception:
            log.exception("processing failed for track %s", track_id)
            _fail(track_id, "Something went wrong on our side. Try again.")
        finally:
            with _active_lock:
                _active_track_ids.discard(track_id)
            connection.close()