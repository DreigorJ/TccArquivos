import pytest
from decimal import Decimal
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model

from inventario_v1.models import Produtos
from inventario_v1.forms import ProdutosFormulario

@pytest.fixture
def user(db):
    User = get_user_model()
    u = User.objects.create_user(username="testuser", password="testpass")
    return u

@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client

@pytest.fixture
def sample_produtos(db):
    p1 = Produtos.objects.create(
        nome="Parafuso M6",
        descricao="Parafuso de aço inox",
        quantidade=150,
        preco=Decimal("0.15"),
    )
    p2 = Produtos.objects.create(
        nome="Porca M6",
        descricao="Porca sextavada",
        quantidade=200,
        preco=Decimal("0.05"),
    )
    return [p1, p2]


@pytest.mark.django_db
def test_produtos_model_create_and_str():
    p = Produtos.objects.create(
        nome="Cabo USB",
        descricao="Cabo USB 1m",
        quantidade=10,
        preco=Decimal("3.50"),
    )
    assert p.pk is not None
    assert "Cabo USB" in str(p)
    assert "(" in str(p) and ")" in str(p)


@pytest.mark.django_db
def test_produtos_form_valid_and_invalid():
    # válido
    data = {"nome": "Mouse", "descricao": "Mouse genérico", "quantidade": 5, "preco": Decimal("12.00")}
    form = ProdutosFormulario(data=data)
    assert form.is_valid(), f"Form should be valid but had errors: {form.errors}"

    # inválido: nome obrigatório
    bad = {"nome": "", "descricao": "", "quantidade": 1, "preco": "1.00"}
    form2 = ProdutosFormulario(data=bad)
    assert not form2.is_valid()
    assert "nome" in form2.errors


def test_urls_reverse_and_resolve():
    # reverse deve funcionar para os names definidos no app
    url_list = reverse("inventario_v2:produtos_lista")
    url_add = reverse("inventario_v2:produtos_adicionar")
    assert isinstance(url_list, str) and url_list.startswith("/")
    assert isinstance(url_add, str) and url_add.startswith("/")

    # resolve a path expected (se /produtos/ estiver registrado)
    # este teste apenas verifica que uma view_name existe para o path gerado por reverse
    resolved = resolve(url_list)
    assert resolved.view_name in ("inventario_v2:produtos_lista", "produtos_lista")


@pytest.mark.django_db
def test_produtos_list_requires_login(client):
    url = reverse("inventario_v2:produtos_lista")
    resp = client.get(url)
    assert resp.status_code in (301, 302)
    assert "login" in resp.url


@pytest.mark.django_db
def test_produtos_list_shows_products(client_logged_in, sample_produtos):
    url = reverse("inventario_v2:produtos_lista")
    resp = client_logged_in.get(url)
    assert resp.status_code == 200
    text = resp.content.decode("utf-8")
    assert "Parafuso M6" in text
    assert "Porca M6" in text


@pytest.mark.django_db
def test_produtos_create_view(client_logged_in):
    url = reverse("inventario_v2:produtos_adicionar")
    data = {"nome": "Teclado USB", "descricao": "Teclado genérico", "quantidade": 7, "preco": "35.50"}
    resp = client_logged_in.post(url, data, follow=True)
    assert resp.status_code == 200
    assert Produtos.objects.filter(nome="Teclado USB").exists()
    assert "Teclado USB" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_produtos_update_view(client_logged_in, sample_produtos):
    produto = sample_produtos[0]
    url = reverse("inventario_v2:produtos_editar", args=(produto.pk,))
    new_qty = produto.quantidade + 5
    data = {
        "nome": produto.nome,
        "descricao": produto.descricao,
        "quantidade": new_qty,
        "preco": str(produto.preco),
    }
    resp = client_logged_in.post(url, data, follow=True)
    assert resp.status_code == 200
    produto.refresh_from_db()
    assert produto.quantidade == new_qty


@pytest.mark.django_db
def test_produtos_delete_view(client_logged_in):
    p = Produtos.objects.create(nome="Item a remover", descricao="", quantidade=1, preco=Decimal("1.00"))
    url = reverse("inventario_v2:produtos_remover", args=(p.pk,))
    # GET confirmation page
    resp_get = client_logged_in.get(url)
    assert resp_get.status_code == 200
    # POST to confirm deletion
    resp_post = client_logged_in.post(url, {}, follow=True)
    assert resp_post.status_code == 200
    assert not Produtos.objects.filter(pk=p.pk).exists()