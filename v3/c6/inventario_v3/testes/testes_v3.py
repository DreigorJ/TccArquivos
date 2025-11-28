# adapted test_v3 for this application
import re
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.contrib.auth.signals import user_logged_in

from inventario_v3.models import (
    PerfilUsuario, Produto, Movimento,
    TabelaProdutos, AcessoTabela
)

User = get_user_model()


@pytest.mark.django_db
def test_profile_created_on_user_creation():
    u = User.objects.create_user(username="u_profile", password="pwd")
    assert PerfilUsuario.objects.filter(usuario=u).exists()
    profile = PerfilUsuario.objects.get(usuario=u)
    assert profile.funcao  # default exists


@pytest.mark.django_db
def test_register_view_auto_login_and_redirect(client):
    url_register = reverse("inventario_v3:register")
    data = {
        "username": "reguser",
        "email": "reg@example.com",
        "password1": "StrongPass!23",
        "password2": "StrongPass!23",
    }
    resp = client.post(url_register, data)
    # should redirect after successful registration and auto-login
    assert resp.status_code in (302, 301)
    # client should now be authenticated: access protected page
    resp2 = client.get(reverse("inventario_v3:tabelas_lista"))
    assert resp2.status_code == 200


@pytest.mark.django_db
def test_login_view_redirects_authenticated_user(client, django_user_model):
    u = django_user_model.objects.create_user(username="authuser", password="pwd")
    client.force_login(u)
    resp = client.get(reverse("inventario_v3:login"))
    # LoginView has redirect_authenticated_user=True => should redirect
    assert resp.status_code in (302, 301)
    # target should be LOGIN_REDIRECT_URL (tabelas)
    assert reverse("inventario_v3:tabelas_lista") in resp["Location"]


@pytest.mark.django_db
def test_select_current_tabela_sets_profile_current_tabela(client, django_user_model):
    user = django_user_model.objects.create_user(username="seluser", password="pwd")
    PerfilUsuario.objects.get_or_create(usuario=user)
    # tornar a tabela pública para permitir seleção (ou alternativamente criar AcessoTabela)
    t = TabelaProdutos.objects.create(nome="T-SEL", descricao="t", publico=True)
    client.force_login(user)
    url = reverse("inventario_v3:seleciona_tabela_atual", args=[t.pk])
    resp = client.post(url)
    # Should redirect to produtos lista
    assert resp.status_code in (302, 301)
    profile = PerfilUsuario.objects.get(usuario=user)
    assert profile.current_tabela == t


@pytest.mark.django_db
def test_create_movimento_updates_produto_quantity_and_saves_movement(client, django_user_model):
    # staff can create movements regardless of table-level permissions in our views
    staff = django_user_model.objects.create_user(username="movstaff", password="pwd", is_staff=True)
    client.force_login(staff)
    # criar uma tabela pública e associar o produto a ela para evitar checks que neguem a operação
    t = TabelaProdutos.objects.create(nome="Tmov", publico=True)
    p = Produto.objects.create(nome="MovProd", quantidade=5, preco="10.00")
    p.tabelas.add(t)
    url = reverse("inventario_v3:novo_movimento", args=[p.pk])

    # use a valid choice for tipo_movimento (first available)
    tipo_val = Movimento._meta.get_field('tipo_movimento').choices[0][0]
    post_data = {"tipo_movimento": tipo_val, "quantidade": 3, "motivo": "test entrada"}
    resp = client.post(url, post_data)
    # accept form re-render (200) or redirect on success
    assert resp.status_code in (200, 302, 301), f"Unexpected response: {resp.status_code}\n{resp.content.decode()}"
    # movement should have been created (otherwise fail and show response for debugging)
    assert Movimento.objects.filter(produto=p, quantidade=3).exists(), f"Movimento not created; response body:\n{resp.content.decode()}"
    p.refresh_from_db()
    assert p.quantidade == 8


@pytest.mark.django_db
def test_deleting_tabela_deletes_orphan_produto_and_movimentos():
    t = TabelaProdutos.objects.create(nome="TDEL", publico=False)
    p = Produto.objects.create(nome="Pdel", quantidade=2, preco="1.00")
    p.tabelas.add(t)
    Movimento.objects.create(produto=p, tipo_movimento=Movimento.MOV_ENT, quantidade=2, motivo="init")
    # sanity
    assert Produto.objects.filter(pk=p.pk).exists()
    assert Movimento.objects.filter(produto=p).exists()
    # delete tabela (handler pre_delete deverá apagar produtos órfãos)
    t.delete()
    # after deletion signals should remove orphan product and its movimentos
    assert not Produto.objects.filter(pk=p.pk).exists()
    assert not Movimento.objects.filter(produto=p.pk).exists()


@pytest.mark.django_db
def test_removing_m2m_relation_removes_orphan_product():
    t = TabelaProdutos.objects.create(nome="TREM", publico=False)
    p = Produto.objects.create(nome="Prem", quantidade=1, preco="2.00")
    p.tabelas.add(t)
    assert p.tabelas.count() == 1
    # remove relation via ORM (triggers m2m_changed)
    p.tabelas.remove(t)
    # product should be deleted (signals)
    assert not Produto.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db
def test_user_crud_and_password_change_by_admin(client, django_user_model):
    # staff creates a user and later edits its password via the Users edit view
    staff = django_user_model.objects.create_user(username="adminu", password="pwd", is_staff=True)
    client.force_login(staff)
    # create user via usuarios_adicionar view
    url_add = reverse("inventario_v3:usuarios_adicionar")
    create_data = {
        "username": "cruduser",
        "email": "crud@example.com",
        "password1": "InitialPass1!",
        "password2": "InitialPass1!",
    }
    resp = client.post(url_add, create_data)
    assert resp.status_code in (302, 301)
    user = User.objects.get(username="cruduser")
    # now edit user password via usuarios_editar
    url_edit = reverse("inventario_v3:usuarios_editar", args=[user.pk])
    edit_data = {
        "username": user.username,
        "email": user.email,
        "is_active": "on",
        "is_staff": "",  # keep not staff
        "password1": "NewSecret!23",
        "password2": "NewSecret!23",
    }
    resp = client.post(url_edit, edit_data)
    assert resp.status_code in (302, 301)
    # logout and login with new credentials
    client.logout()
    assert client.login(username="cruduser", password="NewSecret!23") is True


@pytest.mark.django_db
def test_gerenciar_acessos_create_and_listing(client, django_user_model):
    # staff creates a tabela and assigns access to a user via gerenciar_acessos view
    staff = django_user_model.objects.create_user(username="accstaff", password="pwd", is_staff=True)
    user = django_user_model.objects.create_user(username="targetuser", password="pwd")
    client.force_login(staff)
    t = TabelaProdutos.objects.create(nome="TACC", publico=False)
    url = reverse("inventario_v3:gerenciar_acessos")
    post_data = {"usuario": str(user.pk), "tabela": str(t.pk), "nivel": AcessoTabela.Niveis.ESCRITA}
    resp = client.post(url, post_data)
    assert resp.status_code in (302, 301)
    assert AcessoTabela.objects.filter(usuario=user, tabela=t, nivel=AcessoTabela.Niveis.ESCRITA).exists()
    # list page should show created access
    resp = client.get(url)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8", errors="ignore")
    assert "targetuser" in content or str(user.pk) in content
    assert "TACC" in content or t.nome in content


@pytest.mark.django_db
def test_permission_flow_product_creation_and_visibility(client, django_user_model):
    # Create a tabela, a user with access, and test that product creation/visibility respects current_tabela
    user = django_user_model.objects.create_user(username="permuser", password="pwd")
    PerfilUsuario.objects.get_or_create(usuario=user)
    t = TabelaProdutos.objects.create(nome="Tperm", publico=False)
    # give user escrita
    AcessoTabela.objects.create(usuario=user, tabela=t, nivel=AcessoTabela.Niveis.ESCRITA)
    # user logs in and selects tabela
    client.login(username="permuser", password="pwd")
    sel_url = reverse("inventario_v3:seleciona_tabela_atual", args=[t.pk])
    client.post(sel_url)
    # create product via ProdutosAdicionar view (user not staff but has escrita)
    add_url = reverse("inventario_v3:produtos_adicionar")
    prod_data = {"nome": "ProdPerm", "descricao": "d", "preco": "5.00", "categoria": "", "tabelas": [str(t.pk)]}
    resp = client.post(add_url, prod_data)
    assert resp.status_code in (302, 301)
    p = Produto.objects.filter(nome="ProdPerm").first()
    assert p is not None
    # ProdutosLista for the user (with current_tabela) should show the product
    list_url = reverse("inventario_v3:produtos_lista")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "ProdPerm" in resp.content.decode()


@pytest.mark.django_db
def test_deleting_product_removes_movements_and_m2m_relations():
    t = TabelaProdutos.objects.create(nome="TDelProd", publico=True)
    p = Produto.objects.create(nome="ToDelete", quantidade=4, preco="2.00")
    p.tabelas.add(t)
    # create movimentos
    Movimento.objects.create(produto=p, tipo_movimento=Movimento.MOV_ENT, quantidade=2, motivo="m1")
    Movimento.objects.create(produto=p, tipo_movimento=Movimento.MOV_SAI, quantidade=1, motivo="m2")
    # delete product
    pk = p.pk
    p.delete()
    # movimentos removed
    assert not Movimento.objects.filter(produto_id=pk).exists()
    # m2m relations cleaned (no product related in through)
    assert not TabelaProdutos.objects.filter(produtos__pk=pk).exists()


# -------------------------
# Additional tests added
# -------------------------


@pytest.mark.django_db
def test_gerar_relatorio_command_creates_files(tmp_path):
    # create minimal data
    t = TabelaProdutos.objects.create(nome="T1", publico=True)
    p = Produto.objects.create(nome="P1", quantidade=5, preco="10.00")
    p.tabelas.add(t)

    out = tmp_path / "reports"
    out.mkdir()

    # call the management command (only supported args in this app)
    call_command("gerar_relatorio", out=str(out))

    files = list(out.iterdir())
    # expect at least some JSON or PNG files
    assert any(f.suffix.lower() in (".png", ".json") for f in files)


@pytest.mark.django_db
def test_signal_generates_report_on_login(django_user_model):
    # create user and a public table so the receiver will find tables
    user = django_user_model.objects.create_user(username="siguser", password="pwd")
    TabelaProdutos.objects.create(nome="Tsig", publico=True)

    import inventario_v3.signals as signals_mod
    with patch.object(signals_mod, "call_command") as mock_call:
        # send the login signal (request can be None; receiver handles it defensively)
        user_logged_in.send(sender=user.__class__, user=user, request=None)
        assert mock_call.called


@pytest.mark.django_db
def test_relatorios_post_generates_report(client, django_user_model, tmp_path, settings):
    user = django_user_model.objects.create_user(username="ruser", password="pwd")
    PerfilUsuario.objects.get_or_create(usuario=user)
    # create a public tabela
    TabelaProdutos.objects.create(nome="Trpt", publico=True)
    client.force_login(user)

    # point BASE_DIR to temp so the command writes into tmp_path/resultados/reports
    settings.BASE_DIR = tmp_path
    out_dir = tmp_path / "resultados" / "reports"

    resp = client.post(reverse("inventario_v3:relatorios"))
    assert resp.status_code in (302, 301)
    # verify files were created
    files = list(out_dir.glob("*")) if out_dir.exists() else []
    assert any(("report" in f.name or f.suffix.lower() in (".png", ".json")) for f in files)


@pytest.mark.django_db
def test_tabelas_lista_shows_only_public_and_access(client, django_user_model):
    user = django_user_model.objects.create_user(username="tuser", password="pwd")
    PerfilUsuario.objects.get_or_create(usuario=user)
    public = TabelaProdutos.objects.create(nome="Public", publico=True)
    private = TabelaProdutos.objects.create(nome="Priv", publico=False)
    client.force_login(user)
    resp = client.get(reverse("inventario_v3:tabelas_lista"))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Public" in content
    assert "Priv" not in content

    # create access and assert private shows up
    AcessoTabela.objects.create(usuario=user, tabela=private, nivel=AcessoTabela.Niveis.LEITURA)
    resp2 = client.get(reverse("inventario_v3:tabelas_lista"))
    assert "Priv" in resp2.content.decode()


@pytest.mark.django_db
def test_produto_adicionar_forbidden_without_write_permission(client, django_user_model):
    user = django_user_model.objects.create_user(username="noperm", password="pwd")
    PerfilUsuario.objects.get_or_create(usuario=user)
    t = TabelaProdutos.objects.create(nome="Tno", publico=False)
    client.force_login(user)
    data = {"nome": "X", "preco": "1.00", "tabelas": [str(t.pk)], "descricao": ""}
    resp = client.post(reverse("inventario_v3:produtos_adicionar"), data)
    # view should return 403 Forbidden when user lacks write permission
    assert resp.status_code == 403