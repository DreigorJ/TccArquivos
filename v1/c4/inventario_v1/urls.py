from django.urls import path
from . import views

app_name = "inventario_v1"

urlpatterns = [
    # sobrescreve/expõe nome 'login' para garantir redirect_authenticated_user durante testes
    path("login/", views.LoginViewRedirect.as_view(), name="login"),

    # produtos
    path("produtos/", views.ProdutosLista.as_view(), name="produtos_lista"),
    path("produtos/adicionar/", views.ProdutosAdicionar.as_view(), name="produtos_adicionar"),
    path("produtos/<int:pk>/editar/", views.ProdutosEditar.as_view(), name="produtos_editar"),
    path("produtos/<int:pk>/remover/", views.ProdutosRemover.as_view(), name="produtos_remover"),

    # categorias
    path("categorias/", views.CategoriasLista.as_view(), name="categorias_lista"),
    path("categorias/adicionar/", views.CategoriaAdicionar.as_view(), name="categorias_adicionar"),
    path("categorias/<int:pk>/editar/", views.CategoriaEditar.as_view(), name="categorias_editar"),
    path("categorias/<int:pk>/remover/", views.CategoriaRemover.as_view(), name="categorias_remover"),

    # movimentações
    path("movimentacoes/", views.MovimentacoesLista.as_view(), name="movimentacoes_lista"),
    path("movimentacoes/adicionar/", views.MovimentacaoAdicionar.as_view(), name="movimentacoes_adicionar"),
    path("movimentacoes/<int:pk>/remover/", views.MovimentacaoRemover.as_view(), name="movimentacoes_remover"),

    # relatórios (gráficos)
    path("relatorios/", views.Relatorios.as_view(), name="relatorios"),

    # histórico por produto
    path("produtos/<int:pk>/movimentacoes/", views.ProdutosDescricao.as_view(), name="produtos_descricao"),

    # usuários / perfil
    path("usuarios/", views.UsuariosLista.as_view(), name="usuarios_lista"),
    # rota para admin editar perfil de outro usuário (opcional)
    path("usuarios/<int:pk>/editar/", views.UsuariosEditar.as_view(), name="usuario_editar_admin"),
    # rota para editar o próprio perfil (mantida)
    path("usuarios/editar/", views.UsuariosEditar.as_view(), name="usuarios_editar"),

    # registro público (antes de logar)
    path("registrar/", views.RegistroView.as_view(), name="registrar"),
]