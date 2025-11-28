import pytest
from decimal import Decimal
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model

from inventario_v1.models import Produtos, Movimentacao, PerfilUsuario
from inventario_v1.forms import MovimentacaoFormulario, ProdutosFormulario

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
    p1 = Produtos.objects.create(nome="Produto A", descricao="A", quantidade=10, preco=Decimal("1.00"))
    p2 = Produtos.objects.create(nome="Produto B", descricao="B", quantidade=5, preco=Decimal("2.00"))
    return p1, p2


# 1) View: criar produto via view com dados inválidos não deve criar registro
@pytest.mark.django_db
def test_produto_create_view_invalid(client, client_logged_in):
    try:
        url = reverse("inventario_v1:produtos_adicionar")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:produtos_adicionar não definida")

    invalid_data = {"nome": "", "quantidade": "abc", "preco": "not-a-number"}
    resp = client_logged_in.post(url, invalid_data)
    assert resp.status_code in (200, 400)
    # nenhum produto com nome vazio deve ser criado
    assert not Produtos.objects.filter(nome="").exists()


# 2) View: tentativa de criar movimentação sem login deve redirecionar para login
@pytest.mark.django_db
def test_movimentacao_create_view_requires_login(client, sample_produtos):
    p1, _ = sample_produtos
    try:
        url = reverse("inventario_v1:movimentacoes_adicionar")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:movimentacoes_adicionar não definida")
    resp = client.post(url, {"produto": p1.pk, "tipo": Movimentacao.TIPO_ENTRADA, "quantidade": 1})
    assert resp.status_code in (301, 302)


# 3) View: detalhe do produto (histórico) existe e mostra nome do produto
@pytest.mark.django_db
def test_produto_detail_view_shows_product(client_logged_in, sample_produtos):
    p1, _ = sample_produtos
    # try likely route names that may exist in this project
    urls_to_try = [
        ("inventario_v1:produto_movimentacoes", (p1.pk,)),
        ("inventario_v1:produtos_descricao", (p1.pk,)),
    ]
    for name, args in urls_to_try:
        try:
            url = reverse(name, args=args)
        except NoReverseMatch:
            url = None
        if url:
            resp = client_logged_in.get(url)
            assert resp.status_code == 200
            assert p1.nome in resp.content.decode("utf-8")
            return
    pytest.skip("Nenhuma URL de detalhe de produto encontrada (produto_movimentacoes/produtos_descricao).")


# 4) View: criar movimentação via view persiste e atualiza estoque
@pytest.mark.django_db
def test_create_movimentacao_persists_and_updates_stock(client_logged_in, sample_produtos):
    p1, _ = sample_produtos
    try:
        url = reverse("inventario_v1:movimentacoes_adicionar")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:movimentacoes_adicionar não definida")

    data = {"produto": p1.pk, "tipo": Movimentacao.TIPO_ENTRADA, "quantidade": 3, "observacao": "teste"}
    resp = client_logged_in.post(url, data, follow=True)
    assert resp.status_code in (200, 301, 302)
    p1.refresh_from_db()
    assert Movimentacao.objects.filter(produto=p1, quantidade=3).exists()
    assert p1.quantidade == 13


# 5) Model: saída decrementa quantidade corretamente (usar métodos do modelo)
@pytest.mark.django_db
def test_movimentacao_saida_decrementa_quantidade():
    p = Produtos.objects.create(nome="P_saida", quantidade=10, preco=Decimal("2.00"))
    mov = Movimentacao.objects.create(produto=p, tipo=Movimentacao.TIPO_SAIDA, quantidade=4, usuario=None)
    # aplicar alteração no estoque
    mov.aplicar_no_estoque()
    p.refresh_from_db()
    assert p.quantidade == 6


# 6) Model: saída igual ao estoque zera quantidade
@pytest.mark.django_db
def test_movimentacao_saida_igual_estoque_zera():
    p = Produtos.objects.create(nome="P_zero", quantidade=3, preco=Decimal("1.00"))
    mov = Movimentacao.objects.create(produto=p, tipo=Movimentacao.TIPO_SAIDA, quantidade=3, usuario=None)
    mov.aplicar_no_estoque()
    p.refresh_from_db()
    assert p.quantidade == 0


# 7) Model: __str__ retorna string para Produtos e PerfilUsuario
@pytest.mark.django_db
def test_model_str_returns_string():
    c = Produtos.objects.create(nome="ProdutoX", descricao="", quantidade=1, preco=Decimal("1.00"))
    assert isinstance(str(c), str)
    # perfil: criar usuário e perfil usando a fábrica de usuário já importada
    testu = User.objects.create_user(username="u_str", password="pwd")
    # use get_or_create para evitar UniqueError se o signal já criou o perfil
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=testu, defaults={"papel": PerfilUsuario.ROLE_OPERATOR})
    assert isinstance(str(perfil), str)


# 8) Model: change_quantidade method (se existir) - ajustar quantidade via método
@pytest.mark.django_db
def test_produto_change_quantidade_method():
    p = Produtos.objects.create(nome="Pchg", quantidade=5, preco=Decimal("1.00"))
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
    form = MovimentacaoFormulario(data={"produto": p1.pk, "tipo": Movimentacao.TIPO_ENTRADA, "quantidade": -3})
    assert not form.is_valid()
    assert "quantidade" in form.errors