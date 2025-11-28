from decimal import Decimal
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete

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
        "Uso: python manage.py reset_and_populate_v1 [--admin USER] [--password PASS] [--email EMAIL] [--noadmin] [--gerar-relatorio]\n"
        "Use --noadmin para não criar/atualizar superuser. Use --gerar-relatorio para gerar um relatório de verificação após popular."
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin", default="admin", help="Username do superuser (default: admin)")
        parser.add_argument("--password", default="admin123", help="Password do superuser (default: admin123)")
        parser.add_argument("--email", default="admin@example.com", help="E-mail do superuser (default: admin@example.com)")
        parser.add_argument("--noadmin", action="store_true", help="Não criar/atualizar superuser")
        parser.add_argument("--gerar-relatorio", action="store_true", help="Gerar relatório de verificação após popular")

    def handle(self, *args, **options):
        admin_username = options["admin"]
        admin_password = options["password"]
        admin_email = options["email"]
        skip_admin = options["noadmin"]
        gerar_relatorio_flag = options.get("gerar_relatorio", False)

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

        # Mute signals that might interfere during cleanup (post_delete/post_save)
        from django.db.models.signals import post_delete as _post_delete, post_save as _post_save

        try:
            with mute_signals([_post_delete, _post_save]):
                for model in models:
                    try:
                        model.objects.all().delete()
                        self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {model._meta.label}"))
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(f"  - Falha ao limpar {model._meta.label}: {exc}"))
        except Exception:
            # Fallback: try deleting without muting if mute fails for any reason
            for model in models:
                try:
                    model.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"  - Limpos registros de {model._meta.label}"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao limpar {model._meta.label}: {exc}"))

        # criar/atualizar superuser (muta signals para evitar handlers em outros apps)
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

        # tentar obter Categoria e TabelaProdutos (caso os modelos existam)
        Categoria = None
        try:
            Categoria = apps.get_model(app_label, "Categoria")
        except LookupError:
            Categoria = None

        TabelaProdutos = None
        try:
            TabelaProdutos = apps.get_model(app_label, "TabelaProdutos")
        except LookupError:
            TabelaProdutos = None

        # criar algumas categorias de exemplo (se o modelo existir)
        categoria_objs = {}
        if Categoria is not None:
            self.stdout.write("-> Criando categorias de exemplo...")
            categorias_amostra = [
                {"nome": "Peças", "descricao": "Peças e acessórios"},
                {"nome": "Eletrônicos", "descricao": "Equipamentos eletrônicos"},
                {"nome": "Periféricos", "descricao": "Teclados, mouses e similares"},
                {"nome": "Ferramentas", "descricao": "Ferramentas manuais e elétricas"},
            ]
            for cdata in categorias_amostra:
                try:
                    cobj, _ = Categoria.objects.get_or_create(nome=cdata["nome"], defaults={"descricao": cdata.get("descricao", "")})
                    categoria_objs[cobj.nome] = cobj
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar categoria {cdata.get('nome')}: {exc}"))
            self.stdout.write(self.style.SUCCESS(f"-> {len(categoria_objs)} categorias criadas/recuperadas."))
        else:
            self.stdout.write(self.style.WARNING("-> Modelo Categoria não encontrado — pulando criação de categorias."))

        # criar algumas tabelas de produtos (se o modelo existir)
        tabela_objs = {}
        if TabelaProdutos is not None:
            self.stdout.write("-> Criando Tabelas de Produtos de exemplo...")
            tabelas_amostra = [
                {"nome": "Principal", "descricao": "Tabela principal"},
                {"nome": "Vendas", "descricao": "Produtos disponíveis para vendas"},
                {"nome": "Peças", "descricao": "Peças e componentes"},
            ]
            for tdata in tabelas_amostra:
                try:
                    tobj, _ = TabelaProdutos.objects.get_or_create(nome=tdata["nome"], defaults={"descricao": tdata.get("descricao", "")})
                    tabela_objs[tobj.nome] = tobj
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Falha ao criar tabela {tdata.get('nome')}: {exc}"))
            self.stdout.write(self.style.SUCCESS(f"-> {len(tabela_objs)} tabelas criadas/recuperadas."))
        else:
            self.stdout.write(self.style.WARNING("-> Modelo TabelaProdutos não encontrado — pulando criação de tabelas."))

        # popular produtos de exemplo
        self.stdout.write("-> Populando Produtos de exemplo...")
        amostras = [
            {"nome": "Parafuso M6", "descricao": "Parafuso de aço inox", "quantidade": 150, "preco": Decimal("0.15"), "categoria": "Peças", "tabela": "Peças"},
            {"nome": "Porca M6", "descricao": "Porca sextavada", "quantidade": 200, "preco": Decimal("0.05"), "categoria": "Peças", "tabela": "Peças"},
            {"nome": "Arruela M6", "descricao": "Arruela lisa", "quantidade": 300, "preco": Decimal("0.02"), "categoria": "Peças", "tabela": "Peças"},
            {"nome": "Cabo USB 1m", "descricao": "Cabo USB-A para USB-B", "quantidade": 50, "preco": Decimal("5.00"), "categoria": "Periféricos", "tabela": "Principal"},
            {"nome": 'Monitor 24"', "descricao": "Monitor LED 24\"", "quantidade": 10, "preco": Decimal("420.00"), "categoria": "Eletrônicos", "tabela": "Vendas"},
            {"nome": "Teclado USB", "descricao": "Teclado membrana ABNT2", "quantidade": 25, "preco": Decimal("35.50"), "categoria": "Periféricos", "tabela": "Vendas"},
            {"nome": "Mouse Óptico", "descricao": "Mouse óptico USB", "quantidade": 40, "preco": Decimal("19.90"), "categoria": "Periféricos", "tabela": "Vendas"},
            {"nome": "Chave de Fenda", "descricao": "Chave de fenda Phillips", "quantidade": 60, "preco": Decimal("3.75"), "categoria": "Ferramentas", "tabela": "Principal"},
        ]

        produtos_objs = []
        created = 0
        for item in amostras:
            try:
                cat_name = item.pop("categoria", None)
                tabela_name = item.pop("tabela", None)
                kwargs = item.copy()
                if Categoria is not None and cat_name:
                    kwargs["categoria"] = categoria_objs.get(cat_name)
                p = Produtos.objects.create(**kwargs)
                # associar produto à tabela se existir
                if TabelaProdutos is not None and tabela_name:
                    tobj = tabela_objs.get(tabela_name)
                    if tobj is not None:
                        try:
                            p.tabelas.add(tobj)
                        except Exception:
                            # caso o campo many-to-many não exista ou algo falhe, ignorar
                            pass
                produtos_objs.append(p)
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Falha ao criar produto {item.get('nome')}: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"-> {created} produtos criados."))

        # criar um usuário operador de teste (opcional) e um visualizador
        User = get_user_model()
        usuario_operador = None
        usuario_visualizador = None
        try:
            if not User.objects.filter(username="operador").exists():
                usuario_operador = User.objects.create_user(username="operador", password="operador123", email="operador@example.com")
                self.stdout.write(self.style.SUCCESS("-> Usuário operador criado: operador / operador123"))
            else:
                usuario_operador = User.objects.get(username="operador")
                self.stdout.write(self.style.WARNING("-> Usuário operador já existia."))

            if not User.objects.filter(username="visualizador").exists():
                usuario_visualizador = User.objects.create_user(username="visualizador", password="visual123", email="visual@example.com")
                self.stdout.write(self.style.SUCCESS("-> Usuário visualizador criado: visualizador / visual123"))
            else:
                usuario_visualizador = User.objects.get(username="visualizador")
                self.stdout.write(self.style.WARNING("-> Usuário visualizador já existia."))

            # criar perfis e atribuir papeis e permissões por tabela quando aplicável
            try:
                # perfil do operador: papel operator e acesso a tabela 'Vendas' (exemplo)
                perfil_op, _ = PerfilUsuario.objects.get_or_create(usuario=usuario_operador, defaults={"papel": PerfilUsuario.ROLE_OPERATOR})
                if TabelaProdutos is not None:
                    venda_tabela = tabela_objs.get("Vendas")
                    if venda_tabela:
                        try:
                            perfil_op.tabelas_permitidas.add(venda_tabela)
                        except Exception:
                            pass

                # perfil do visualizador: papel visualizador (uso do ROLE_VISUALIZADOR se definido)
                perfil_vis, _ = PerfilUsuario.objects.get_or_create(
                    usuario=usuario_visualizador,
                    defaults={"papel": getattr(PerfilUsuario, "ROLE_VISUALIZADOR", PerfilUsuario.ROLE_OPERATOR)},
                )

                # garantir que o superuser/admin também tenha PerfilUsuario com papel 'administrador' e acesso a todas as tabelas
                if not skip_admin:
                    admin_user = User.objects.get(username=admin_username)
                    perfil_admin, created_admin = PerfilUsuario.objects.get_or_create(usuario=admin_user, defaults={"papel": PerfilUsuario.ROLE_ADMINISTRADOR})
                    if TabelaProdutos is not None:
                        try:
                            # dar acesso a todas as tabelas ao administrador
                            for t in tabela_objs.values():
                                perfil_admin.tabelas_permitidas.add(t)
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"-> Falha ao criar usuário operador/visualizador: {exc}"))

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
                        # caso a aplicação falhe, remover movimentação criada
                        try:
                            mov.delete()
                        except Exception:
                            pass
                        self.stdout.write(self.style.WARNING(f"  - Falha ao aplicar movimentação {mov}: {exc}"))
                self.stdout.write(self.style.SUCCESS(f"-> {mov_created} movimentações criadas e aplicadas."))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"-> Erro criando movimentações: {exc}"))
        else:
            self.stdout.write(self.style.WARNING("-> Nenhum produto disponível para criar movimentações."))

        # opcional: gerar relatório de verificação
        if gerar_relatorio_flag:
            try:
                # garante MEDIA_ROOT existe
                from django.conf import settings
                media_root = getattr(settings, "MEDIA_ROOT", None)
                if media_root:
                    Path(media_root).mkdir(parents=True, exist_ok=True)
                # tenta importar e gerar relatório (módulo relatorios.py)
                try:
                    from inventario_v1.relatorios import gerar_relatorio
                    self.stdout.write("-> Gerando relatório de verificação (opção --gerar-relatorio)...")
                    resultado = gerar_relatorio(pks_tabelas=None, usuario="populacao")
                    self.stdout.write(self.style.SUCCESS(f"  - Relatório gerado: {resultado.get('url_html_relativa')}"))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  - Não foi possível gerar relatório: {exc}"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - Erro ao preparar geração de relatório: {exc}"))

        self.stdout.write(self.style.NOTICE("Operação finalizada."))