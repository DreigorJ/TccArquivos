from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'inventario_v3'

urlpatterns = [
    path('', views.ProdutosLista.as_view(), name='produtos_lista'),
    path('produto/<int:pk>/', views.ProdutosDescricao.as_view(), name='produtos_descricao'),
    path('produto/adicionar/', views.ProdutosCriacao.as_view(), name='produtos_criacao'),
    path('produto/<int:pk>/editar/', views.ProdutosEdicao.as_view(), name='produtos_edicao'),
    path('produto/<int:pk>/apagar/', views.ProdutosRemocao.as_view(), name='produtos_remocao'),
    path('produto/<int:pk>/movimento/', views.NovoMovimento.as_view(), name='novo_movimento'),

    # auth
    path('login/', auth_views.LoginView.as_view(template_name='inventario_v3/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='inventario_v3:login'), name='logout'),
]