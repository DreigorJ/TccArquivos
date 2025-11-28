# inventario_v2/management/commands/populacao_teste.py
from decimal import Decimal
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

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
        "Limpa apenas os dados do app inventario_v2, popula Categorias, Produtos e Movimentacoes de exemplo.\n"
        "Uso: python manage.py populacao_teste [--admin USER] [--password PASS] [--email EMAIL] "
        "[--noadmin] [--operator USER] [--op-password PASS] [--op-email EMAIL]\n"
        "Observação: o comando aplica migrações apenas do app inventario_v2 (makemigrations+migrate)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin", default="admin", help="Username do superuser (default: admin)")
        parser.add_argument("--password", default="admin", help="Password do superuser (default: admin)")
        parser.add_argument("--email", default="admin@example.com", help="E-mail do superuser (default: admin@example.com)")
        parser.add_argument("--noadmin", action="store_true", help="Não criar/atualizar superuser")
        parser.add_argument("--operator", default="operator", help="Username do operador (default: operator)")
        parser.add_argument("--op-password", default="operator123", help="Password do operador (default: operator123)")
        parser.add_argument("--op-email", default="operator@example.com", help="E-mail do operador (default: operator@example.com)")

    def handle(self, *args, **options):
        admin_username = options["admin"]
        admin_password = options["password"]
        admin_email = options["email"]
        skip_admin = options["noadmin"]

        operator_username = options["operator"]
        operator_password = options["op_password"]
        operator_email = options["op_email"]

        app_label = "inventario_v2"

        # 1) Aplicar migrações apenas do app inventario_v2 (garante esquema)
        self.stdout.write("-> Aplicando migrações do app inventario_v2 (makemigrations + migrate)...")
        try:
            call_command("makemigrations", app_label, "--noinput")
        except Exception:
            # ignora se não houver mudanças a serem feitas
            pass
        call_command("migrate", app_label, "--noinput")

        # 2) Apagar apenas os registros dos modelos do inventario_v2
        #    Importante: apagar Movimentacao antes de Produtos (Movimentacao tem FK PROTECT/PROTECT-like)
        self.stdout.write("-> Apagando dados dos modelos do inventario_v2 (ordem segura)...")
        try:
            Categoria = apps.get_model(app_label, "Categoria")
        except LookupError:
            Categoria = None
        try:
            Movimentacao = apps.get_model(app_label, "Movimentacao")
        except LookupError:
            Movimentacao = None
        try:
            Produtos = apps.get_model(app_label, "Produtos")
        except LookupError:
            Produtos = None

        # Deletar em ordem segura: Movimentacao -> Produtos -> Categoria
        if Movimentacao:
            try:
                Movimentacao.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {app_label}.Movimentacao"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Movimentacao: {exc}"))
        if Produtos:
            try:
                Produtos.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {app_label}.Produtos"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Produtos: {exc}"))
        if Categoria:
            try:
                Categoria.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {app_label}.Categoria"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Categoria: {exc}"))

        # 3) Criar/atualizar superuser (opcional). Mutar signals post_save para evitar handlers de outros apps.
        User = get_user_model()
        if not skip_admin:
            self.stdout.write("-> Criando/atualizando superuser (signals mutados durante a operação)...")
            with mute_signals([post_save]):  # evita que post_save de User dispare handlers (ex: inventario_v2)
                if not User.objects.filter(username=admin_username).exists():
                    User.objects.create_superuser(admin_username, admin_email, admin_password)
                    self.stdout.write(self.style.SUCCESS(f"  - Superuser criado: {admin_username}/{admin_password}"))
                else:
                    user = User.objects.get(username=admin_username)
                    user.set_password(admin_password)
                    user.email = admin_email
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"  - Superuser atualizado: {admin_username}/{admin_password}"))
        else:
            self.stdout.write("-> Pulando criação/atualização de superuser (--noadmin).")

        # 4) Criar/atualizar usuário operador (usado como usuario das movimentações)
        self.stdout.write("-> Criando/atualizando usuário operador para movimentações...")
        try:
            operator, created = User.objects.get_or_create(username=operator_username, defaults={
                "email": operator_email,
            })
            if created:
                operator.set_password(operator_password)
                operator.is_staff = True
                operator.save()
                self.stdout.write(self.style.SUCCESS(f"  - Operador criado: {operator_username}/{operator_password}"))
            else:
                operator.set_password(operator_password)
                operator.email = operator_email
                operator.is_staff = True
                operator.save()
                self.stdout.write(self.style.SUCCESS(f"  - Operador atualizado: {operator_username}/{operator_password}"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  - Falha ao criar/atualizar operador: {exc}"))
            operator = None

        # 5) Criar categorias de exemplo (usar get_or_create para evitar duplicação em re-runs)
        categorias_amostra = [
            {"nome": "Ferragens", "descricao": "Parafusos, porcas, arruelas e componentes mecânicos."},
            {"nome": "Periféricos", "descricao": "Monitores, teclados, mouses e cabos."},
            {"nome": "Cables", "descricao": "Cabos e conectores variados."},
        ]

        created_cat = 0
        if Categoria:
            for c in categorias_amostra:
                try:
                    obj, created = Categoria.objects.get_or_create(nome=c["nome"], defaults={"descricao": c["descricao"]})
                    if created:
                        created_cat += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar categoria {c.get('nome')}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created_cat} categorias criadas no {app_label}."))

        # 6) Criar Produtos de exemplo (usar update_or_create para evitar duplicação)
        amostras = [
            {"nome": "Parafuso M6", "descricao": "Parafuso de aço inox", "quantidade": 150, "preco": Decimal("0.15"), "categoria_nome": "Ferragens"},
            {"nome": "Porca M6", "descricao": "Porca sextavada", "quantidade": 200, "preco": Decimal("0.05"), "categoria_nome": "Ferragens"},
            {"nome": "Arruela M6", "descricao": "Arruela lisa", "quantidade": 300, "preco": Decimal("0.02"), "categoria_nome": "Ferragens"},
            {"nome": "Cabo USB 1m", "descricao": "Cabo USB-A para USB-B", "quantidade": 50, "preco": Decimal("5.00"), "categoria_nome": "Cables"},
            {"nome": 'Monitor 24"', "descricao": "Monitor LED 24\"", "quantidade": 10, "preco": Decimal("420.00"), "categoria_nome": "Periféricos"},
            {"nome": "Teclado USB", "descricao": "Teclado membrana ABNT2", "quantidade": 25, "preco": Decimal("35.50"), "categoria_nome": "Periféricos"},
            {"nome": "Mouse Óptico", "descricao": "Mouse óptico USB", "quantidade": 40, "preco": Decimal("19.90"), "categoria_nome": "Periféricos"},
        ]

        created = 0
        if Produtos:
            for item in amostras:
                try:
                    cat = None
                    if Categoria and item.get("categoria_nome"):
                        try:
                            cat = Categoria.objects.get(nome=item["categoria_nome"])
                        except Exception:
                            cat = None
                    defaults = {
                        "descricao": item["descricao"],
                        "quantidade": item["quantidade"],
                        "preco": item["preco"],
                        "categoria": cat,
                    }
                    # update_or_create evita duplicação em re-runs
                    obj, was_created = Produtos.objects.update_or_create(nome=item["nome"], defaults=defaults)
                    if was_created:
                        created += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar/atualizar {item.get('nome')}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created} produtos criados/atualizados no {app_label}."))

        # 7) Criar Movimentacoes de exemplo (se o modelo existir)
        if not Movimentacao:
            self.stdout.write(self.style.WARNING("Modelo 'Movimentacao' não encontrado. Pulando criação de movimentações."))
            return

        self.stdout.write("-> Criando movimentações de exemplo...")
        amostras_mov = {
            "Parafuso M6": [
                {"tipo": Movimentacao.TIPO_SAIDA, "quantidade": 20, "descricao": "Uso em montagem A"},
                {"tipo": Movimentacao.TIPO_ENTRADA, "quantidade": 50, "descricao": "Reabastecimento fornecedor X"},
            ],
            "Cabo USB 1m": [
                {"tipo": Movimentacao.TIPO_SAIDA, "quantidade": 5, "descricao": "Venda online"},
                {"tipo": Movimentacao.TIPO_ENTRADA, "quantidade": 10, "descricao": "Compra estoque"},
            ],
            'Monitor 24"': [
                {"tipo": Movimentacao.TIPO_SAIDA, "quantidade": 2, "descricao": "Devolução cliente (retirada)"},
            ],
            "Teclado USB": [
                {"tipo": Movimentacao.TIPO_SAIDA, "quantidade": 3, "descricao": "Venda física"},
            ],
        }

        mov_created = 0
        for prod_name, movs in amostras_mov.items():
            # Use filter().first() para evitar MultipleObjectsReturned; preferir produto único
            try:
                produto = Produtos.objects.filter(nome=prod_name).first()
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Erro ao buscar produto {prod_name}: {exc}"))
                produto = None

            if not produto:
                self.stdout.write(self.style.WARNING(f"  - Produto não encontrado para movimentação: {prod_name}"))
                continue

            for m in movs:
                try:
                    usuario = operator
                    if usuario is None:
                        try:
                            usuario = User.objects.get(username=admin_username)
                        except Exception:
                            usuario = None

                    Movimentacao.objects.create(
                        produto=produto,
                        tipo=m["tipo"],
                        quantidade=m["quantidade"],
                        descricao=m.get("descricao", ""),
                        usuario=usuario
                    )
                    mov_created += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar movimentação para {prod_name}: {exc}"))
                    continue

        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {mov_created} movimentações criadas no {app_label}."))
        self.stdout.write(self.style.SUCCESS("-> População de teste concluída."))