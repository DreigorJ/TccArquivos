from django.urls import path
from . import views

app_name = 'inventario_v1'

urlpatterns = [
    path("produtos/", views.ProdutosLista.as_view(), name="produtos_lista"),
    path("produtos/adicionar/", views.ProdutosAdicionar.as_view(), name="produtos_adicionar"),
    path("produtos/<int:pk>/editar/", views.ProdutosEditar.as_view(), name="produtos_editar"),
    path("produtos/<int:pk>/remover/", views.ProdutosRemover.as_view(), name="produtos_remover"),
]