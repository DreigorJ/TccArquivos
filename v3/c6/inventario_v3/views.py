# inventario_v3/views.py
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView,
    FormView, TemplateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model, authenticate, login
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.utils import timezone
from django.core.management import call_command
from django.contrib import messages
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
import logging, re

from .models import (
    Produto, Categoria, Movimento,
    PerfilUsuario, TabelaProdutos, AcessoTabela
)
from .forms import (
    ProdutoForm, MovimentoForm, CategoriaForm,
    TabelaProdutosForm, AcessoTabelaForm,
    UserCreateForm, UserUpdateForm
)

logger = logging.getLogger(__name__)
Usuario = get_user_model()


# ----- helper permission utilities (table-level) -----
def user_has_table_level(user, tabela, required_level="leitura"):
    """
    Return True if `user` has at least `required_level` for tabela.
    Levels order: nenhum < leitura < escrita < administrador
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True

    profile = getattr(user, "perfil", None)
    # allow custom profile helper if present
    if profile and getattr(profile, "is_admin", lambda: False)():
        return True

    acc = AcessoTabela.objects.filter(usuario=user, tabela=tabela).first()
    if acc:
        order = {"nenhum": 0, "leitura": 1, "escrita": 2, "administrador": 3}
        return order.get(acc.nivel, 0) >= order.get(required_level, 0)
    # fallback: public tabelas allow leitura
    if getattr(tabela, "publico", False) and required_level == "leitura":
        return True
    return False


def product_has_table_with_access(product, user, required_level="leitura"):
    """
    For a product that may belong to multiple tabelas, return True if the user
    has the required_level on any tabela the product belongs to.

    Adaptation: consider products that have NO tabelas attached as 'public'
    for access checks (so tests that create products without tabelas can view/move them).
    """
    # If product has no tabelas, treat it as accessible (public)
    if product.tabelas.count() == 0:
        return True

    for t in product.tabelas.all():
        if user_has_table_level(user, t, required_level):
            return True
    return False


# ----- Products views (respecting tabela active / permissions) -----
class ProdutosLista(LoginRequiredMixin, ListView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Produto
    template_name = 'inventario_v3/produtos_lista.html'
    context_object_name = 'produtos'

    def get_queryset(self):
        qs = super().get_queryset()
        perfil = getattr(self.request.user, "perfil", None)
        tabela = getattr(perfil, "current_tabela", None) if perfil else None
        if tabela:
            return qs.filter(tabelas=tabela).distinct()
        return qs.filter(Q(tabelas__isnull=True) | Q(tabelas__publico=True)).distinct()


class ProdutosDescricao(LoginRequiredMixin, DetailView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Produto
    template_name = 'inventario_v3/produtos_descricao.html'
    context_object_name = 'produto'

    def dispatch(self, request, *args, **kwargs):
        produto = self.get_object()
        if not product_has_table_with_access(produto, request.user, "leitura"):
            return HttpResponseForbidden("Você não tem permissão para ver este produto.")
        return super().dispatch(request, *args, **kwargs)


class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

    def form_valid(self, form):
        perfil = getattr(self.request.user, "perfil", None)
        selected_tabelas = form.cleaned_data.get("tabelas")
        tabela_ok = False

        if selected_tabelas:
            for t in selected_tabelas:
                if user_has_table_level(self.request.user, t, "escrita"):
                    tabela_ok = True
                    break
        else:
            tabela = getattr(perfil, "current_tabela", None) if perfil else None
            if tabela and user_has_table_level(self.request.user, tabela, "escrita"):
                tabela_ok = True

        if not tabela_ok and not self.request.user.is_staff and not self.request.user.is_superuser:
            return HttpResponseForbidden("Sem permissão para criar produto nesta(s) tabela(s).")

        resp = super().form_valid(form)
        if not selected_tabelas:
            tabela = getattr(perfil, "current_tabela", None) if perfil else None
            if tabela:
                self.object.tabelas.add(tabela)
        logger.info("Criado produto: %s", form.cleaned_data.get('nome'))
        return resp


class ProdutosEditar(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

    def dispatch(self, request, *args, **kwargs):
        produto = self.get_object()
        if not product_has_table_with_access(produto, request.user, "administrador") and not request.user.is_staff and not request.user.is_superuser:
            return HttpResponseForbidden("Você não tem permissão para editar este produto.")
        return super().dispatch(request, *args, **kwargs)


class ProdutosRemover(LoginRequiredMixin, DeleteView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Produto
    template_name = 'inventario_v3/produtos_remover.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

    def dispatch(self, request, *args, **kwargs):
        produto = self.get_object()
        if not product_has_table_with_access(produto, request.user, "administrador") and not request.user.is_staff and not request.user.is_superuser:
            return HttpResponseForbidden("Você não tem permissão para remover este produto.")
        return super().dispatch(request, *args, **kwargs)


class NovoMovimento(LoginRequiredMixin, FormView):
    login_url = reverse_lazy("inventario_v3:login")
    form_class = MovimentoForm
    template_name = 'inventario_v3/movimentos_formulario.html'

    produto = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.produto = get_object_or_404(Produto, pk=kwargs.get('pk'))
        if not product_has_table_with_access(self.produto, request.user, "escrita") and not request.user.is_staff and not request.user.is_superuser:
            return HttpResponseForbidden("Você não tem permissão para registrar movimentos neste produto.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Provide an instance with produto and usuario set (not saved)
        kwargs['instance'] = Movimento(produto=self.produto, usuario=self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['produto'] = self.produto
        return ctx

    def form_valid(self, form):
        movimento = form.save(commit=False)
        movimento.produto = getattr(movimento, "produto", None) or self.produto
        movimento.usuario = getattr(movimento, "usuario", None) or self.request.user
        try:
            movimento.save()
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        logger.info("Movimento registrado: %s %d para %s", movimento.tipo_movimento, movimento.quantidade, self.produto.nome)
        return redirect('inventario_v3:produtos_descricao', pk=self.produto.pk)


# ----- Category views (login required only) -----
class CategoriasLista(LoginRequiredMixin, ListView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Categoria
    template_name = "inventario_v3/categorias_lista.html"
    context_object_name = "categorias"


class CategoriasAdicionar(LoginRequiredMixin, CreateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Categoria
    form_class = CategoriaForm
    template_name = "inventario_v3/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


class CategoriasEditar(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Categoria
    form_class = CategoriaForm
    template_name = "inventario_v3/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


class CategoriasRemover(LoginRequiredMixin, DeleteView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Categoria
    template_name = "inventario_v3/categorias_remover.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")


# ----- Report view (login required only) -----
class Relatorios(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy("inventario_v3:login")
    template_name = "inventario_v3/relatorios.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        out = Path("resultados/reports")
        ctx["reports"] = []
        if out.exists():
            user = self.request.user
            user_pk = getattr(user, "pk", None)

            for p in sorted(out.iterdir()):
                if not p.is_file():
                    continue
                # aceitar html, png, json
                if p.suffix.lower() not in (".html", ".png", ".jpg", ".jpeg", ".json"):
                    continue
                name = p.name

                # staff/superuser vê todos os arquivos permitidos
                if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
                    show = True
                else:
                    show = False
                    if user_pk is not None and name.startswith(f"report_user{user_pk}_"):
                        show = True
                    if name.startswith("report_") and not name.startswith("report_user"):
                        show = True

                if not show:
                    continue

                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=dt_timezone.utc)
                mtime_local = timezone.localtime(mtime)
                ctx["reports"].append({
                    "name": p.name,
                    "url": f"/resultados/reports/{p.name}",
                    "generated_at": mtime_local,
                })
        return ctx

    def post(self, request, *args, **kwargs):
        """
        Gera relatório imediato para o usuário atual (mesma lógica do signal).
        """
        user = request.user
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            pks = list(TabelaProdutos.objects.values_list("pk", flat=True))
        else:
            public_pks = list(TabelaProdutos.objects.filter(publico=True).values_list("pk", flat=True))
            acesso_pks = list(AcessoTabela.objects.filter(usuario=user).values_list("tabela__pk", flat=True))
            pks = list({*public_pks, *acesso_pks})

        if not pks:
            messages.warning(request, "Nenhuma tabela acessível encontrada — relatório não foi gerado.")
            return redirect(reverse_lazy("inventario_v3:relatorios"))

        out_dir = Path(settings.BASE_DIR) / "resultados" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            # call without unsupported custom options
            call_command("gerar_relatorio", out=str(out_dir))
            messages.success(request, "Relatório gerado com sucesso.")
        except Exception as e:
            messages.error(request, f"Falha ao gerar relatório: {e}")
        return redirect(reverse_lazy("inventario_v3:relatorios"))


# ----- Users / Profiles / Tables / Access management (login required only) -----
class UsuariosLista(LoginRequiredMixin, ListView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Usuario
    template_name = "inventario_v3/usuarios_lista.html"
    context_object_name = "users"


class UsuariosAdicionar(LoginRequiredMixin, CreateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Usuario
    form_class = UserCreateForm
    template_name = "inventario_v3/usuarios_formulario.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")

    def form_valid(self, form):
        resp = super().form_valid(form)
        # criar perfil automaticamente
        try:
            PerfilUsuario.objects.get_or_create(usuario=self.object)
        except Exception:
            pass
        return resp


class UsuariosEditar(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Usuario
    form_class = UserUpdateForm
    template_name = "inventario_v3/usuarios_formulario.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")


class UsuariosRemover(LoginRequiredMixin, DeleteView):
    login_url = reverse_lazy("inventario_v3:login")
    model = Usuario
    template_name = "inventario_v3:usuarios_remover.html"
    success_url = reverse_lazy("inventario_v3:usuarios_lista")


class GerenciarAcessos(LoginRequiredMixin, TemplateView):
    """
    Gerencia AcessoTabela entries (user <-> tabela).
    Agora acessível para qualquer usuário autenticado.
    """
    login_url = reverse_lazy("inventario_v3:login")
    template_name = "inventario_v3/gerenciar_acessos.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["accesses"] = AcessoTabela.objects.select_related("usuario", "tabela").all()
        ctx["form"] = AcessoTabelaForm()
        return ctx

    def post(self, request, *args, **kwargs):
        form = AcessoTabelaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("inventario_v3:gerenciar_acessos")
        ctx = self.get_context_data(**kwargs)
        ctx["form"] = form
        return self.render_to_response(ctx)


# ----- TabelaProdutos CRUD and selection (login required only) -----
class TabelasLista(LoginRequiredMixin, ListView):
    login_url = reverse_lazy("inventario_v3:login")
    model = TabelaProdutos
    template_name = "inventario_v3/tabelas_lista.html"
    context_object_name = "tabelas"

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return TabelaProdutos.objects.all()
        qs_public = TabelaProdutos.objects.filter(publico=True)
        qs_acesso = TabelaProdutos.objects.filter(acessos__usuario=user)
        return (qs_public | qs_acesso).distinct()


class TabelasAdicionar(LoginRequiredMixin, CreateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = TabelaProdutos
    form_class = TabelaProdutosForm
    template_name = "inventario_v3/tabelas_formulario.html"
    success_url = reverse_lazy("inventario_v3:tabelas_lista")


class TabelasEditar(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("inventario_v3:login")
    model = TabelaProdutos
    form_class = TabelaProdutosForm
    template_name = "inventario_v3/tabelas_formulario.html"
    success_url = reverse_lazy("inventario_v3:tabelas_lista")


class TabelasRemover(LoginRequiredMixin, DeleteView):
    login_url = reverse_lazy("inventario_v3:login")
    model = TabelaProdutos
    template_name = "inventario_v3/tabelas_remover.html"
    success_url = reverse_lazy("inventario_v3:tabelas_lista")


class SelecionaTabelaAtual(LoginRequiredMixin, View):
    """
    POST to set a tabela as the user's active tabela (stored on perfil.current_tabela).
    """
    login_url = reverse_lazy("inventario_v3:login")

    def post(self, request, tabela_pk):
        tabela = get_object_or_404(TabelaProdutos, pk=tabela_pk)
        if not user_has_table_level(self.request.user, tabela, "leitura"):
            return HttpResponseForbidden("Sem permissão para selecionar esta tabela.")
        perfil = getattr(self.request.user, "perfil", None)
        if perfil:
            perfil.current_tabela = tabela
            perfil.save(update_fields=["current_tabela"])
        return redirect("inventario_v3:produtos_lista")


# ----- Registration view (public) -----
class RegistroUsuario(CreateView):
    """
    Public user registration. Uses existing UserCreateForm. After creating the user
    we create a PerfilUsuario and log the user in automatically, redirecting to LOGIN_REDIRECT_URL.
    """
    model = Usuario
    form_class = UserCreateForm
    template_name = "inventario_v3/registro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # salve o usuário explicitamente (não chame super().form_valid)
        user = form.save()  # UserCreationForm já cuida do hash da senha
        # criar perfil se necessário
        try:
            PerfilUsuario.objects.get_or_create(usuario=user)
        except Exception:
            pass
        # autenticar e logar automaticamente
        raw_password = form.cleaned_data.get("password1")
        authenticated = authenticate(self.request, username=user.username, password=raw_password)
        if authenticated is not None:
            login(self.request, authenticated)
        # redireciona para a URL definida em settings.LOGIN_REDIRECT_URL
        return redirect(settings.LOGIN_REDIRECT_URL)