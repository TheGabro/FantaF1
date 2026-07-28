from django.apps import AppConfig


class FantaappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fantaApp'

    def ready(self):
        from .django_compat import apply_python314_django42_context_copy_patch

        apply_python314_django42_context_copy_patch()
