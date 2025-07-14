from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.http import JsonResponse
from .models import Produto, Estoque, Movimentacao
from .forms import ProdutoForm

@login_required
def produtos_gerenciar(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    produtos = estoque.produtos.select_related('categoria').all()

    # Filtros de pesquisa (adaptar conforme necessário)
    q = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '')
    marca = request.GET.get('marca', '').strip()
    metrica_id = request.GET.get('metrica', '').strip()
    marcas = produtos.exclude(marca='').values_list('marca', flat=True).distinct().order_by('marca')

    if q:
        produtos = produtos.filter(nome__icontains=q)
    if categoria_id:
        produtos = produtos.filter(categoria__id=categoria_id)
    if marca:
        produtos = produtos.filter(marca=marca)
    if metrica_id:
        produtos = produtos.filter(metrica__id=metrica_id)

    produtos_info = []
    avisos_cota_minima = []
    for produto in produtos:
        entradas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(total=models.Sum('quantidade'))['total'] or 0
        saidas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(total=models.Sum('quantidade'))['total'] or 0
        saldo = entradas - saidas
        preco_total = produto.preco * saldo
        produtos_info.append({
            'produto': produto,
            'saldo': saldo,
            'preco_total': preco_total,
        })

        # COTA MINIMA
        if produto.precisa_alerta_cota_func() and saldo < produto.cota_minima:
            avisos_cota_minima.append({
                'produto_nome': produto.nome,
                'saldo_atual': saldo,
                'minimo': produto.cota_minima,
            })

    return render(request, 'App/produtos_gerenciar.html', {
        'estoque': estoque,
        'estoque_atual': estoque,
        'produtos_info': produtos_info,
        'marcas': marcas,
        'avisos_cota_minima': avisos_cota_minima,
    })

@login_required
def produto_create(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, estoque=estoque)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.estoque = estoque
            quantidade_inicial = produto.unidades or 0
            produto.unidades = 0
            produto.save()
            if quantidade_inicial > 0:
                Movimentacao.objects.create(
                    produto=produto,
                    tipo=Movimentacao.ENTRADA,
                    quantidade=quantidade_inicial
                )
            messages.success(request, "Produto criado com sucesso!")
            return redirect('produtos_gerenciar', estoque_id=estoque.id)
    else:
        form = ProdutoForm(estoque=estoque)
    return render(request, 'App/produto_form.html', {
        'form': form,
        'estoque': estoque,
        'estoque_atual': estoque,
    })

@login_required
def produto_update(request, estoque_id, produto_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    produto = get_object_or_404(Produto, id=produto_id, estoque=estoque)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto, estoque=estoque)
        if form.is_valid():
            entradas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(total=models.Sum('quantidade'))['total'] or 0
            saidas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(total=models.Sum('quantidade'))['total'] or 0
            saldo_atual = entradas - saidas
            novo_saldo = form.cleaned_data['unidades']
            diff = novo_saldo - saldo_atual
            produto = form.save(commit=False)
            produto.save()
            if diff != 0:
                Movimentacao.objects.create(
                    produto=produto,
                    tipo=Movimentacao.ENTRADA if diff > 0 else Movimentacao.SAIDA,
                    quantidade=abs(diff)
                )
            messages.success(request, "Produto atualizado com sucesso!")
            return redirect('produtos_gerenciar', estoque_id=estoque.id)
    else:
        form = ProdutoForm(instance=produto, estoque=estoque)
    return render(request, 'App/produto_form.html', {
        'form': form,
        'estoque': estoque,
        'produto': produto,
        'estoque_atual': estoque,
    })

@login_required
def produto_delete(request, estoque_id, produto_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    produto = get_object_or_404(Produto, id=produto_id, estoque=estoque)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        produto.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)