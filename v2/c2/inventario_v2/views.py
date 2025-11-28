from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import logging

from .models import Produtos, Movimentacao
from .forms import ProdutosFormulario, MovimentacaoFormulario

usuarioAtual = logging.getLogger(__name__)

# Produtos views (mantidas com pequena correção no filtro)
class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produtos
    template_name = "inventario_v2/produtos_lista.html"
    context_object_name = "produtos"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("nome")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(nome__icontains=q)  # corrigido para 'nome'
        return qs

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
    """
    Confirmação e remoção da movimentação.
    Observação: o método delete do modelo Movimentacao já reverte o estoque.
    Implementação segura: não chamar super().delete() antes de ter um success_url;
    aqui executamos a lógica de deleção manualmente para controlar o redirect.
    """
    model = Movimentacao
    template_name = "inventario_v2/movimentacao_remover.html"

    def post(self, request, *args, **kwargs):
        # O DeleteView chama post() para confirmar deleção; implementamos aqui
        obj = self.get_object()
        produto_pk = getattr(obj, 'produto_id', None)

        # registrar log antes da deleção (obj será excluído em seguida)
        usuarioAtual.info("Movimentação excluída: %s por %s", obj, request.user)

        # chamar o delete do objeto (o delete do modelo reverte o estoque)
        obj.delete()

        # mensagem para o usuário
        messages.success(request, "Movimentação removida e estoque revertido.")

        # redirecionar para histórico do produto quando possível
        if produto_pk:
            return redirect('inventario_v2:produto_movimentacoes', produto_pk=produto_pk)

        # fallback para lista geral de movimentações
        return redirect('inventario_v2:movimentacoes_lista')

    # também permitir GET para exibir a confirmação (DeleteView já implementa get)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


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