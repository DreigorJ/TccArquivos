import pytest
from decimal import Decimal
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model

from inventario_v1.models import Categoria, Produtos
from inventario_v1.forms import CategoriaFormulario

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cat_user", password="pwd")


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_categoria_model_and_str():
    c = Categoria.objects.create(nome="Eletrônicos", descricao="Equipamentos eletrônicos")
    assert isinstance(str(c), str)
    assert str(c) == "Eletrônicos"
    # unique constraint: creating same name should raise IntegrityError at DB level,
    # but here we simply verify get_or_create behavior works
    c2, created = Categoria.objects.get_or_create(nome="Eletrônicos")
    assert c2.pk == c.pk
    assert not created


@pytest.mark.django_db
def test_categoria_form_validation():
    # valid form
    form = CategoriaFormulario(data={"nome": "Periféricos", "descricao": "Mouses e teclados"})
    assert form.is_valid()

    # invalid: empty name
    form2 = CategoriaFormulario(data={"nome": "", "descricao": "X"})
    assert not form2.is_valid()
    assert "nome" in form2.errors


@pytest.mark.django_db
def test_categorias_list_view_requires_login(client):
    try:
        url = reverse("inventario_v1:categorias_lista")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:categorias_lista não definida")
    resp = client.get(url)
    assert resp.status_code in (301, 302)


@pytest.mark.django_db
def test_categorias_crud_views(client_logged_in):
    # adicionar
    try:
        url_add = reverse("inventario_v1:categorias_adicionar")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:categorias_adicionar não definida")

    data = {"nome": "Peças", "descricao": "Peças e acessórios"}
    resp = client_logged_in.post(url_add, data, follow=True)
    assert resp.status_code in (200, 302)
    cat = Categoria.objects.filter(nome="Peças").first()
    assert cat is not None

    # editar
    try:
        url_edit = reverse("inventario_v1:categorias_editar", args=(cat.pk,))
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:categorias_editar não definida")
    resp_edit = client_logged_in.post(url_edit, {"nome": "Peças-Atualizado", "descricao": "desc"}, follow=True)
    assert resp_edit.status_code in (200, 302)
    cat.refresh_from_db()
    assert cat.nome == "Peças-Atualizado"

    # remover (GET shows confirmation, POST performs delete)
    try:
        url_rem = reverse("inventario_v1:categorias_remover", args=(cat.pk,))
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:categorias_remover não definida")
    get_resp = client_logged_in.get(url_rem)
    assert get_resp.status_code == 200
    post_resp = client_logged_in.post(url_rem, {}, follow=True)
    assert post_resp.status_code in (200, 302)
    assert not Categoria.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_deleting_category_sets_product_category_null(client_logged_in):
    # create category and product assigned to it
    cat = Categoria.objects.create(nome="TesteCat")
    p = Produtos.objects.create(nome="ProdutoC", descricao="", quantidade=1, preco=Decimal("1.00"), categoria=cat)

    # delete category via ORM (simulates admin/view)
    cat.delete()
    p.refresh_from_db()
    # FK is SET_NULL: product remains but category is None
    assert p.categoria is None


@pytest.mark.django_db
def test_produtos_filter_by_categoria_in_produtos_lista(client_logged_in):
    # create categories and products
    cat1 = Categoria.objects.create(nome="CatA")
    cat2 = Categoria.objects.create(nome="CatB")

    p1 = Produtos.objects.create(nome="Prod A1", descricao="", quantidade=1, preco=Decimal("1.00"), categoria=cat1)
    p2 = Produtos.objects.create(nome="Prod B1", descricao="", quantidade=2, preco=Decimal("2.00"), categoria=cat2)
    p3 = Produtos.objects.create(nome="Prod A2", descricao="", quantidade=3, preco=Decimal("3.00"), categoria=cat1)

    try:
        url = reverse("inventario_v1:produtos_lista")
    except NoReverseMatch:
        pytest.skip("URL inventario_v1:produtos_lista não definida")

    # all products shown
    resp_all = client_logged_in.get(url)
    assert resp_all.status_code == 200
    content_all = resp_all.content.decode("utf-8")
    assert "Prod A1" in content_all and "Prod B1" in content_all and "Prod A2" in content_all

    # filter by cat1
    resp_f = client_logged_in.get(url + f"?categoria={cat1.pk}")
    assert resp_f.status_code == 200
    content = resp_f.content.decode("utf-8")
    assert "Prod A1" in content
    assert "Prod A2" in content
    # Prod B1 should not be present in the filtered table (it may still appear in selects)
    assert "Prod B1" not in content.split("</table>")[0]  # check only table portion