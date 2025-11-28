# inventario_v3/apps.py
from django.apps import AppConfig


class InventarioV3Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventario_v3'

    def ready(self):
        # importa signals para registrar receivers
        import inventario_v3.signals  # noqa: F401