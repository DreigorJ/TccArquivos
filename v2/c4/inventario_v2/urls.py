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
    path("movimentacoes/<int:pk>/remover/", views.MovimentacaoRemover.as_view(), name="movimentacoes_remover"),

    # histórico de produto
    path("produtos/<int:produto_pk>/movimentacoes/", views.ProdutoMovimentacoes.as_view(), name="produto_movimentacoes"),

    # categorias
    path("categorias/", views.CategoriaLista.as_view(), name="categorias_lista"),
    path("categorias/adicionar/", views.CategoriaAdicionar.as_view(), name="categorias_adicionar"),
    path("categorias/<int:pk>/editar/", views.CategoriaEditar.as_view(), name="categorias_editar"),
    path("categorias/<int:pk>/remover/", views.CategoriaRemover.as_view(), name="categorias_remover"),

    # relatórios
    path("relatorios/", views.RelatoriosIndex.as_view(), name="relatorios_index"),
    path("relatorios/produto/<int:produto_pk>/", views.RelatorioProduto.as_view(), name="relatorio_produto"),
    path("relatorios/api/produto_movimentacoes/", views.api_produto_movimentacoes, name="api_produto_movimentacoes"),
]