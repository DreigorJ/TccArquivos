#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model

try:
    from inventario_v3.models import Categoria, Produto, Movimento
except Exception as e:
    raise ImportError("Não foi possível importar os modelos de inventario_v3: %s" % e)


class Command(BaseCommand):
    help = (
        "Zera o banco de dados (flush) e popula com dados de teste.\n"
        "ATENÇÃO: este comando apagará TODOS os dados do banco (tabelas de auth, sessões, etc.)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-migrate',
            action='store_true',
            help='Não executar migrate após o flush (útil se você já tem o schema pronto).'
        )
        parser.add_argument(
            '--admin-pass',
            type=str,
            default='admin',
            help='Senha do superuser criado para testes (padrão: "admin").'
        )
        parser.add_argument(
            '--reports',
            action='store_true',
            help='Executa o comando gerar_relatorio ao final para criar relatórios.'
        )

    def handle(self, *args, **options):
        no_migrate = options.get('no_migrate')
        admin_password = options.get('admin_pass') or 'admin'
        do_reports = options.get('reports')

        # 0) AVISO e flush total do banco
        self.stdout.write(self.style.WARNING('Executando FLUSH completo do banco de dados (perda TOTAL de dados).'))
        try:
            # --no-input para não perguntar confirmação
            call_command('flush', '--no-input')
            self.stdout.write(self.style.SUCCESS('Flush concluído. Banco limpo.'))
        except Exception as e:
            self.stderr.write('Erro ao executar flush: %s' % e)
            # Se o flush falhar, abortar para evitar populacões parciais
            return

        # 1) Aplicar migrations (a menos que pedido para pular)
        if not no_migrate:
            self.stdout.write('Aplicando migrations...')
            try:
                call_command('migrate', verbosity=1)
            except Exception as e:
                self.stderr.write('Erro ao aplicar migrations: %s' % e)
                return
        else:
            self.stdout.write('Pulando migrate por opção --no-migrate (assume schema já aplicado).')

        # 2) Criar superuser admin simples
        User = get_user_model()
        admin_username = 'admin'
        admin_email = 'admin@example.com'

        try:
            if not User.objects.filter(username=admin_username).exists():
                self.stdout.write('Criando superuser de teste "%s"...' % admin_username)
                try:
                    User.objects.create_superuser(admin_username, admin_email, admin_password)
                except TypeError:
                    # diferents assinaturas
                    try:
                        User.objects.create_superuser(username=admin_username, password=admin_password)
                    except Exception:
                        u = User.objects.create_user(admin_username, admin_email, admin_password)
                        u.is_staff = True
                        u.is_superuser = True
                        u.save()
                except Exception as e:
                    self.stderr.write('Erro ao criar superuser: %s' % e)
                    # continuar mesmo que falhe (p.ex. custom user model diferente)
            else:
                self.stdout.write('Usuário "%s" já existe. Pulando criação.' % admin_username)
        except Exception as e:
            # situação atípica (ex: custom user manager com side effects) — logar e prosseguir
            self.stderr.write('Aviso ao checar/criar superuser: %s' % e)

        try:
            admin_user = User.objects.filter(username=admin_username).first()
        except Exception:
            admin_user = None

        # 3) População: categorias e produtos
        categorias_nomes = [
            {"nome": "Eletrônicos", "descricao": "Categoria de eletrônicos", "ativo": True},
            {"nome": "Móveis", "descricao": "Móveis e mobiliário", "ativo": True},
            {"nome": "Escritório", "descricao": "Produtos para escritório", "ativo": True},
        ]
        categorias = {}
        for info in categorias_nomes:
            try:
                with transaction.atomic():
                    cat, created = Categoria.objects.get_or_create(
                        nome=info["nome"],
                        defaults={"descricao": info.get("descricao", ""), "ativo": info.get("ativo", True)}
                    )
                    categorias[info["nome"]] = cat
                    self.stdout.write('Categoria "%s": %s' % (info["nome"], 'criada' if created else 'existia'))
            except IntegrityError as e:
                self.stderr.write('Erro ao criar Categoria "%s": %s' % (info["nome"], e))
                # tentar recuperar existente
                cat = Categoria.objects.filter(nome=info["nome"]).first()
                if cat:
                    categorias[info["nome"]] = cat

        produtos_def = [
            ("Mouse Sem Fio", "Mouse óptico sem fio", 10, Decimal("59.90"), "Eletrônicos"),
            ("Teclado Mecânico", "Teclado com switches", 5, Decimal("299.00"), "Eletrônicos"),
            ("Cadeira Escritório", "Cadeira ergonômica", 3, Decimal("499.00"), "Móveis"),
            ("Caneta Azul (Pacote 10)", "Pacote com 10 canetas azuis", 50, Decimal("4.90"), "Escritório"),
        ]

        for nome, descricao, quantidade, preco, categoria_nome in produtos_def:
            categoria = categorias.get(categoria_nome)
            if categoria is None:
                self.stderr.write('Pular produto "%s": categoria "%s" ausente.' % (nome, categoria_nome))
                continue

            try:
                with transaction.atomic():
                    produto, created = Produto.objects.get_or_create(
                        nome=nome,
                        defaults={"descricao": descricao, "preco": preco, "categoria": categoria, "quantidade": 0}
                    )
                    self.stdout.write('Produto "%s": %s' % (nome, 'criado' if created else 'existia'))
            except IntegrityError as e:
                self.stderr.write('Erro ao criar Produto "%s": %s' % (nome, e))
                produto = Produto.objects.filter(nome=nome).first()
                if not produto:
                    continue

            # Ajustar estoque via Movimento (entrada) se necessário
            try:
                produto.refresh_from_db(fields=['quantidade'])
            except Exception:
                produto = Produto.objects.get(pk=produto.pk)

            if produto.quantidade < quantidade:
                to_add = int(quantidade) - int(produto.quantidade)
                mov = Movimento(
                    produto=produto,
                    tipo_movimento=Movimento.MOV_ENT,
                    quantidade=to_add,
                    motivo='População inicial',
                    usuario=admin_user
                )
                try:
                    mov.save()
                    produto.refresh_from_db()
                    self.stdout.write('  - Estoque ajustado para "%s": agora %s' % (produto.nome, produto.quantidade))
                except Exception as e:
                    self.stderr.write('  - Erro ao criar movimento para "%s": %s' % (produto.nome, e))
            else:
                self.stdout.write('  - Estoque já satisfatório para "%s": %s' % (produto.nome, produto.quantidade))

        # 4) Movimento de saída de teste (se houver estoque)
        mouse = Produto.objects.filter(nome='Mouse Sem Fio').first()
        if mouse and mouse.quantidade >= 1:
            try:
                mov_saida = Movimento(produto=mouse, tipo_movimento=Movimento.MOV_SAI, quantidade=1,
                                      motivo='Teste de saída', usuario=admin_user)
                mov_saida.save()
                try:
                    mouse.refresh_from_db(fields=['quantidade'])
                except Exception:
                    mouse = Produto.objects.get(pk=mouse.pk)
                self.stdout.write('Movimento de saída criado para "%s". Estoque agora: %s' % (mouse.nome, mouse.quantidade))
            except Exception as e:
                self.stderr.write('Erro ao criar movimento de saída de teste: %s' % e)
        else:
            self.stdout.write('Não há estoque suficiente em "Mouse Sem Fio" para criar movimento de saída de teste.')

        # 5) Opcional: gerar relatórios
        if do_reports:
            out = "resultados/reports"
            try:
                self.stdout.write("Gerando relatórios em %s ..." % out)
                call_command("gerar_relatorio", out=out)
            except Exception as e:
                self.stderr.write("Erro ao executar gerar_relatorio: %s" % e)

        self.stdout.write(self.style.SUCCESS('População de teste finalizada.'))