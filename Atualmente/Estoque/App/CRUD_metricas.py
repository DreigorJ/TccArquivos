from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Metrica, Estoque
from .forms import MetricaForm

@login_required
def metricas_gerenciar(request, estoque_id=None):
    # Mantém o contexto do estoque atual se informado
    estoque_atual = None
    if estoque_id:
        estoque_atual = get_object_or_404(Estoque, pk=estoque_id, usuarios=request.user)
    metricas = Metrica.objects.all().order_by('-fixa', 'nome')
    if request.method == 'POST':
        nome = request.POST.get('nome_metrica')
        codigo = request.POST.get('codigo_metrica')
        if nome and codigo:
            if not Metrica.objects.filter(codigo=codigo).exists():
                Metrica.objects.create(nome=nome, codigo=codigo)
                messages.success(request, "Métrica criada com sucesso!")
            else:
                messages.error(request, "Já existe uma métrica com esse código.")
            if estoque_atual:
                return redirect('metricas_gerenciar', estoque_id=estoque_atual.id)
            else:
                return redirect('metricas_gerenciar')
    return render(request, 'App/metricas_gerenciar.html', {
        'metricas': metricas,
        'estoque_atual': estoque_atual
    })

@login_required
def metrica_create(request, estoque_id=None):
    estoque_atual = None
    if estoque_id:
        estoque_atual = get_object_or_404(Estoque, pk=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = MetricaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Métrica criada com sucesso!")
            if estoque_atual:
                return redirect('metricas_gerenciar', estoque_id=estoque_atual.id)
            else:
                return redirect('metricas_gerenciar')
    else:
        form = MetricaForm()
    return render(request, 'App/metrica_form.html', {
        'form': form,
        'estoque_atual': estoque_atual
    })

@login_required
def metrica_update(request, metrica_id, estoque_id=None):
    metrica = get_object_or_404(Metrica, id=metrica_id)
    estoque_atual = None
    if estoque_id:
        estoque_atual = get_object_or_404(Estoque, pk=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = MetricaForm(request.POST, instance=metrica)
        if form.is_valid():
            form.save()
            messages.success(request, "Métrica atualizada com sucesso!")
            if estoque_atual:
                return redirect('metricas_gerenciar', estoque_id=estoque_atual.id)
            else:
                return redirect('metricas_gerenciar')
    else:
        form = MetricaForm(instance=metrica)
    return render(request, 'App/metrica_form.html', {
        'form': form,
        'metrica': metrica,
        'estoque_atual': estoque_atual
    })

@login_required
def metrica_delete(request, metrica_id, estoque_id=None):
    metrica = get_object_or_404(Metrica, id=metrica_id)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        metrica.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)