from django.conf import settings
from django.apps import AppConfig
import os


class GameConfig(AppConfig):
    name = "game"

    def ready(self):
        if settings.DEBUG and os.environ.get("RUN_MAIN") != "true":
            return
        from .processing import recover_interrupted_tracks

        recover_interrupted_tracks()
