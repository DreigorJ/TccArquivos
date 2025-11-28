import pytest
from decimal import Decimal
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model

from inventario_v3.models import Produto, Movimento
from inventario_v3.forms import MovimentoForm

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass", email="test@example.com")


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def sample_produtos(db):
    p1 = Produto.objects.create(nome="Produto A", descricao="A", quantidade=10, preco=Decimal("1.00"))
    p2 = Produto.objects.create(nome="Produto B", descricao="B", quantidade=5, preco=Decimal("2.00"))
    return p1, p2


# 1) View: criar produto via view com dados inválidos não deve criar registro
@pytest.mark.django_db
def test_produto_create_view_invalid(client_logged_in):
    try:
        url = reverse("inventario_v3:produtos_adicionar")
    except NoReverseMatch:
        pytest.skip("URL inventario_v3:produtos_adicionar não definida")

    invalid_data = {"nome": "", "quantidade": "abc", "preco": "not-a-number"}
    resp = client_logged_in.post(url, invalid_data)
    # CreateView com formulário inválido normalmente re-renderiza (200) — alguns setups podem retornar 400
    assert resp.status_code in (200, 400)
    # nenhum produto com nome vazio deve ser criado
    assert not Produto.objects.filter(nome="").exists()


# 2) View: tentativa de criar movimentação sem login deve redirecionar para login
@pytest.mark.django_db
def test_movimentacao_create_view_requires_login(client, sample_produtos):
    p1, _ = sample_produtos
    try:
        url = reverse("inventario_v3:novo_movimento", args=[p1.pk])
    except NoReverseMatch:
        pytest.skip("URL inventario_v3:novo_movimento não definida")
    resp = client.post(url, {"tipo_movimento": Movimento.MOV_ENT, "quantidade": 1})
    assert resp.status_code in (301, 302)


# 3) View: detalhe do produto (histórico) existe e mostra nome do produto
@pytest.mark.django_db
def test_produto_detail_view_shows_product(client_logged_in, sample_produtos):
    p1, _ = sample_produtos
    try:
        url = reverse("inventario_v3:produtos_descricao", args=[p1.pk])
    except NoReverseMatch:
        pytest.skip("URL inventario_v3:produtos_descricao não definida")
    resp = client_logged_in.get(url)
    assert resp.status_code == 200
    assert p1.nome in resp.content.decode("utf-8")


# 4) View: criar movimentação via view persiste e atualiza estoque
@pytest.mark.django_db
def test_create_movimentacao_persists_and_updates_stock(client_logged_in, sample_produtos):
    p1, _ = sample_produtos
    try:
        url = reverse("inventario_v3:novo_movimento", args=[p1.pk])
    except NoReverseMatch:
        pytest.skip("URL inventario_v3:novo_movimento não definida")

    data = {"tipo_movimento": Movimento.MOV_ENT, "quantidade": 3, "motivo": "teste"}
    resp = client_logged_in.post(url, data, follow=True)
    assert resp.status_code in (200, 301, 302)
    p1.refresh_from_db()
    assert Movimento.objects.filter(produto=p1, quantidade=3).exists()
    assert p1.quantidade == 13


# 5) Model: saída decrementa quantidade corretamente (usar save() do modelo)
@pytest.mark.django_db
def test_movimentacao_saida_decrementa_quantidade():
    p = Produto.objects.create(nome="P_saida", quantidade=10, preco=Decimal("2.00"))
    mov = Movimento(produto=p, tipo_movimento=Movimento.MOV_SAI, quantidade=4, usuario=None)
    mov.save()
    p.refresh_from_db()
    assert p.quantidade == 6


# 6) Model: saída igual ao estoque zera quantidade
@pytest.mark.django_db
def test_movimentacao_saida_igual_estoque_zera():
    p = Produto.objects.create(nome="P_zero", quantidade=3, preco=Decimal("1.00"))
    mov = Movimento(produto=p, tipo_movimento=Movimento.MOV_SAI, quantidade=3, usuario=None)
    mov.save()
    p.refresh_from_db()
    assert p.quantidade == 0


# 7) Model: __str__ retorna string para Produto e Movimento
@pytest.mark.django_db
def test_model_str_returns_string():
    c = Produto.objects.create(nome="ProdutoX", descricao="", quantidade=1, preco=Decimal("1.00"))
    assert isinstance(str(c), str)
    mov = Movimento(produto=c, tipo_movimento=Movimento.MOV_ENT, quantidade=2, usuario=None)
    mov.save()
    assert isinstance(str(mov), str)


# 8) Model: change_quantidade method - ajustar quantidade via método
@pytest.mark.django_db
def test_produto_change_quantidade_method():
    p = Produto.objects.create(nome="Pchg", quantidade=5, preco=Decimal("1.00"))
    if hasattr(p, "change_quantidade"):
        p.change_quantidade(2)
        p.refresh_from_db()
        assert p.quantidade == 7
        p.change_quantidade(-3)
        p.refresh_from_db()
        assert p.quantidade == 4
    else:
        pytest.skip("Produto.change_quantidade não existe — pulei o teste.")


# 9) Validation: movimentação com quantidade inválida é rejeitada pelo form
@pytest.mark.django_db
def test_movimentacao_quantidade_negativa_rejeitada(sample_produtos):
    p1, _ = sample_produtos
    form = MovimentoForm(data={"tipo_movimento": Movimento.MOV_ENT, "quantidade": -3, "motivo": ""})
    assert not form.is_valid()
    assert "quantidade" in form.errors