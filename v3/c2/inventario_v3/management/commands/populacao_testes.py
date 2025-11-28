#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.contrib.auth import get_user_model

try:
    from inventario_v3.models import Categoria, Produto, Movimento
except Exception as e:
    raise ImportError("Não foi possível importar os modelos de inventario_v3: %s" % e)


class Command(BaseCommand):
    help = 'Aplica migrations, limpa dados do app inventario_v3 e popula com dados de teste simples e idempotentes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush-all',
            action='store_true',
            help='Se fornecido, executa manage.py flush --no-input antes de popular (apaga TODOS os dados do banco).'
        )

    def handle(self, *args, **options):
        flush_all = options.get('flush_all')

        self.stdout.write('Aplicando migrations (se necessário)...')
        try:
            call_command('migrate', verbosity=1)
        except Exception as e:
            self.stderr.write('Erro ao aplicar migrations: %s' % e)
            return

        if flush_all:
            self.stdout.write(self.style.WARNING('Executando flush completo do banco (perda TOTAL de dados)...'))
            try:
                call_command('flush', '--no-input')
            except Exception as e:
                self.stderr.write('Erro ao executar flush: %s' % e)
                return

        # Limpar apenas dados do app para ficar determinístico
        self.stdout.write('Removendo dados das tabelas do app inventario_v3 (Movimento, Produto, Categoria)...')
        try:
            with transaction.atomic():
                Movimento.objects.all().delete()
                Produto.objects.all().delete()
                Categoria.objects.all().delete()
        except Exception as e:
            self.stderr.write('Erro ao apagar dados do app (continuando): %s' % e)
        else:
            self.stdout.write('Dados do app removidos.')

        # Criar superuser admin simples se não existir
        User = get_user_model()
        admin_username = 'admin'
        admin_email = 'admin@example.com'
        admin_password = 'admin'  # senha simples para testes

        if not User.objects.filter(username=admin_username).exists():
            self.stdout.write('Criando superuser de teste "%s"...' % admin_username)
            try:
                User.objects.create_superuser(admin_username, admin_email, admin_password)
            except TypeError:
                # fallback para diferentes assinaturas de create_superuser
                try:
                    User.objects.create_superuser(username=admin_username, password=admin_password)
                except Exception:
                    u = User.objects.create_user(admin_username, admin_email, admin_password)
                    u.is_staff = True
                    u.is_superuser = True
                    u.save()
            except Exception as e:
                self.stderr.write('Erro ao criar superuser: %s' % e)
        else:
            self.stdout.write('Usuário "%s" já existe. Pulando criação.' % admin_username)

        try:
            admin_user = User.objects.get(username=admin_username)
        except Exception:
            admin_user = None

        # Categorias e produtos de teste (idempotentes)
        categorias_nomes = ['Eletrônicos', 'Móveis', 'Escritório']
        categorias = {}
        for nome in categorias_nomes:
            cat, created = Categoria.objects.get_or_create(nome=nome)
            categorias[nome] = cat
            self.stdout.write('Categoria "%s": %s' % (nome, 'criada' if created else 'existia'))

        produtos_def = [
            ('Mouse Sem Fio', 'Mouse óptico sem fio', 10, Decimal('59.90'), 'Eletrônicos'),
            ('Teclado Mecânico', 'Teclado com switches', 5, Decimal('299.00'), 'Eletrônicos'),
            ('Cadeira Escritório', 'Cadeira ergonômica', 3, Decimal('499.00'), 'Móveis'),
            ('Caneta Azul (Pacote 10)', 'Pacote com 10 canetas azuis', 50, Decimal('4.90'), 'Escritório'),
        ]

        for nome, descricao, quantidade, preco, categoria_nome in produtos_def:
            categoria = categorias.get(categoria_nome)
            if categoria is None:
                self.stderr.write('Pular produto "%s": categoria "%s" ausente.' % (nome, categoria_nome))
                continue

            produto, created = Produto.objects.get_or_create(
                nome=nome,
                defaults={'descricao': descricao, 'preco': preco, 'categoria': categoria, 'quantidade': 0}
            )
            self.stdout.write('Produto "%s": %s' % (nome, 'criado' if created else 'existia'))

            # Ajustar estoque via método do modelo (idempotente: só aumenta até o nível desejado)
            try:
                produto.refresh_from_db(fields=['quantidade'])
            except Exception:
                produto = Produto.objects.get(pk=produto.pk)

            if produto.quantidade < quantidade:
                to_add = int(quantidade) - int(produto.quantidade)
                produto.change_quantidade(to_add, usuario=admin_user, motivo='População inicial')
                try:
                    produto.refresh_from_db(fields=['quantidade'])
                except Exception:
                    produto = Produto.objects.get(pk=produto.pk)
                self.stdout.write('  - Estoque ajustado para "%s": agora %s' % (produto.nome, produto.quantidade))
            else:
                self.stdout.write('  - Estoque já satisfatório para "%s": %s' % (produto.nome, produto.quantidade))

        # Movimento de saída de teste (se houver estoque)
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

        self.stdout.write(self.style.SUCCESS('População de teste finalizada.'))