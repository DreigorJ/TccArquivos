# inventario_v2/management/commands/populacao_teste.py
"""
Comando de gerenciamento para limpar e popular dados de teste do app inventario_v2,
adaptado para as mudanças: TabelaProdutos + PerfilUsuario + produto.tabela.

Uso:
  python manage.py populacao_teste [--noadmin] [--admin USER] [--password PASS] [--email EMAIL]
                                   [--operator USER] [--op-password PASS] [--op-email EMAIL]
"""
from decimal import Decimal
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.db import transaction

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
        "Limpa apenas os dados do app inventario_v2 e popula Tabelas, Categorias, "
        "Produtos, Movimentacoes e Perfis de exemplo.\n"
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin", default="admin", help="Username do superuser (default: admin)")
        parser.add_argument("--password", default="admin", help="Password do superuser (default: admin)")
        parser.add_argument("--email", default="admin@example.com", help="E-mail do superuser")
        parser.add_argument("--noadmin", action="store_true", help="Não criar/atualizar superuser")
        parser.add_argument("--operator", default="operator", help="Username do operador (default: operator)")
        parser.add_argument("--op-password", default="operator123", help="Password do operador (default: operator123)")
        parser.add_argument("--op-email", default="operator@example.com", help="E-mail do operador")

    def handle(self, *args, **options):
        admin_username = options["admin"]
        admin_password = options["password"]
        admin_email = options["email"]
        skip_admin = options["noadmin"]

        operator_username = options["operator"]
        operator_password = options["op_password"]
        operator_email = options["op_email"]

        app_label = "inventario_v2"
        User = get_user_model()

        # 1) Aplicar migrações apenas do app inventario_v2 (garante esquema)
        self.stdout.write("-> Aplicando migrações do app inventario_v2 (makemigrations + migrate)...")
        try:
            call_command("makemigrations", app_label, "--noinput")
        except Exception:
            # ignora se não houver mudanças a serem feitas
            pass
        call_command("migrate", app_label, "--noinput")

        # 2) Preparar referências aos modelos (se existirem)
        Categoria = None
        Produtos = None
        Movimentacao = None
        TabelaProdutos = None
        PerfilUsuario = None

        try:
            Categoria = apps.get_model(app_label, "Categoria")
        except LookupError:
            pass
        try:
            Produtos = apps.get_model(app_label, "Produtos")
        except LookupError:
            pass
        try:
            Movimentacao = apps.get_model(app_label, "Movimentacao")
        except LookupError:
            pass
        try:
            TabelaProdutos = apps.get_model(app_label, "TabelaProdutos")
        except LookupError:
            pass
        try:
            PerfilUsuario = apps.get_model(app_label, "PerfilUsuario")
        except LookupError:
            pass

        # 3) Apagar dados na ordem segura:
        # Movimentacao -> Produtos -> TabelaProdutos -> Categoria -> PerfilUsuario
        self.stdout.write("-> Apagando dados dos modelos do inventario_v2 (ordem segura)...")
        with transaction.atomic():
            if Movimentacao:
                try:
                    Movimentacao.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS("  - Limpos registros de Movimentacao"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Movimentacao: {exc}"))
            if Produtos:
                try:
                    Produtos.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS("  - Limpos registros de Produtos"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Produtos: {exc}"))
            if TabelaProdutos:
                try:
                    TabelaProdutos.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS("  - Limpos registros de TabelaProdutos"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar TabelaProdutos: {exc}"))
            if Categoria:
                try:
                    Categoria.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS("  - Limpos registros de Categoria"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar Categoria: {exc}"))
            if PerfilUsuario:
                try:
                    PerfilUsuario.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS("  - Limpos registros de PerfilUsuario"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar PerfilUsuario: {exc}"))

        # 4) Criar/atualizar superuser (opcional). Mutar signals post_save para evitar handlers
        operator = None
        if not skip_admin:
            self.stdout.write("-> Criando/atualizando superuser (signals mutados durante a operação)...")
            with mute_signals([post_save]):
                if not User.objects.filter(username=admin_username).exists():
                    try:
                        admin = User.objects.create_superuser(admin_username, admin_email, admin_password)
                        self.stdout.write(self.style.SUCCESS(f"  - Superuser criado: {admin_username}/{admin_password}"))
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(f"  - Falha ao criar superuser: {exc}"))
                        admin = None
                else:
                    admin = User.objects.get(username=admin_username)
                    admin.set_password(admin_password)
                    admin.email = admin_email
                    admin.is_superuser = True
                    admin.is_staff = True
                    admin.save()
                    self.stdout.write(self.style.SUCCESS(f"  - Superuser atualizado: {admin_username}/{admin_password}"))
            # criar perfil ADMIN se modelo existir
            if PerfilUsuario and admin:
                try:
                    PerfilUsuario.objects.update_or_create(usuario=admin, defaults={"papel": PerfilUsuario.ROLE_ADMIN})
                except Exception:
                    pass
        else:
            self.stdout.write("-> Pulando criação/atualização de superuser (--noadmin).")
            admin = None

        # 5) Criar/atualizar usuário operador
        self.stdout.write("-> Criando/atualizando usuário operador para movimentações...")
        try:
            operator, created = User.objects.get_or_create(username=operator_username, defaults={"email": operator_email})
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
            # criar perfil OPERATOR se modelo existir
            if PerfilUsuario:
                try:
                    PerfilUsuario.objects.update_or_create(usuario=operator, defaults={"papel": PerfilUsuario.ROLE_OPERATOR})
                except Exception:
                    pass
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  - Falha ao criar/atualizar operador: {exc}"))
            operator = None

        # 6) Criar tabelas de produtos de exemplo (get_or_create)
        tabelas_amostra = [
            {"nome": "Ferragens", "descricao": "Tabela para ferragens"},
            {"nome": "Periféricos", "descricao": "Tabela para periféricos"},
            {"nome": "Cables", "descricao": "Tabela para cabos"},
        ]

        created_tables = 0
        tabela_map = {}  # nome -> objeto
        if TabelaProdutos:
            for t in tabelas_amostra:
                try:
                    owner = admin or operator  # prefer admin, senão operator
                    obj, created = TabelaProdutos.objects.get_or_create(nome=t["nome"], defaults={"descricao": t.get("descricao", ""), "owner": owner})
                    # garantir que operator tenha acesso a Periféricos e Cables for demo
                    if operator and obj.nome in ("Periféricos", "Cables"):
                        obj.acessos.add(operator)
                    tabela_map[obj.nome] = obj
                    if created:
                        created_tables += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar tabela {t.get('nome')}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created_tables} tabelas criadas/atualizadas."))

        # 7) Criar categorias de exemplo (get_or_create)
        categorias_amostra = [
            {"nome": "Ferragens", "descricao": "Parafusos, porcas, arruelas e componentes mecânicos."},
            {"nome": "Periféricos", "descricao": "Monitores, teclados, mouses e cabos."},
            {"nome": "Cables", "descricao": "Cabos e conectores variados."},
        ]

        created_cat = 0
        if Categoria:
            for c in categorias_amostra:
                try:
                    obj, created = Categoria.objects.get_or_create(nome=c["nome"], defaults={"descricao": c.get("descricao", "")})
                    if created:
                        created_cat += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar categoria {c.get('nome')}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created_cat} categorias criadas/atualizadas."))

        # 8) Criar/atualizar produtos de exemplo (update_or_create) e associar tabela/categoria
        amostras_produtos = [
            {"nome": "Parafuso M6", "descricao": "Parafuso de aço inox", "quantidade": 150, "preco": Decimal("0.15"), "categoria_nome": "Ferragens", "tabela_nome": "Ferragens"},
            {"nome": "Porca M6", "descricao": "Porca sextavada", "quantidade": 200, "preco": Decimal("0.05"), "categoria_nome": "Ferragens", "tabela_nome": "Ferragens"},
            {"nome": "Arruela M6", "descricao": "Arruela lisa", "quantidade": 300, "preco": Decimal("0.02"), "categoria_nome": "Ferragens", "tabela_nome": "Ferragens"},
            {"nome": "Cabo USB 1m", "descricao": "Cabo USB-A para USB-B", "quantidade": 50, "preco": Decimal("5.00"), "categoria_nome": "Cables", "tabela_nome": "Cables"},
            {"nome": 'Monitor 24"', "descricao": "Monitor LED 24\"", "quantidade": 10, "preco": Decimal("420.00"), "categoria_nome": "Periféricos", "tabela_nome": "Periféricos"},
            {"nome": "Teclado USB", "descricao": "Teclado membrana ABNT2", "quantidade": 25, "preco": Decimal("35.50"), "categoria_nome": "Periféricos", "tabela_nome": "Periféricos"},
            {"nome": "Mouse Óptico", "descricao": "Mouse óptico USB", "quantidade": 40, "preco": Decimal("19.90"), "categoria_nome": "Periféricos", "tabela_nome": "Periféricos"},
        ]

        created_prod = 0
        if Produtos:
            for item in amostras_produtos:
                try:
                    cat = None
                    if Categoria and item.get("categoria_nome"):
                        try:
                            cat = Categoria.objects.get(nome=item["categoria_nome"])
                        except Exception:
                            cat = None
                    tabela_obj = None
                    if TabelaProdutos and item.get("tabela_nome"):
                        tabela_obj = tabela_map.get(item["tabela_nome"])
                        # fallback lookup by name
                        if not tabela_obj:
                            try:
                                tabela_obj = TabelaProdutos.objects.get(nome=item["tabela_nome"])
                            except Exception:
                                tabela_obj = None
                    defaults = {
                        "descricao": item["descricao"],
                        "quantidade": item["quantidade"],
                        "preco": item["preco"],
                        "categoria": cat,
                        "tabela": tabela_obj,
                    }
                    obj, was_created = Produtos.objects.update_or_create(nome=item["nome"], defaults=defaults)
                    if was_created:
                        created_prod += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar/atualizar produto {item.get('nome')}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {created_prod} produtos criados/atualizados."))

        # 9) Criar movimentações de exemplo (somente se o modelo existir)
        if not Movimentacao:
            self.stdout.write(self.style.WARNING("-> Modelo 'Movimentacao' não encontrado. Pulando criação de movimentações."))
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
                    if usuario is None and admin:
                        try:
                            usuario = User.objects.get(username=admin_username)
                        except Exception:
                            usuario = None

                    Movimentacao.objects.create(
                        produto=produto,
                        tipo=m["tipo"],
                        quantidade=m["quantidade"],
                        descricao=m.get("descricao", ""),
                        usuario=usuario,
                    )
                    mov_created += 1
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar movimentação para {prod_name}: {exc}"))
                    continue

        self.stdout.write(self.style.SUCCESS(f"-> Finalizado: {mov_created} movimentações criadas."))
        self.stdout.write(self.style.SUCCESS("-> População de teste concluída."))