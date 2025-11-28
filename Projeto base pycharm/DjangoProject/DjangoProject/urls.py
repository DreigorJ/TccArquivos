from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # delegado ao app inventario_v3 (que registra 'login/' e outros nomes no seu namespace)
    path('', include('inventario_v3.urls')),
]