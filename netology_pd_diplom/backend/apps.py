from django.apps import AppConfig


class BackendConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend"

    def ready(self):
        """
        Импортируем сигналы
        """
        from .signals import generate_thumbnails_async
