from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import json

from .models import Score, Track, TrackStatus
from .processing import start_processing
from .utils import extract_youtube_id

# Create your views here.

@login_required
@require_POST
def submit(request):
    vid = extract_youtube_id(request.POST.get("url", ""))
    if not vid:
        messages.error(request, "That doesn't look like a YouTube link. Paste the full video address.")
        return redirect("/")

    track, created = Track.objects.get_or_create(
        youtube_id=vid,
        defaults={"title": f"Video {vid}", "submitted_by": request.user},
    )
    if created or track.status == TrackStatus.FAILED:      # retry failed ones
        track.status, track.progress, track.error = TrackStatus.QUEUED, 0, ""
        track.save(update_fields=["status", "progress", "error"])
        start_processing(track.id)
    return redirect("track_detail", track_id=track.id)

def track_detail(request, track_id):
    return render(request, "track.html", {"track": get_object_or_404(Track, id=track_id)})

@login_required
def account(request):
    scores = Score.objects.filter(user=request.user).select_related("track")
    return render(request, "account.html", {
        "scores": scores,
        "total_plays": scores.count(),
        "best_score": scores.aggregate(best=Max("score"))["best"] or 0,
        "best_combo": scores.aggregate(best=Max("max_combo"))["best"] or 0,
    })

def play_library(request):
    tracks = Track.objects.filter(
        status=TrackStatus.READY,
        video_file__isnull=False,
    ).exclude(video_file="").annotate(best_score=Max("score__score"))
    return render(request, "play.html", {"tracks": tracks})

def play_track(request, track_id):
    track = get_object_or_404(
        Track,
        id=track_id,
        status=TrackStatus.READY,
    )
    if not track.video_file:
        return redirect("play")
    return render(request, "track.html", {"track": track})

def track_status(request, track_id):
    t = get_object_or_404(Track, id=track_id)
    return JsonResponse({
        "status": t.status, "progress": t.progress, "error": t.error, "title": t.title,
        "video_url": t.video_file.url if t.video_file else "",
        "keypoints_url": t.keypoints_file.url if t.keypoints_file else "",
    })

@login_required
@require_POST
def save_score(request, track_id):
    track = get_object_or_404(Track, id=track_id, status=TrackStatus.READY)
    try:
        data = json.loads(request.body)
        score = max(0, min(10000, int(data["score"])))
        accuracy = max(0.0, min(1.0, float(data["accuracy"])))
        max_combo = max(0, min(10000, int(data["max_combo"])))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "bad data"}, status=400)
    s = Score.objects.create(track=track, user=request.user, score=score, accuracy=accuracy, max_combo=max_combo)
    return JsonResponse({"id": s.id})