from django.contrib import admin
from .models import Produto, Movimento, Categoria

@admin.register(Produto)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quantidade', 'preco', 'categoria')
    search_fields = ('nome',)
    list_filter = ('categoria',)

@admin.register(Movimento)
class MovementAdmin(admin.ModelAdmin):
    list_display = ('produto', 'quantidade', 'motivo', 'criado_em', 'usuario')
    list_filter = ('criado_em',)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)