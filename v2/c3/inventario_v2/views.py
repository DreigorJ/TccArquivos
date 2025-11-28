from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import logging

from .models import Produtos, Movimentacao, Categoria
from .forms import ProdutosFormulario, MovimentacaoFormulario, CategoriaFormulario

usuarioAtual = logging.getLogger(__name__)

# Produtos views
class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produtos
    template_name = "inventario_v2/produtos_lista.html"
    context_object_name = "produtos"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("nome")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(nome__icontains=q)
        cat = self.request.GET.get("categoria")
        if cat:
            qs = qs.filter(categoria__id=cat)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # fornecer categorias para auxiliar no filtro (template pode não usar)
        context['categorias'] = Categoria.objects.all()
        return context

class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v2/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Produto criado: %s por %s", self.object, self.request.user)
        return resp

class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v2/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Produto atualizado: %s por %s", self.object, self.request.user)
        return resp

class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produtos
    template_name = "inventario_v2/produtos_remover.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        usuarioAtual.info("Produto excluído: %s por %s", obj, request.user)
        return super().delete(request, *args, **kwargs)


# Movimentações views
class MovimentacaoLista(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = "inventario_v2/movimentacao_lista.html"
    context_object_name = "movimentacoes"
    paginate_by = 25

class MovimentacaoAdicionar(LoginRequiredMixin, CreateView):
    model = Movimentacao
    form_class = MovimentacaoFormulario
    template_name = "inventario_v2/movimentacao_formulario.html"
    success_url = reverse_lazy("inventario_v2:movimentacoes_lista")

    def get_initial(self):
        initial = super().get_initial()
        produto_pk = self.request.GET.get('produto') or self.request.POST.get('produto')
        if produto_pk:
            initial['produto'] = produto_pk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        produto_pk = self.request.GET.get('produto') or self.request.POST.get('produto')
        if produto_pk:
            # restringe opção de produto ao indicado (opcional)
            form.fields['produto'].queryset = Produtos.objects.filter(pk=produto_pk)
            form.fields['produto'].initial = produto_pk
        return form

    def get_success_url(self):
        if hasattr(self, 'object') and getattr(self.object, 'produto_id', None):
            return reverse_lazy('inventario_v2:produto_movimentacoes', kwargs={'produto_pk': self.object.produto_id})
        return reverse_lazy('inventario_v2:movimentacoes_lista')

    def form_valid(self, form):
        mov = form.save(commit=False)
        mov.usuario = self.request.user
        try:
            mov.save()
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(self.request, "Movimentação registrada com sucesso.")
        usuarioAtual.info("Movimentação criada: %s por %s", mov, self.request.user)
        return redirect(self.get_success_url())

class MovimentacaoDetalhe(LoginRequiredMixin, DetailView):
    model = Movimentacao
    template_name = "inventario_v2/movimentacao_detalhe.html"
    context_object_name = "movimentacao"


class MovimentacaoRemover(LoginRequiredMixin, DeleteView):
    model = Movimentacao
    template_name = "inventario_v2/movimentacao_remover.html"

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        produto_pk = getattr(obj, 'produto_id', None)
        usuarioAtual.info("Movimentação excluída: %s por %s", obj, request.user)
        # chama o delete do modelo (que reverte o estoque)
        obj.delete()
        messages.success(request, "Movimentação removida e estoque revertido.")
        if produto_pk:
            return redirect('inventario_v2:produto_movimentacoes', produto_pk=produto_pk)
        return redirect('inventario_v2:movimentacoes_lista')

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# IMPORTANT: class name abaixo MUST match the usage in urls.py:
# ProdutoMovimentacoes  <-- mantenha exatamente este nome
class ProdutoMovimentacoes(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = "inventario_v2/produto_movimentacoes.html"
    context_object_name = "movimentacoes"
    paginate_by = 50

    def get_queryset(self):
        produto_pk = self.kwargs.get('produto_pk')
        produto = get_object_or_404(Produtos, pk=produto_pk)
        return produto.movimentacoes.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['produto'] = get_object_or_404(Produtos, pk=self.kwargs.get('produto_pk'))
        return context


# Categorias CRUD
class CategoriaLista(LoginRequiredMixin, ListView):
    model = Categoria
    template_name = "inventario_v2/categorias_lista.html"
    context_object_name = "categorias"
    paginate_by = 50

class CategoriaAdicionar(LoginRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaFormulario
    template_name = "inventario_v2/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v2:categorias_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Categoria criada: %s por %s", self.object, self.request.user)
        return resp

class CategoriaEditar(LoginRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaFormulario
    template_name = "inventario_v2/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v2:categorias_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Categoria atualizada: %s por %s", self.object, self.request.user)
        return resp

class CategoriaRemover(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = "inventario_v2/categorias_remover.html"
    success_url = reverse_lazy("inventario_v2:categorias_lista")

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        usuarioAtual.info("Categoria excluída: %s por %s", obj, request.user)
        return super().delete(request, *args, **kwargs)