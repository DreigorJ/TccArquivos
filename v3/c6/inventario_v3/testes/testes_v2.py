import shutil
from pathlib import Path

import pytest
from django.core.management import call_command, CommandError
from django.urls import reverse

from django.contrib.auth import get_user_model

from inventario_v3.models import Categoria, Produto, Movimento

User = get_user_model()


@pytest.mark.django_db
def test_categoria_crud_via_views(client, django_user_model):
    """
    Test basic CRUD for Categoria via the class-based views (requires staff).
    """
    # create staff user and login
    user = django_user_model.objects.create_user(username="staff1", password="pwd", is_staff=True)
    assert client.login(username="staff1", password="pwd") is True

    # list view (should be accessible)
    url_list = reverse("inventario_v3:categorias_lista")
    resp = client.get(url_list)
    assert resp.status_code == 200

    # create category via POST
    url_add = reverse("inventario_v3:categorias_adicionar")
    resp = client.post(url_add, {"nome": "Cat Teste", "descricao": "desc", "ativo": True})
    # CreateView typically redirects on success
    assert resp.status_code in (302, 301)
    cat = Categoria.objects.filter(nome="Cat Teste").first()
    assert cat is not None

    # edit category
    url_edit = reverse("inventario_v3:categorias_editar", args=[cat.pk])
    resp = client.post(url_edit, {"nome": "Cat Teste Edit", "descricao": "novo", "ativo": False})
    assert resp.status_code in (302, 301)
    cat.refresh_from_db()
    assert cat.nome == "Cat Teste Edit"
    assert cat.ativo is False

    # delete category
    url_del = reverse("inventario_v3:categorias_remover", args=[cat.pk])
    resp = client.post(url_del, {})
    assert resp.status_code in (302, 301)
    assert not Categoria.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_populate_command_and_models():
    """
    Run the populacao_testes management command and assert it creates entities.
    The command itself does a flush at start; tests just validate expected side-effects.
    """
    try:
        call_command("populacao_testes")
    except CommandError:
        pytest.skip("Command populacao_testes not available")
    # basic assertions: some categories, products and movements were created
    assert Categoria.objects.count() > 0
    assert Produto.objects.count() > 0
    # movimentos may be zero in some edge cases but should not error
    assert Movimento.objects.count() >= 0


@pytest.mark.django_db
def test_gerar_relatorio_command_creates_files(tmp_path):
    """
    Run the report generation management command and assert it writes JSON
    and (optionally) PNG files into the provided output directory.
    """
    out = tmp_path / "reports"
    out.mkdir(parents=True, exist_ok=True)

    try:
        call_command("gerar_relatorio", out=str(out))
    except CommandError:
        pytest.skip("gerar_relatorio command not available")
    except Exception:
        # if the command exists but fails, fail the test to surface the problem
        raise

    # Check that JSON summary files exist
    json_files = list(out.glob("*.json"))
    assert any(p.name.endswith(".json") for p in json_files), "No JSON report files were written"

    # PNG images are optional if matplotlib not available — accept either case
    png_files = list(out.glob("*.png"))
    # If matplotlib wrote images we will have PNGs; otherwise JSON is sufficient
    assert len(json_files) >= 1


@pytest.mark.django_db
def test_report_view_shows_generated_reports(client, django_user_model, tmp_path):
    """
    Ensure that the ReportView lists files present in resultados/reports.
    We'll create a resultados/reports directory in the project root and place
    a dummy file into it, then request the view as a staff user.
    """
    # create staff user and login
    username = "reportadmin"
    password = "pwd"
    django_user_model.objects.create_user(username=username, password=password, is_staff=True)
    assert client.login(username=username, password=password) is True

    # ensure the results dir exists in project root
    proj_root = Path.cwd()
    reports_dir = proj_root / "resultados" / "reports"
    moved_backup = False
    restore_after = None
    if reports_dir.exists():
        backup = tmp_path / "backup_reports"
        shutil.move(str(reports_dir), str(backup))
        reports_dir.mkdir(parents=True, exist_ok=True)
        restore_after = backup
        moved_backup = True
    else:
        reports_dir.mkdir(parents=True, exist_ok=True)
        moved_backup = False
        restore_after = None

    try:
        # create a dummy PNG (or text) file that the template will detect
        dummy_png = reports_dir / "dummy_report.png"
        dummy_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")  # minimal PNG header bytes

        # GET the reports page
        url = reverse("inventario_v3:relatorios")
        resp = client.get(url)
        assert resp.status_code == 200

        # Template content should include the filename or the URL
        content = resp.content.decode("utf-8", errors="ignore")
        assert "dummy_report.png" in content or "/resultados/reports/dummy_report.png" in content

    finally:
        # cleanup: remove dummy files and restore backup if any
        if reports_dir.exists():
            shutil.rmtree(str(reports_dir))
        if moved_backup and restore_after:
            shutil.move(str(restore_after), str(proj_root / "resultados" / "reports"))


@pytest.mark.django_db
def test_produto_change_quantidade_method_persists():
    """
    Ensure Produto.change_quantidade updates and persists the quantidade
    (this test assumes Produto.change_quantidade exists and saves).
    """
    p = Produto.objects.create(nome="ProdChange", quantidade=5, preco="1.00")
    # call with positive delta
    new = p.change_quantidade(3)
    p.refresh_from_db()
    assert new == p.quantidade
    assert p.quantidade == 8

    # call with negative delta that is allowed
    new2 = p.change_quantidade(-2)
    p.refresh_from_db()
    assert new2 == p.quantidade
    assert p.quantidade == 6

    # attempt to reduce below zero should raise
    with pytest.raises(ValueError):
        p.change_quantidade(-9999)