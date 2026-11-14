from django.db import models

# status enum
class TrackStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    DOWNLOADING = "downloading", "Downloading"
    ANALYSING = "analysing", "Analysing"
    SYNCING = "syncing", "Syncing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"

# Create your models here.
class Track(models.Model):
    youtube_id = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=TrackStatus.choices,
        default=TrackStatus.QUEUED,
    )
    progress = models.FloatField(default=0.0) # progress percentage from 0.0 to 100.0
    error = models.TextField(blank=True, null=True) # error message if status is FAILED
    bpm = models.FloatField(blank=True, null=True) # beats per minute
    offset = models.FloatField(blank=True, null=True) # offset in seconds
    keypoints_file = models.FileField(upload_to="keypoints/", blank=True, null=True) # path to keypoints file
    submitted_by = models.ForeignKey("auth.User", on_delete=models.CASCADE) # user who submitted the track, null if user is deleted
    created_at = models.DateTimeField(auto_now_add=True)