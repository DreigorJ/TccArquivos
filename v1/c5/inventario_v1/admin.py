from django.contrib import admin
from django.apps import apps

# Import models that always exist
from .models import Produtos, Movimentacao, PerfilUsuario, Categoria

# TabelaProdutos is opcional (compatibilidade com versões anteriores).
# Importamos com try/except para evitar ImportError quando o modelo não foi adicionado/ migrado.
try:
    from .models import TabelaProdutos  # type: ignore
except Exception:
    TabelaProdutos = None  # type: ignore


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "criado_em")
    search_fields = ("nome",)


@admin.register(Produtos)
class ProdutosAdmin(admin.ModelAdmin):
    list_display = ("nome", "quantidade", "preco", "categoria", "criado_em")
    search_fields = ("nome",)
    list_filter = ("criado_em", "categoria")


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("produto", "tipo", "quantidade", "usuario", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("produto__nome",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "papel")
    search_fields = ("usuario__username",)
    # Se TabelaProdutos existe, expomos tabelas_permitidas com filter_horizontal para facilitar edição
    if TabelaProdutos is not None:
        filter_horizontal = ("tabelas_permitidas",)
    list_filter = ("papel",)


# Registrar TabelaProdutos no admin apenas se o modelo existir
if TabelaProdutos is not None:
    @admin.register(TabelaProdutos)
    class TabelaProdutosAdmin(admin.ModelAdmin):
        list_display = ("nome", "descricao", "criado_em")
        search_fields = ("nome",)