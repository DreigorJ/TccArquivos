from django.contrib import admin
from importlib import import_module
from django.apps import apps

# Defensive import: try to import models, but tolerate missing optional models
try:
    from .models import Produto, Movimento, Categoria
    try:
        from .models import PerfilUsuario, AcessoProdutos
    except Exception:
        PerfilUsuario = None
        AcessoProdutos = None
except Exception:
    mod = import_module("inventario_v3.models")
    Produto = getattr(mod, "Produto", None)
    Movimento = getattr(mod, "Movimento", None)
    Categoria = getattr(mod, "Categoria", None)
    PerfilUsuario = getattr(mod, "PerfilUsuario", None)
    AcessoProdutos = getattr(mod, "AcessoProdutos", None)


if Produto is not None:
    @admin.register(Produto)
    class ProductAdmin(admin.ModelAdmin):
        list_display = ('nome', 'quantidade', 'preco', 'categoria')
        search_fields = ('nome',)
        list_filter = ('categoria',)


if Movimento is not None:
    @admin.register(Movimento)
    class MovementAdmin(admin.ModelAdmin):
        list_display = ('produto', 'quantidade', 'motivo', 'criado_em', 'usuario')
        list_filter = ('criado_em',)


if Categoria is not None:
    @admin.register(Categoria)
    class CategoriaAdmin(admin.ModelAdmin):
        list_display = ("nome", "ativo", "criado_em")
        search_fields = ("nome",)
        list_filter = ("ativo",)


if PerfilUsuario is not None:
    @admin.register(PerfilUsuario)
    class PerfilUsuarioAdmin(admin.ModelAdmin):
        list_display = ("usuario", "funcao", "ativo", "criado_em")
        search_fields = ("funcao", "usuario__username")
        list_filter = ("funcao", "ativo")


if AcessoProdutos is not None:
    @admin.register(AcessoProdutos)
    class AcessoProdutosAdmin(admin.ModelAdmin):
        list_display = ("usuario", "produto", "nivel", "criado_em")
        search_fields = ("nivel", "usuario__username", "produto__nome")
        list_filter = ("nivel", "usuario")