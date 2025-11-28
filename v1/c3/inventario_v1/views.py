from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.apps import apps
from django.db import transaction
import logging

from .models import Produtos, Movimentacao, PerfilUsuario, Categoria
from .forms import (
    ProdutosFormulario,
    MovimentacaoFormulario,
    PerfilUsuarioFormulario,
    CategoriaFormulario,
    ConfirmForm,
)

usuarioAtual = logging.getLogger(__name__)


# Produtos views (mantidas)
class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produtos
    template_name = "inventario_v1/produtos_lista.html"
    context_object_name = "produtos"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("nome")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(nome__icontains=q)
        categoria_pk = self.request.GET.get("categoria")
        if categoria_pk:
            qs = qs.filter(categoria__pk=categoria_pk)
        return qs


class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v1/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        usuarioAtual.info("Produto criado: %s por %s", self.object, self.request.user)
        messages.success(self.request, "Produto criado com sucesso.")
        return resp


class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v1/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Produto atualizado com sucesso.")
        return resp


class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produtos
    template_name = "inventario_v1/produtos_remover.html"
    success_url = reverse_lazy("inventario_v1:produtos_lista")
    form_class = ConfirmForm  # usar ConfirmForm concreto

    def form_valid(self, form):
        obj = self.get_object()
        usuarioAtual.info("Produto excluído: %s por %s", obj, self.request.user)
        messages.success(self.request, "Produto excluído.")
        return super().form_valid(form)


# Categoria views (CRUD)
class CategoriasLista(LoginRequiredMixin, ListView):
    model = Categoria
    template_name = "inventario_v1/categorias_lista.html"
    context_object_name = "categorias"
    paginate_by = 30

    def get_queryset(self):
        return super().get_queryset().order_by("nome")


class CategoriaAdicionar(LoginRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaFormulario
    template_name = "inventario_v1/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v1:categorias_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Categoria criada com sucesso.")
        return resp


class CategoriaEditar(LoginRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaFormulario
    template_name = "inventario_v1/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v1:categorias_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Categoria atualizada com sucesso.")
        return resp


class CategoriaRemover(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = "inventario_v1/categorias_remover.html"
    success_url = reverse_lazy("inventario_v1:categorias_lista")
    form_class = ConfirmForm

    def form_valid(self, form):
        usuarioAtual.info("Categoria excluída: %s por %s", self.get_object(), self.request.user)
        messages.success(self.request, "Categoria excluída.")
        return super().form_valid(form)


# Movimentações
class MovimentacoesLista(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = "inventario_v1/movimentacoes_lista.html"
    context_object_name = "movimentacoes"
    paginate_by = 30
    ordering = ["-criado_em"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("produto", "usuario").order_by("-criado_em")
        produto_pk = self.request.GET.get("produto")
        if produto_pk:
            qs = qs.filter(produto__pk=produto_pk)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["products_list"] = Produtos.objects.all().order_by("nome")
        ctx["selected_prod"] = self.request.GET.get("produto", "")
        return ctx


class MovimentacaoAdicionar(LoginRequiredMixin, CreateView):
    model = Movimentacao
    form_class = MovimentacaoFormulario
    template_name = "inventario_v1/movimentacoes_formulario.html"
    success_url = reverse_lazy("inventario_v1:movimentacoes_lista")

    def get_initial(self):
        initial = super().get_initial()
        produto_pk = self.request.GET.get("produto")
        if produto_pk:
            initial["produto"] = produto_pk
        return initial

    def form_valid(self, form):
        mov = form.save(commit=False)
        mov.usuario = self.request.user
        mov.save()
        self.object = mov
        try:
            mov.aplicar_no_estoque()
            messages.success(self.request, "Movimentação registrada e estoque atualizado.")
        except Exception as exc:
            mov.delete()
            messages.error(self.request, f"Erro ao aplicar movimentação: {exc}")
            return super().form_invalid(form)
        usuarioAtual.info("Movimentação criada: %s por %s", mov, self.request.user)
        return redirect(self.get_success_url())


class MovimentacaoRemover(LoginRequiredMixin, DeleteView):
    model = Movimentacao
    template_name = "inventario_v1/movimentacoes_remover.html"
    success_url = reverse_lazy("inventario_v1:movimentacoes_lista")
    form_class = ConfirmForm

    def form_valid(self, form):
        obj = self.get_object()
        try:
            with transaction.atomic():
                obj.reverter_no_estoque()
                return super().form_valid(form)
        except Exception as exc:
            usuarioAtual.exception("Erro ao reverter movimentação %s: %s", getattr(obj, "pk", "N/A"), exc)
            messages.error(self.request, f"Não foi possível reverter movimentação: {exc}")
            return redirect(self.success_url)


# Histórico por produto (compatibilidade com nomes existentes)
class ProdutosDescricao(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = "inventario_v1/produtos_descricao.html"
    context_object_name = "movimentacoes"

    def get_queryset(self):
        produto_pk = self.kwargs.get("pk")
        produto = get_object_or_404(Produtos, pk=produto_pk)
        return produto.movimentacoes.select_related("usuario").order_by("-criado_em")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["produto"] = get_object_or_404(Produtos, pk=self.kwargs.get("pk"))
        return ctx


# Usuários / perfil simples (lista e editar perfil)
class UsuariosLista(LoginRequiredMixin, ListView):
    model = apps.get_model("auth", "User")
    template_name = "inventario_v1/usuarios_lista.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        User = apps.get_model("auth", "User")
        return User.objects.all().order_by("username")


class UsuariosEditar(LoginRequiredMixin, UpdateView):
    model = PerfilUsuario
    form_class = PerfilUsuarioFormulario
    template_name = "inventario_v1/usuario_formulario.html"
    success_url = reverse_lazy("inventario_v1:usuarios_lista")

    def get_object(self, queryset=None):
        perfil, created = PerfilUsuario.objects.get_or_create(usuario=self.request.user)
        return perfil

    def form_valid(self, form):
        messages.success(self.request, "Usuário atualizado.")
        return super().form_valid(form)