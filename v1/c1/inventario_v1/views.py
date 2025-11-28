from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
import logging

from .models import Produtos
from .forms import ProdutosFormulario

usuarioAtual = logging.getLogger(__name__)

class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produtos
    template_name = "inventario_v1/produtos_lista.html"  # corrigido (sem .html.html)
    context_object_name = "produtos"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("nome")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v1/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")  # usa o name definido no urls.py

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Produto criado: %s por %s", self.object, self.request.user)
        return resp

class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v1/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Produto atualizado: %s por %s", self.object, self.request.user)
        return resp

class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produtos
    template_name = "inventario_v1/produtos_remover.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        usuarioAtual.info("Produto excluído: %s por %s", obj, request.user)
        return super().delete(request, *args, **kwargs)