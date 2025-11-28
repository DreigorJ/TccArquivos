from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path

app_name = 'inventario_v3'

urlpatterns = [
    path('', views.ProdutosLista.as_view(), name='produtos_lista'),
    path('produto/<int:pk>/', views.ProdutosDescricao.as_view(), name='produtos_descricao'),
    path('produto/adicionar/', views.ProdutosAdicionar.as_view(), name='produtos_adicionar'),
    path('produto/<int:pk>/editar/', views.ProdutosEditar.as_view(), name='produtos_editar'),
    path('produto/<int:pk>/remover/', views.ProdutosRemover.as_view(), name='produtos_remover'),
    path('produto/<int:pk>/movimento/', views.NovoMovimento.as_view(), name='novo_movimento'),

    path("categorias/", views.CategoriasLista.as_view(), name="categorias_lista"),
    path("categorias/adicionar/", views.CategoriasAdicionar.as_view(), name="categorias_adicionar"),
    path("categorias/<int:pk>/editar/", views.CategoriasEditar.as_view(), name="categorias_editar"),
    path("categorias/<int:pk>/remover/", views.CategoriasRemover.as_view(), name="categorias_remover"),

    path("relatorios/", views.ReportView.as_view(), name="relatorios"),

    # auth
    path('login/', auth_views.LoginView.as_view(template_name='inventario_v3/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='inventario_v3:login'), name='logout'),
]

# Serve a pasta "resultados" em DEBUG (para desenvolvimento)
if settings.DEBUG:
    try:
        BASE_DIR = Path(settings.BASE_DIR)
    except Exception:
        BASE_DIR = Path(__file__).resolve().parent.parent
    urlpatterns += static("/resultados/", document_root=str(BASE_DIR / "resultados"))