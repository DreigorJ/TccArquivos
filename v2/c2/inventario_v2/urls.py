from django.urls import path
from . import views

app_name = 'inventario_v2'

urlpatterns = [
    # produtos
    path("produtos/", views.ProdutosLista.as_view(), name="produtos_lista"),
    path("produtos/adicionar/", views.ProdutosAdicionar.as_view(), name="produtos_adicionar"),
    path("produtos/<int:pk>/editar/", views.ProdutosEditar.as_view(), name="produtos_editar"),
    path("produtos/<int:pk>/remover/", views.ProdutosRemover.as_view(), name="produtos_remover"),

    # movimentações
    path("movimentacoes/", views.MovimentacaoLista.as_view(), name="movimentacoes_lista"),
    path("movimentacoes/adicionar/", views.MovimentacaoAdicionar.as_view(), name="movimentacoes_adicionar"),
    path("movimentacoes/<int:pk>/", views.MovimentacaoDetalhe.as_view(), name="movimentacoes_detalhe"),
    path("movimentacoes/<int:pk>/remover/", views.MovimentacaoRemover.as_view(), name="movimentacoes_remover"),  # nova rota de remoção
    path("produtos/<int:produto_pk>/movimentacoes/", views.ProdutoMovimentacoes.as_view(), name="produto_movimentacoes"),
]