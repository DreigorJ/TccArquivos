from django.urls import path
from . import views

app_name = "inventario_v1"

urlpatterns = [
    # produtos (existentes)
    path("produtos/", views.ProdutosLista.as_view(), name="produtos_lista"),
    path("produtos/adicionar/", views.ProdutosAdicionar.as_view(), name="produtos_adicionar"),
    path("produtos/<int:pk>/editar/", views.ProdutosEditar.as_view(), name="produtos_editar"),
    path("produtos/<int:pk>/remover/", views.ProdutosRemover.as_view(), name="produtos_remover"),

    # movimentações
    path("movimentacoes/", views.MovimentacoesLista.as_view(), name="movimentacoes_lista"),
    path("movimentacoes/adicionar/", views.MovimentacaoAdicionar.as_view(), name="movimentacoes_adicionar"),
    path("movimentacoes/<int:pk>/remover/", views.MovimentacaoRemover.as_view(), name="movimentacoes_remover"),

    # histórico por produto
    path("produtos/<int:pk>/movimentacoes/", views.ProdutosDescricao.as_view(), name="produtos_descricao"),

    # usuários / perfil
    path("usuarios/", views.UsuariosLista.as_view(), name="usuarios_lista"),
    path("usuarios/editar/", views.UsuariosEditar.as_view(), name="usuarios_editar"),
]