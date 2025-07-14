from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Estoque
from .forms import EstoqueForm
from django.contrib.auth.models import User

@login_required
def estoque_gerenciar(request):
    """
    Lista estoques do usuário e redireciona para produtos_gerenciar ao selecionar um estoque.
    """
    estoques = Estoque.objects.filter(usuarios=request.user)
    estoque_id = request.GET.get('estoque_id')
    if estoque_id:
        try:
            estoque_selecionado = estoques.get(pk=estoque_id)
            return redirect('produtos_gerenciar', estoque_id=estoque_selecionado.id)
        except Estoque.DoesNotExist:
            estoque_selecionado = None
    else:
        estoque_selecionado = None
    return render(request, 'App/estoques_gerenciar.html', {
        'estoques': estoques,
        'estoque_selecionado': estoque_selecionado,
        'usuario_atual': request.user,
    })

@login_required
def estoque_create(request):
    if request.method == 'POST':
        form = EstoqueForm(request.POST, usuario_atual=request.user)
        if form.is_valid():
            estoque = form.save(commit=False)
            estoque.save()
            estoque.usuarios.add(request.user)
            for user in form.cleaned_data['usuarios']:
                estoque.usuarios.add(user)
            messages.success(request, "Estoque criado com sucesso!")
            return redirect('estoque_gerenciar')
    else:
        form = EstoqueForm(usuario_atual=request.user)
    return render(request, 'App/estoque_form.html', {
        'form': form,
        'usuario_atual': request.user,
    })

@login_required
def estoque_update(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = EstoqueForm(request.POST, instance=estoque, usuario_atual=request.user)
        if form.is_valid():
            usuarios_novos = [request.user] + list(form.cleaned_data['usuarios'])
            estoque.usuarios.set(usuarios_novos)
            # Se após atualização, não sobrou nenhum usuário, apaga o estoque
            if estoque.usuarios.count() == 0:
                estoque.delete()
                messages.success(request, "O estoque foi removido pois não há mais usuários associados.")
                return redirect('estoque_gerenciar')
            else:
                estoque.save()
                messages.success(request, "Estoque atualizado com sucesso!")
            return redirect('estoque_gerenciar')
    else:
        form = EstoqueForm(instance=estoque, usuario_atual=request.user)
    return render(request, 'App/estoque_form.html', {
        'form': form,
        'estoque': estoque,
        'usuario_atual': request.user,
    })

@login_required
def remover_usuario_do_estoque(request, estoque_id, usuario_id):
    """
    Remove um usuário do estoque.
    Se for o último usuário, apaga o estoque.
    Se o usuário remover a si mesmo, redireciona para a tela de estoques.
    """
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    usuario = get_object_or_404(User, id=usuario_id)
    if usuario in estoque.usuarios.all():
        estoque.usuarios.remove(usuario)
        # Se não sobrou usuário, apaga o estoque
        if estoque.usuarios.count() == 0:
            estoque.delete()
            messages.success(request, "O estoque foi removido pois não há mais usuários associados.")
            return redirect('estoque_gerenciar')
        # Se o usuário removeu a si mesmo, redireciona para listagem
        if usuario == request.user:
            messages.success(request, "Você saiu do estoque. Outros usuários ainda têm acesso.")
            return redirect('estoque_gerenciar')
        messages.success(request, f"Usuário {usuario.username} removido do estoque!")
    return redirect('estoque_update', estoque_id=estoque.id)

@login_required
def estoque_delete(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        estoque.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)