from decimal import Decimal
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

# context manager para mutar signals temporariamente
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
        "Limpa (apaga registros) apenas do app inventario_v1 e popula com dados de teste.\n"
        "Uso: python manage.py reset_and_populate_v1 [--admin USER] [--password PASS] [--email EMAIL] [--noadmin]\n"
        "Use --noadmin para não criar/atualizar superuser."
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin", default="admin", help="Username do superuser (default: admin)")
        parser.add_argument("--password", default="admin123", help="Password do superuser (default: admin123)")
        parser.add_argument("--email", default="admin@example.com", help="E-mail do superuser (default: admin@example.com)")
        parser.add_argument("--noadmin", action="store_true", help="Não criar/atualizar superuser")

    def handle(self, *args, **options):
        admin_username = options["admin"]
        admin_password = options["password"]
        admin_email = options["email"]
        skip_admin = options["noadmin"]

        app_label = "inventario_v1"

        # garantir migrações do app v1
        self.stdout.write("-> Aplicando migrações do app inventario_v1...")
        try:
            call_command("makemigrations", app_label, "--noinput")
        except Exception:
            pass
        call_command("migrate", app_label, "--noinput")

        # apagar registros apenas do app v1
        self.stdout.write("-> Apagando registros dos modelos do inventario_v1...")
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
                self.stdout.write(self.style.WARNING(f"  - Falha ao limpar {model._meta.label}: {exc}"))

        # criar/atualizar superuser (muta sinais para evitar handlers em outros apps)
        if not skip_admin:
            User = get_user_model()
            self.stdout.write("-> Criando/atualizando superuser (mutando signals durante a operação)...")
            with mute_signals([post_save]):
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

        # pegar modelos via app registry (após migrate)
        try:
            Produtos = apps.get_model(app_label, "Produtos")
            Movimentacao = apps.get_model(app_label, "Movimentacao")
            PerfilUsuario = apps.get_model(app_label, "PerfilUsuario")
        except LookupError as exc:
            self.stdout.write(self.style.ERROR(f"Erro ao obter modelos do app '{app_label}': {exc}"))
            return

        # popular produtos de exemplo
        self.stdout.write("-> Populando Produtos de exemplo...")
        amostras = [
            {"nome": "Parafuso M6", "descricao": "Parafuso de aço inox", "quantidade": 150, "preco": Decimal("0.15")},
            {"nome": "Porca M6", "descricao": "Porca sextavada", "quantidade": 200, "preco": Decimal("0.05")},
            {"nome": "Arruela M6", "descricao": "Arruela lisa", "quantidade": 300, "preco": Decimal("0.02")},
            {"nome": "Cabo USB 1m", "descricao": "Cabo USB-A para USB-B", "quantidade": 50, "preco": Decimal("5.00")},
            {"nome": 'Monitor 24"', "descricao": "Monitor LED 24\"", "quantidade": 10, "preco": Decimal("420.00")},
            {"nome": "Teclado USB", "descricao": "Teclado membrana ABNT2", "quantidade": 25, "preco": Decimal("35.50")},
            {"nome": "Mouse Óptico", "descricao": "Mouse óptico USB", "quantidade": 40, "preco": Decimal("19.90")},
        ]

        produtos_objs = []
        created = 0
        for item in amostras:
            try:
                p = Produtos.objects.create(**item)
                produtos_objs.append(p)
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao criar produto {item.get('nome')}: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"-> {created} produtos criados."))

        # criar um usuário operador de teste (opcional)
        User = get_user_model()
        usuario_operador = None
        try:
            if not User.objects.filter(username="operador").exists():
                usuario_operador = User.objects.create_user(username="operador", password="operador123", email="operador@example.com")
                self.stdout.write(self.style.SUCCESS("-> Usuário operador criado: operador / operador123"))
            else:
                usuario_operador = User.objects.get(username="operador")
                self.stdout.write(self.style.WARNING("-> Usuário operador já existia."))
            # criar perfil para operador
            try:
                PerfilUsuario.objects.get_or_create(usuario=usuario_operador, papel=PerfilUsuario.ROLE_OPERATOR)
            except Exception:
                pass
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"-> Falha ao criar usuário operador: {exc}"))

        # criar movimentações de exemplo e aplicar no estoque
        self.stdout.write("-> Criando movimentações de exemplo (aplicando no estoque)...")
        if produtos_objs:
            mov_created = 0
            try:
                mov_samples = [
                    {"produto": produtos_objs[0], "tipo": Movimentacao.TIPO_ENTRADA, "quantidade": 20, "usuario": usuario_operador, "observacao": "Reabastecimento teste"},
                    {"produto": produtos_objs[1], "tipo": Movimentacao.TIPO_SAIDA, "quantidade": 5, "usuario": usuario_operador, "observacao": "Saída teste"},
                ]
                for mdata in mov_samples:
                    mov = Movimentacao.objects.create(
                        produto=mdata["produto"],
                        tipo=mdata["tipo"],
                        quantidade=mdata["quantidade"],
                        usuario=mdata["usuario"],
                        observacao=mdata.get("observacao", ""),
                    )
                    try:
                        mov.aplicar_no_estoque()
                        mov_created += 1
                    except Exception as exc:
                        mov.delete()
                        self.stdout.write(self.style.WARNING(f"  - Falha ao aplicar movimentação {mov}: {exc}"))
                self.stdout.write(self.style.SUCCESS(f"-> {mov_created} movimentações criadas e aplicadas."))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"-> Erro criando movimentações: {exc}"))
        else:
            self.stdout.write(self.style.WARNING("-> Nenhum produto disponível para criar movimentações."))

        self.stdout.write(self.style.NOTICE("Operação finalizada."))