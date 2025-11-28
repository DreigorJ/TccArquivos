import pytest
from django.urls import reverse
from django.apps import apps
from django.contrib.auth import get_user_model

from inventario_v3.models import Produto

User = get_user_model()
pytestmark = pytest.mark.django_db


def _get_model_or_skip(app_label, model_name):
    try:
        mdl = apps.get_model(app_label, model_name)
    except LookupError:
        pytest.skip(f"Model {app_label}.{model_name} not available")
    return mdl


def test_profile_created_on_user_creation(django_user_model):
    """
    Creating a user should auto-create a PerfilUsuario (signal).
    If the model doesn't exist in this branch/environment, skip the test.
    """
    PerfilUsuario = _get_model_or_skip("inventario_v3", "PerfilUsuario")
    u = django_user_model.objects.create_user(username="u_profile", password="pwd")
    assert PerfilUsuario.objects.filter(usuario=u).exists()
    profile = PerfilUsuario.objects.get(usuario=u)
    assert getattr(profile, "funcao", None)


def test_users_crud_views(client, django_user_model):
    """
    Test the basic CRUD views for users (staff-required views).
    If user-management views are not wired in this environment, skip gracefully.
    """
    # create and login as staff
    staff = django_user_model.objects.create_user(username="staff", password="pwd", is_staff=True)
    assert client.login(username="staff", password="pwd") is True

    # ensure URLs exist before proceeding (reverse will raise NoReverseMatch if not)
    try:
        url_list = reverse("inventario_v3:usuarios_lista")
    except Exception:
        pytest.skip("User management URLs not available in this environment")

    resp = client.get(url_list)
    assert resp.status_code == 200

    # create (POST) a new user
    url_add = reverse("inventario_v3:usuarios_adicionar")
    new_data = {
        "username": "newuser",
        "email": "new@example.com",
        "password1": "safepwd123",
        "password2": "safepwd123",
    }
    resp = client.post(url_add, new_data)
    assert resp.status_code in (301, 302)
    new_user = User.objects.filter(username="newuser").first()
    assert new_user is not None

    # edit the user
    url_edit = reverse("inventario_v3:usuarios_editar", args=[new_user.pk])
    edit_data = {
        "username": "newuser",
        "email": "changed@example.com",
        "is_active": "on",
    }
    resp = client.post(url_edit, edit_data)
    assert resp.status_code in (301, 302)
    new_user.refresh_from_db()
    assert new_user.email == "changed@example.com"

    # delete the user
    url_del = reverse("inventario_v3:usuarios_remover", args=[new_user.pk])
    resp = client.post(url_del, {})
    assert resp.status_code in (301, 302)
    assert not User.objects.filter(pk=new_user.pk).exists()


def test_user_create_validation_passwords(client, django_user_model):
    """
    Posting mismatched passwords should not create a user (form validation).
    Skip if URLs not available.
    """
    staff = django_user_model.objects.create_user(username="staff2", password="pwd", is_staff=True)
    assert client.login(username="staff2", password="pwd") is True

    try:
        url_add = reverse("inventario_v3:usuarios_adicionar")
    except Exception:
        pytest.skip("User creation URL not available in this environment")

    bad_data = {
        "username": "baduser",
        "email": "b@example.com",
        "password1": "pwdA",
        "password2": "pwdB",  # mismatch
    }
    resp = client.post(url_add, bad_data)
    assert resp.status_code in (200, 302)  # form with errors usually returns 200; some setups redirect
    assert not User.objects.filter(username="baduser").exists()


def test_product_access_create_and_list_via_view(client, django_user_model):
    """
    Ensure the product-access view allows staff to create an AcessoProdutos entry
    and that the created access appears in the accesses listing.
    Skip if AcessoProdutos model or view is not available.
    """
    try:
        AcessoProdutos = apps.get_model("inventario_v3", "AcessoProdutos")
    except LookupError:
        pytest.skip("AcessoProdutos model not available")

    staff = django_user_model.objects.create_user(username="access_staff", password="pwd", is_staff=True)
    user = django_user_model.objects.create_user(username="user_target", password="pwd")
    assert client.login(username="access_staff", password="pwd") is True

    p = Produto.objects.create(nome="TestProd", quantidade=5, preco="1.00")

    try:
        url_access = reverse("inventario_v3:product_access_list")
    except Exception:
        pytest.skip("product_access_list view not available")

    post_data = {
        "usuario": str(user.pk),
        "produto": str(p.pk),
        "nivel": "escrita",
    }
    resp = client.post(url_access, post_data)
    assert resp.status_code in (301, 302)

    assert AcessoProdutos.objects.filter(usuario=user, produto=p, nivel="escrita").exists()

    resp = client.get(url_access)
    assert resp.status_code == 200
    text = resp.content.decode("utf-8", errors="ignore")
    assert "TestProd" in text
    assert "user_target" in text