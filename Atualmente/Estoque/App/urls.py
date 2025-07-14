from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_usuario, name='login'),
    path('cadastro/', views.cadastro_usuario, name='cadastro'),
    path('configuracoes/', views.usuario_configuracao, name='usuario_configuracao'),
    path('configuracoes/deletar/', views.deletar_usuario, name='deletar_usuario'),
    path('logout/', views.logout_usuario, name='logout'),

    path('estoques/', views.estoque_gerenciar, name='estoque_gerenciar'),
    path('estoque/novo/', views.estoque_create, name='estoque_create'),
    path('estoque/<int:estoque_id>/editar/', views.estoque_update, name='estoque_update'),
    path('estoque/<int:estoque_id>/remover/', views.estoque_delete, name='estoque_delete'),

    path('estoque/<int:estoque_id>/produtos/', views.produtos_gerenciar, name='produtos_gerenciar'),
    path('estoque/<int:estoque_id>/produto/novo/', views.produto_create, name='produto_create'),
    path('estoque/<int:estoque_id>/produto/<int:produto_id>/editar/', views.produto_update, name='produto_update'),
    path('estoque/<int:estoque_id>/produto/<int:produto_id>/remover/', views.produto_delete, name='produto_delete'),

    path('categorias/<int:estoque_id>/', views.categorias_gerenciar, name='categorias_gerenciar'),
    path('categoria/<int:estoque_id>/novo/', views.categoria_create, name='categoria_create'),
    path('categoria/<int:estoque_id>/<int:categoria_id>/editar/', views.categoria_update, name='categoria_update'),
    path('categoria/<int:estoque_id>/<int:categoria_id>/remover/', views.categoria_delete, name='categoria_delete'),


    path('metricas/', views.metricas_gerenciar, name='metricas_gerenciar'),
    path('estoque/<int:estoque_id>/metricas/', views.metricas_gerenciar, name='metricas_gerenciar'),
    path('metrica/nova/', views.metrica_create, name='metrica_create'),
    path('estoque/<int:estoque_id>/metrica/nova/', views.metrica_create, name='metrica_create'),
    path('metrica/<int:metrica_id>/editar/', views.metrica_update, name='metrica_update'),
    path('metrica/<int:metrica_id>/<int:estoque_id>/editar/', views.metrica_update, name='metrica_update'),
    path('metrica/<int:metrica_id>/remover/', views.metrica_delete, name='metrica_delete'),
]