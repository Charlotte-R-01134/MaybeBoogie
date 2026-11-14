from django.contrib import admin

from game.models import Score, Track

# Register your models here.


class AuthorAdmin(admin.ModelAdmin):
    list_display = ("youtube_id", "title", "status", "progress", "error", "bpm", "offset", "submitted_by", "created_at")
    list_filter = ("status", "submitted_by")
    search_fields = ("youtube_id", "title", "submitted_by__username")

admin.site.register(Track, AuthorAdmin)