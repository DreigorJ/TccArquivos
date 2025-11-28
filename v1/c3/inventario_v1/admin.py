from django.contrib import admin
from .models import Produtos, Movimentacao, PerfilUsuario, Categoria

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