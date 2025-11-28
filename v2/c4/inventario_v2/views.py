from datetime import timedelta
from pathlib import Path
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    TemplateView,
)

from .forms import CategoriaFormulario, MovimentacaoFormulario, ProdutosFormulario
from .models import Categoria, Movimentacao, Produtos

logger = logging.getLogger(__name__)


# -------------------
# Produtos (CRUD)
# -------------------
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
        context["categorias"] = Categoria.objects.all()
        return context


class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v2/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        logger.info("Produto criado: %s por %s", self.object, self.request.user)
        return resp


class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produtos
    form_class = ProdutosFormulario
    template_name = "inventario_v2/produtos_formulario.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        logger.info("Produto atualizado: %s por %s", self.object, self.request.user)
        return resp


class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produtos
    template_name = "inventario_v2/produtos_remover.html"
    success_url = reverse_lazy("inventario_v2:produtos_lista")

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        logger.info("Produto excluído: %s por %s", obj, request.user)
        return super().delete(request, *args, **kwargs)


# -------------------
# Movimentações (CRUD)
# -------------------
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
        produto_pk = self.request.GET.get("produto") or self.request.POST.get("produto")
        if produto_pk:
            initial["produto"] = produto_pk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        produto_pk = self.request.GET.get("produto") or self.request.POST.get("produto")
        if produto_pk:
            form.fields["produto"].queryset = Produtos.objects.filter(pk=produto_pk)
            form.fields["produto"].initial = produto_pk
        return form

    def get_success_url(self):
        if hasattr(self, "object") and getattr(self.object, "produto_id", None):
            return reverse_lazy("inventario_v2:produto_movimentacoes", kwargs={"produto_pk": self.object.produto_id})
        return reverse_lazy("inventario_v2:movimentacoes_lista")

    def form_valid(self, form):
        mov = form.save(commit=False)
        mov.usuario = self.request.user
        try:
            mov.save()
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Movimentação registrada com sucesso.")
        logger.info("Movimentação criada: %s por %s", mov, self.request.user)
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
        produto_pk = getattr(obj, "produto_id", None)
        logger.info("Movimentação excluída: %s por %s", obj, request.user)
        # chama delete do modelo (que reverte o estoque)
        obj.delete()
        messages.success(request, "Movimentação removida e estoque revertido.")
        if produto_pk:
            return redirect("inventario_v2:produto_movimentacoes", produto_pk=produto_pk)
        return redirect("inventario_v2:movimentacoes_lista")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# -------------------
# Histórico de um produto
# -------------------
class ProdutoMovimentacoes(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = "inventario_v2/produto_movimentacoes.html"
    context_object_name = "movimentacoes"
    paginate_by = 50

    def get_queryset(self):
        produto_pk = self.kwargs.get("produto_pk")
        produto = get_object_or_404(Produtos, pk=produto_pk)
        return produto.movimentacoes.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["produto"] = get_object_or_404(Produtos, pk=self.kwargs.get("produto_pk"))
        return context


# -------------------
# Categorias (CRUD)
# -------------------
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
        logger.info("Categoria criada: %s por %s", self.object, self.request.user)
        return resp


class CategoriaEditar(LoginRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaFormulario
    template_name = "inventario_v2/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v2:categorias_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        logger.info("Categoria atualizada: %s por %s", self.object, self.request.user)
        return resp


class CategoriaRemover(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = "inventario_v2/categorias_remover.html"
    success_url = reverse_lazy("inventario_v2:categorias_lista")

    # moved custom deletion logic to form_valid to avoid DeleteViewCustomDeleteWarning
    def form_valid(self, form):
        obj = self.get_object()
        logger.info("Categoria excluída: %s por %s", obj, self.request.user)
        # super().form_valid will call delete() internally for DeleteView/FormMixin
        return super().form_valid(form)


# -------------------
# Relatórios (gráficos)
# -------------------
class RelatoriosIndex(LoginRequiredMixin, TemplateView):
    template_name = "inventario_v2/relatorios_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["produtos"] = Produtos.objects.all().order_by("nome")
        context["categorias"] = Categoria.objects.all().order_by("nome")

        rel_files = []
        media_root = getattr(settings, "MEDIA_ROOT", None)
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if media_root:
            rel_dir = Path(media_root) / "relatorios"
            if rel_dir.exists():
                for p in sorted(rel_dir.iterdir()):
                    if p.is_file():
                        rel_files.append(
                            {
                                "name": p.name,
                                "url": f"{media_url.rstrip('/')}/relatorios/{p.name}",
                            }
                        )
        context["relatorios_files"] = rel_files
        return context


class RelatorioProduto(LoginRequiredMixin, TemplateView):
    template_name = "inventario_v2/relatorio_produto.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produto_pk = self.kwargs.get("produto_pk")
        produto = get_object_or_404(Produtos, pk=produto_pk)
        context["produto"] = produto
        end = timezone.now().date()
        start = end - timedelta(days=30)
        context["default_start"] = start.isoformat()
        context["default_end"] = end.isoformat()
        return context


@login_required
def api_produto_movimentacoes(request):
    produto_pk = request.GET.get("produto")
    if not produto_pk:
        return JsonResponse({"error": "Parâmetro produto é obrigatório."}, status=400)

    # parse de datas
    try:
        start_str = request.GET.get("start")
        end_str = request.GET.get("end")
        if start_str:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
        else:
            start = timezone.now().date() - timedelta(days=30)
        if end_str:
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        else:
            end = timezone.now().date()
    except Exception:
        return JsonResponse({"error": "Formato de data inválido. Use YYYY-MM-DD."}, status=400)

    if start > end:
        return JsonResponse({"error": "start cannot be after end date."}, status=400)

    qs = (
        Movimentacao.objects.filter(
            produto_id=produto_pk,
            criado_em__date__gte=start,
            criado_em__date__lte=end,
        )
        .annotate(data=TruncDate("criado_em"))
        .values("data", "tipo")
        .annotate(total=Sum("quantidade"))
        .order_by("data")
    )

    date_map = {}
    current = start
    while current <= end:
        date_map[current.isoformat()] = {"ENTRADA": 0, "SAIDA": 0}
        current = current + timedelta(days=1)

    for row in qs:
        d = row["data"].isoformat()
        tipo = row["tipo"]
        total = row["total"] or 0
        if d not in date_map:
            date_map[d] = {"ENTRADA": 0, "SAIDA": 0}
        date_map[d][tipo] = total

    labels = list(date_map.keys())
    entradas = [date_map[d]["ENTRADA"] for d in labels]
    saidas = [date_map[d]["SAIDA"] for d in labels]

    return JsonResponse({"labels": labels, "datasets": {"entrada": entradas, "saida": saidas}})