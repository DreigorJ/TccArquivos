from pathlib import Path
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    TemplateView,
    FormView,
    CreateView,
    UpdateView,
    DeleteView,
    ListView,
    RedirectView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy

from .models import Produto, Movimento, Categoria
from .forms import MovimentoForm

User = get_user_model()


# Lista de produtos - fornece 'produtos' no contexto (templates esperam essa variável)
class ProdutosLista(ListView):
    model = Produto
    template_name = "inventario_v3/produtos_lista.html"
    context_object_name = "produtos"


class ProdutosDescricao(TemplateView):
    template_name = "inventario_v3/produtos_descricao.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = kwargs.get("pk")
        produto = get_object_or_404(Produto, pk=pk)
        ctx["produto"] = produto
        # fornece movimentos como lista para o template (produto.movimentos.all() também funciona graças ao related_name)
        ctx["movimentos"] = produto.movimentos.all()
        return ctx


class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produto
    fields = ["nome", "descricao", "quantidade", "preco", "categoria"]
    template_name = "inventario_v3/produtos_adicionar.html"
    success_url = reverse_lazy("inventario_v3:produtos_lista")


class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produto
    fields = ["nome", "descricao", "quantidade", "preco", "categoria"]
    template_name = "inventario_v3/produtos_editar.html"
    success_url = reverse_lazy("inventario_v3:produtos_lista")


class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = "inventario_v3/produtos_remover.html"
    success_url = reverse_lazy("inventario_v3:produtos_lista")


class NovoMovimento(LoginRequiredMixin, FormView):
    form_class = MovimentoForm
    template_name = "inventario_v3/novo_movimento.html"

    def dispatch(self, request, *args, **kwargs):
        self.produto_pk = kwargs.get("pk")
        self.produto = get_object_or_404(Produto, pk=self.produto_pk)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        init = super().get_initial()
        init["produto"] = self.produto.pk
        return init

    def get_form_kwargs(self):
        """
        Ensure the bound form receives the produto field coming from URL.
        When posting from the NovoMovimento view the client doesn't include
        produto in the POST by default, so inject it into the form data so
        validation/save will work as expected.
        """
        kw = super().get_form_kwargs()
        # if there's POST data, inject produto pk into it (QueryDict copy)
        data = kw.get("data")
        if data is not None:
            try:
                d = data.copy()
            except Exception:
                d = data
            # ensure produto is a string (forms expect string values from POST)
            d["produto"] = str(self.produto.pk)
            kw["data"] = d
        else:
            # no bound data (GET) — ensure initial has produto
            initial = kw.get("initial", {})
            initial["produto"] = self.produto.pk
            kw["initial"] = initial
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["produto"] = getattr(self, "produto", None)
        return ctx

    def form_valid(self, form):
        # form is valid => safe to create Movimento and update stock
        mov = form.save(commit=False)
        mov.produto = self.produto
        mov.usuario = self.request.user if self.request.user.is_authenticated else None
        mov.save()
        return redirect("inventario_v3:produtos_descricao", pk=self.produto_pk)


# Categorias - expõe 'categorias' no contexto
class CategoriasLista(ListView):
    model = Categoria
    template_name = "inventario_v3/categorias_lista.html"
    context_object_name = "categorias"


class CategoriasAdicionar(LoginRequiredMixin, CreateView):
    model = Categoria
    fields = ["nome", "descricao", "ativo"]
    template_name = "inventario_v3/categorias_adicionar.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


class CategoriasEditar(LoginRequiredMixin, UpdateView):
    model = Categoria
    fields = ["nome", "descricao", "ativo"]
    template_name = "inventario_v3/categorias_editar.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


class CategoriasRemover(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = "inventario_v3/categorias_remover.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


class TabelasLista(RedirectView):
    permanent = False
    pattern_name = "inventario_v3:produtos_lista"


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class UsuariosLista(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = User
    template_name = "inventario_v3/usuarios_lista.html"
    context_object_name = "users"


class UsuariosAdicionar(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "inventario_v3/usuarios_adicionar.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")


class UsuariosEditar(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = User
    fields = ["username", "email", "is_active", "is_staff"]
    template_name = "inventario_v3/usuarios_editar.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")


class UsuariosRemover(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = User
    template_name = "inventario_v3/usuarios_remover.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")


class ProductAccessListCreateView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = "inventario_v3/product_access_list.html"


class ReportView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = "inventario_v3/relatorios.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = Path.cwd()
        reports_dir = base / "resultados" / "reports"
        files = []
        if reports_dir.exists():
            for p in sorted(reports_dir.iterdir()):
                files.append({"name": p.name, "url": f"/resultados/reports/{p.name}"})
        ctx["reports"] = files
        return ctx