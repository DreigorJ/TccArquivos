from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Categoria, Estoque
from .forms import CategoriaForm

@login_required
def categorias_gerenciar(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    categorias = estoque.categorias.all()
    if request.method == 'POST':
        nome = request.POST.get('nome_categoria')
        if nome:
            Categoria.objects.create(estoque=estoque, nome=nome)
            messages.success(request, "Categoria criada com sucesso!")
            return redirect('categorias_gerenciar', estoque_id=estoque.id)
    return render(request, 'App/categorias_gerenciar.html', {
        'estoque': estoque,
        'categorias': categorias,
        'estoque_atual': estoque,
    })

@login_required
def categoria_create(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.estoque = estoque
            categoria.save()
            messages.success(request, "Categoria criada com sucesso!")
            return redirect('categorias_gerenciar', estoque_id=estoque.id)
    else:
        form = CategoriaForm()
    return render(request, 'App/categoria_form.html', {
        'form': form,
        'estoque': estoque,
        'estoque_atual': estoque
    })

@login_required
def categoria_update(request, estoque_id, categoria_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    categoria = get_object_or_404(Categoria, id=categoria_id, estoque=estoque)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria atualizada com sucesso!")
            return redirect('categorias_gerenciar', estoque_id=estoque.id)
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'App/categoria_form.html', {
        'form': form,
        'estoque': estoque,
        'categoria': categoria,
        'estoque_atual': estoque
    })

@login_required
def categoria_delete(request, estoque_id, categoria_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    categoria = get_object_or_404(Categoria, id=categoria_id, estoque=estoque)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        categoria.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)