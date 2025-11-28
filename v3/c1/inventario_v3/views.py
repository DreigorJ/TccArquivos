from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect
from .models import Produto, Movimento
from .forms import ProdutoForm, MovimentoForm
import logging

usuarioAtual = logging.getLogger(__name__)

class LoginViewRedirect(LoginView):
    """
    LoginView que:
    - usa o template inventario_v3/login.html (mesmo template que o app fornece)
    - redireciona usuário autenticado (redirect_authenticated_user=True)
    - força o success_url para a listagem de produtos após login
    """
    template_name = "inventario_v3/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        # nome existente nas urls.py
        return reverse_lazy('inventario_v3:produtos_lista')

class ProdutosLista(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'inventario_v3/produtos_lista.html'
    context_object_name = 'produtos'   # plural para lista

class ProdutosDescricao(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'inventario_v3/produtos_descricao.html'
    context_object_name = 'produto'

class ProdutosCriacao(LoginRequiredMixin, CreateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

    def form_valid(self, form):
        usuarioAtual.info("Criado produto: %s", form.cleaned_data.get('nome'))
        return super(ProdutosCriacao, self).form_valid(form)

class ProdutosEdicao(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'inventario_v3/produtos_formulario.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

class ProdutosRemocao(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = 'inventario_v3/produtos_remocao.html'
    success_url = reverse_lazy('inventario_v3:produtos_lista')

class NovoMovimento(LoginRequiredMixin, FormView):
    form_class = MovimentoForm
    template_name = 'inventario_v3/movimentos_formulario.html'

    def dispatch(self, request, *args, **kwargs):
        self.produto = get_object_or_404(Produto, pk=kwargs.get('pk'))
        return super(NovoMovimento, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(NovoMovimento, self).get_context_data(**kwargs)
        ctx['produto'] = self.produto
        return ctx

    def form_valid(self, form):
        # salva movimento ligado ao produto e ao usuário, validando saldo para saídas
        movimento = form.save(commit=False)
        movimento.produto = self.produto
        movimento.usuario = self.request.user
        try:
            movimento.save()
        except ValueError as e:
            # se houver erro (ex: estoque insuficiente), adiciona erro ao form e re-renderiza
            form.add_error(None, str(e))
            return self.form_invalid(form)
        usuarioAtual.info("Movimento registrado: %s %d para %s", movimento.tipo_movimento, movimento.quantidade, self.produto.nome)
        return redirect('inventario_v3:produtos_descricao', pk=self.produto.pk)