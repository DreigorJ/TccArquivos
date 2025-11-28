from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from .models import Produto, Categoria, Movimento
from .forms import ProdutoForm, MovimentoForm, CategoriaForm
import logging

usuarioAtual = logging.getLogger(__name__)

class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'inventario_v3/produtos_lista.html'
    context_object_name = 'produtos'   # plural para lista

class ProdutosDescricao(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'inventario_v3/produtos_descricao.html'
    context_object_name = 'produto'

class ProdutosAdicionar(LoginRequiredMixin, CreateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

    def form_valid(self, form):
        usuarioAtual.info("Criado produto: %s", form.cleaned_data.get('nome'))
        return super().form_valid(form)

class ProdutosEditar(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

class ProdutosRemover(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = 'inventario_v3/produtos_remover.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

class NovoMovimento(LoginRequiredMixin, FormView):
    form_class = MovimentoForm
    template_name = 'inventario_v3/movimentos_formulario.html'

    def dispatch(self, request, *args, **kwargs):
        self.produto = get_object_or_404(Produto, pk=kwargs.get('pk'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['produto'] = self.produto
        return ctx

    def form_valid(self, form):
        movimento = form.save(commit=False)
        movimento.produto = self.produto
        movimento.usuario = self.request.user
        try:
            movimento.save()
        except ValueError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        usuarioAtual.info("Movimento registrado: %s %d para %s", movimento.tipo_movimento, movimento.quantidade, self.produto.nome)
        return redirect('inventario_v3:produtos_descricao', pk=self.produto.pk)


from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import generic
from pathlib import Path
from django.core.management import call_command, CommandError
from django.contrib import messages

@method_decorator(staff_member_required, name='dispatch')
class CategoriasLista(generic.ListView):
    model = Categoria
    template_name = "inventario_v3/categorias_lista.html"
    context_object_name = "categorias"

@method_decorator(staff_member_required, name='dispatch')
class CategoriasAdicionar(generic.CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "inventario_v3/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")

@method_decorator(staff_member_required, name='dispatch')
class CategoriasEditar(generic.UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "inventario_v3/categorias_formulario.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")

@method_decorator(staff_member_required, name='dispatch')
class CategoriasRemover(generic.DeleteView):
    model = Categoria
    template_name = "inventario_v3/categorias_remover.html"
    success_url = reverse_lazy("inventario_v3:categorias_lista")

@method_decorator(staff_member_required, name="dispatch")
class ReportView(generic.TemplateView):
    template_name = "inventario_v3/relatorios.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        out = Path("resultados/reports")
        ctx["reports"] = []
        if out.exists():
            for p in sorted(out.iterdir()):
                if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    ctx["reports"].append({
                        "name": p.name,
                        "url": f"/resultados/reports/{p.name}",
                    })
        return ctx

    def post(self, request, *args, **kwargs):
        out_dir = "resultados/reports"
        try:
            call_command("gerar_relatorio", out=out_dir)
            messages.success(request, "Relatórios gerados com sucesso.")
        except CommandError as ce:
            messages.error(request, f"Erro ao gerar relatórios (CommandError): {ce}")
        except Exception as e:
            messages.error(request, f"Erro ao gerar relatórios: {e}")
        return redirect("inventario_v3:relatorios")