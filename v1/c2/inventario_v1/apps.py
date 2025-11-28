from django.apps import AppConfig

class InventarioV1Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventario_v1'

    def ready(self):
        # importa o módulo signals para registrar os receivers
        # import aqui evita importações circulares durante o carregamento de models
        from . import signals  # noqa: F401