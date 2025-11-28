# inventario_v1/management/commands/reset_and_populate_v1.py
from decimal import Decimal
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

# Context manager para "mutar" signals (temporariamente remove receivers)
@contextmanager
def mute_signals(signals):
    original = {signal: list(signal.receivers) for signal in signals}
    try:
        for signal in signals:
            signal.receivers[:] = []
        yield
    finally:
        for signal, receivers in original.items():
            signal.receivers[:] = receivers

class Command(BaseCommand):
    help = (
        "Limpa apenas os dados do app inventario_v1 e popula com exemplos. "
        "Não altera outros apps (v3 etc.).\n"
        "Uso: python manage.py reset_and_populate_v1 [--admin USER] [--password PASS] [--email EMAIL] [--noadmin]"
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin", default="admin", help="Username do superuser (default: admin)")
        parser.add_argument("--password", default="admin", help="Password do superuser (default: admin123)")
        parser.add_argument("--email", default="admin@example.com", help="E-mail do superuser (default: admin@example.com)")
        parser.add_argument("--noadmin", action="store_true", help="Não criar/atualizar superuser (útil se preferir não mexer em usuários)")

    def handle(self, *args, **options):
        admin_username = options["admin"]
        admin_password = options["password"]
        admin_email = options["email"]
        skip_admin = options["noadmin"]

        app_label = "inventario_v1"

        # 1) Aplicar migrações apenas do app v1 (garante esquema)
        self.stdout.write("-> Aplicando migrações do app inventario_v1 (migrate inventario_v1)...")
        try:
            call_command("makemigrations", app_label, "--noinput")
        except Exception:
            # ignora se não houver mudanças a serem feitas
            pass
        call_command("migrate", app_label, "--noinput")

        # 2) Apagar apenas os registros dos modelos do inventario_v1
        self.stdout.write("-> Apagando dados dos modelos do inventario_v1...")
        try:
            app_cfg = apps.get_app_config(app_label)
        except LookupError:
            self.stdout.write(self.style.ERROR(f"App '{app_label}' não encontrado em INSTALLED_APPS."))
            return

        models = list(app_cfg.get_models())
        for model in models:
            try:
                model.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {model._meta.label}"))
            except Exception as exc:
                # não falhar por causa de um modelo problemático; só avisar
                self.stdout.write(self.style.WARNING(f"  - Falha ao limpar {model._meta.label}: {exc}"))

        # 3) Criar/atualizar superuser (opcional). Mutar sinais post_save para evitar handlers de outros apps.
        if not skip_admin:
            User = get_user_model()
            self.stdout.write("-> Criando/atualizando superuser (signals mutados durante a operação)...")
            with mute_signals([post_save]):  # evita que post_save de User dispare handlers (ex: inventario_v3)
                if not User.objects.filter(username=admin_username).exists():
                    User.objects.create_superuser(admin_username, admin_email, admin_password)
                    self.stdout.write(self.style.SUCCESS(f"  - Superuser criado: {admin_username}/{admin_password}"))
                else:
                    user = User.objects.get(username=admin_username)
                    user.set_password(admin_password)
                    user.email = admin_email
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"  - Superuser atualizado: {admin_username}/{admin_password}"))
        else:
            self.stdout.write("-> Pulando criação/atualização de superuser (--noadmin).")

        # 4) Importar modelo Produtos do inventario_v1 e popular com amostras
        try:
            Produtos = apps.get_model(app_label, "Produtos")
        except LookupError:
            self.stdout.write(self.style.ERROR("Modelo 'Produtos' não encontrado. Verifique o nome da classe e app_label."))
            return

        # Verificar tabela acessível
        try:
            Produtos.objects.exists()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Não foi possível acessar a tabela de Produtos: {exc}"))
            return

        self.stdout.write("-> Populando Produtos de exemplo (somente inventario_v1)...")
        amostras = [
            {"nome": "Parafuso M6", "descricao": "Parafuso de aço inox", "quantidade": 150, "preco": Decimal("0.15")},
            {"nome": "Porca M6", "descricao": "Porca sextavada", "quantidade": 200, "preco": Decimal("0.05")},
            {"nome": "Arruela M6", "descricao": "Arruela lisa", "quantidade": 300, "preco": Decimal("0.02")},
            {"nome": "Cabo USB 1m", "descricao": "Cabo USB-A para USB-B", "quantidade": 50, "preco": Decimal("5.00")},
            {"nome": 'Monitor 24"', "descricao": "Monitor LED 24\"", "quantidade": 10, "preco": Decimal("420.00")},
            {"nome": "Teclado USB", "descricao": "Teclado membrana ABNT2", "quantidade": 25, "preco": Decimal("35.50")},
            {"nome": "Mouse Óptico", "descricao": "Mouse óptico USB", "quantidade": 40, "preco": Decimal("19.90")},
        ]

        created = 0
        for item in amostras:
            try:
                Produtos.objects.create(**item)
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao criar {item.get('nome')}: {exc}"))
                continue

        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created} produtos criados no {app_label}."))