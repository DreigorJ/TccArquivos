from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import  CustomUserCreationForm

from .CRUD_estoques import estoque_gerenciar, estoque_create, estoque_update, estoque_delete
from .CRUD_produtos import produtos_gerenciar, produto_create, produto_update, produto_delete
from .CRUD_categorias import categorias_gerenciar, categoria_create, categoria_update, categoria_delete
from .CRUD_metricas import metricas_gerenciar, metrica_create, metrica_update, metrica_delete

def login_usuario(request):
    if request.user.is_authenticated:
        return redirect('estoque_gerenciar')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('estoque_gerenciar')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    else:
        form = AuthenticationForm()
    return render(request, 'App/login.html', {'form': form})

def cadastro_usuario(request):
    if request.user.is_authenticated:
        return redirect('estoque_gerenciar')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('estoque_gerenciar')
        else:
            messages.error(request, 'Corrija os erros abaixo.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'App/cadastro_usuario.html', {'form': form})

@login_required
def usuario_configuracao(request):
    aba = request.GET.get('aba', 'dados')  # 'dados', 'privacidade', 'deletar'
    context = {'aba': aba}
    return render(request, 'App/configuracao_usuario.html', context)

@login_required
def logout_usuario(request):
    logout(request)
    return redirect('login')

@login_required
def deletar_usuario(request):
    if request.method == 'POST':
        user = request.user
        estoques = user.estoques.all()
        for estoque in estoques:
            if estoque.usuarios.count() > 1:
                estoque.usuarios.remove(user)
            else:
                estoque.delete()
        logout(request)
        user.delete()
        messages.success(request, "Sua conta foi deletada com sucesso.")
        return redirect('login')
    return redirect('usuario_configuracao')
