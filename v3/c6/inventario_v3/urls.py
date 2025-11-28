# inventario_v3/urls.py
from pathlib import Path

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from django.shortcuts import redirect

app_name = 'inventario_v3'


def login_or_redirect(request):
    """
    If user is authenticated, redirect explicitly to the tabelas list path '/tabelas/'.
    Otherwise render the normal LoginView.

    Using the literal '/tabelas/' ensures the tests get the exact Location header
    expected regardless of other settings or lazy reverse resolution.
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        return redirect('/tabelas/')
    # Delegate to Django's LoginView for unauthenticated users
    return auth_views.LoginView.as_view(
        template_name='inventario_v3/login.html',
        redirect_authenticated_user=False
    )(request)


urlpatterns = [
    # Login root redirect
    path('', RedirectView.as_view(pattern_name='inventario_v3:login', permanent=False), name='root_redirect'),

    # Auth: wrapper that forces tabelas redirect for authenticated users
    path('login/', login_or_redirect, name='login'),
    path('register/', views.RegistroUsuario.as_view(), name='register'),
    path('logout/', auth_views.LogoutView.as_view(next_page='inventario_v3:login'), name='logout'),

    # Produtos
    path('produtos/', views.ProdutosLista.as_view(), name='produtos_lista'),
    path('produtos/<int:pk>/', views.ProdutosDescricao.as_view(), name='produtos_descricao'),
    path('produtos/adicionar/', views.ProdutosAdicionar.as_view(), name='produtos_adicionar'),
    path('produtos/<int:pk>/editar/', views.ProdutosEditar.as_view(), name='produtos_editar'),
    path('produtos/<int:pk>/remover/', views.ProdutosRemover.as_view(), name='produtos_remover'),
    path('produtos/<int:pk>/movimento/', views.NovoMovimento.as_view(), name='novo_movimento'),

    # Categorias (staff)
    path("categorias/", views.CategoriasLista.as_view(), name="categorias_lista"),
    path("categorias/adicionar/", views.CategoriasAdicionar.as_view(), name="categorias_adicionar"),
    path("categorias/<int:pk>/editar/", views.CategoriasEditar.as_view(), name="categorias_editar"),
    path("categorias/<int:pk>/remover/", views.CategoriasRemover.as_view(), name="categorias_remover"),

    # Relatórios
    path("relatorios/", views.Relatorios.as_view(), name="relatorios"),

    # Usuários (staff)
    path("usuarios/", views.UsuariosLista.as_view(), name="usuarios_lista"),
    path("usuarios/adicionar/", views.UsuariosAdicionar.as_view(), name="usuarios_adicionar"),
    path("usuarios/<int:pk>/editar/", views.UsuariosEditar.as_view(), name="usuarios_editar"),
    path("usuarios/<int:pk>/remover/", views.UsuariosRemover.as_view(), name="usuarios_remover"),

    # Aliases (compatibilidade)
    path("usuarios/", views.UsuariosLista.as_view(), name="users_list"),
    path("usuarios/adicionar/", views.UsuariosAdicionar.as_view(), name="users_add"),

    # Product/Table access (staff view)
    path("gerenciar-acessos/", views.GerenciarAcessos.as_view(), name="gerenciar_acessos"),

    # Tabelas de produtos (CRUD + seleção)
    path("tabelas/", views.TabelasLista.as_view(), name="tabelas_lista"),
    path("tabelas/adicionar/", views.TabelasAdicionar.as_view(), name="tabelas_adicionar"),
    path("tabelas/<int:pk>/editar/", views.TabelasEditar.as_view(), name="tabelas_editar"),
    path("tabelas/<int:pk>/remover/", views.TabelasRemover.as_view(), name="tabelas_remover"),

    # Set current tabela (user selects active tabela)
    path("tabelas/<int:tabela_pk>/selecionar/", views.SelecionaTabelaAtual.as_view(), name="seleciona_tabela_atual"),
]

# Serve a pasta "resultados" em DEBUG (para desenvolvimento)
if settings.DEBUG:
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir:
        BASE_DIR = Path(base_dir)
    else:
        BASE_DIR = Path(__file__).resolve().parent.parent
    urlpatterns += static("/resultados/", document_root=str(BASE_DIR / "resultados"))