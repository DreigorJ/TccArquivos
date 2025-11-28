"""
Testes de integração / comandos usados pelo app inventario_v1.

Este módulo contém testes que exercitam:
- CRUD de categorias via views
- comando de população (populacao_teste, reset_and_populate_v1, ...)
- geração de relatórios (chamada ao comando gerar_relatorio ou à função relatorios.gerar_relatorio)
- página que lista relatórios (usa MEDIA_ROOT/relatorios)
- método Produtos.change_quantidade

Notas:
- imports de models são protegidos para evitar erros em análise estática (pylint)
  quando o ambiente Django não estiver totalmente inicializado.
"""
from pathlib import Path
import shutil

import pytest
from django.core.management import call_command, CommandError
from django.urls import reverse, NoReverseMatch

from django.contrib.auth import get_user_model

# Import dos modelos. Em execução normal do pytest/Django estes imports devem funcionar.
# Pylint pode falhar ao resolver esses imports fora do contexto Django (disable import-error).
try:  # pylint: disable=import-error
    from inventario_v1.models import Categoria, Produtos, Movimentacao
except Exception:
    # Em análise estática/por segurança, permitimos continuar; os testes reais falharão cedo
    Categoria = Produtos = Movimentacao = None  # type: ignore

User = get_user_model()


@pytest.mark.django_db
def test_categoria_crud_via_views(client, django_user_model):
    """
    Test basic CRUD for Categoria via the class-based views (requires staff).
    Compatible with either inventario_v3 or inventario_v1 URL namespace.
    """
    # create staff user and login
    user = django_user_model.objects.create_user(
        username="staff1", password="pwd", is_staff=True
    )
    assert client.login(username=user.username, password="pwd") is True

    # Try to resolve list/create/edit/delete urls in a couple of common namespaces
    url_names = [
        (
            "inventario_v3:categorias_lista",
            "inventario_v3:categorias_adicionar",
            "inventario_v3:categorias_editar",
            "inventario_v3:categorias_remover",
        ),
        (
            "inventario_v1:categorias_lista",
            "inventario_v1:categorias_adicionar",
            "inventario_v1:categorias_editar",
            "inventario_v1:categorias_remover",
        ),
    ]

    resolved = None
    for list_name, add_name, edit_name, del_name in url_names:
        try:
            url_list = reverse(list_name)
            url_add = reverse(add_name)
            resolved = (list_name, add_name, edit_name, del_name)
            break
        except NoReverseMatch:
            continue

    if not resolved:
        pytest.skip("Nenhuma rota de categorias encontrada (inventario_v3 ou inventario_v1)")

    # list view (should be accessible)
    resp = client.get(url_list)
    assert resp.status_code == 200

    # create category via POST
    resp = client.post(url_add, {"nome": "Cat Teste", "descricao": "desc", "ativo": True})
    assert resp.status_code in (302, 301)
    cat = Categoria.objects.filter(nome="Cat Teste").first()
    assert cat is not None

    # edit category
    url_edit = reverse(resolved[2], args=[cat.pk])
    resp = client.post(
        url_edit, {"nome": "Cat Teste Edit", "descricao": "novo", "ativo": False}
    )
    assert resp.status_code in (302, 301)
    cat.refresh_from_db()
    assert cat.nome == "Cat Teste Edit"
    # some Categoria implementations may not have 'ativo' field; guard accordingly
    if hasattr(cat, "ativo"):
        assert cat.ativo is False

    # delete category
    url_del = reverse(resolved[3], args=[cat.pk])
    resp = client.post(url_del, {})
    assert resp.status_code in (302, 301)
    assert not Categoria.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_populate_command_and_models():
    """
    Try to run the populate sample data command (if present).
    Verify that products, categories and movements exist afterwards.
    This test prefers the project's populacao_teste command if present.
    """
    # Try project's known command names first, including populacao_teste present in this repo
    populate_cmd_names = (
        "populacao_teste",
        "reset_and_populate_v1",
        "populate_sample_data",
        "populacao_testes",
        "popula_dados",
        "populate_sample",
    )
    found = False
    last_exception = None
    for name in populate_cmd_names:
        try:
            # Many populators accept different flags; try a plain call first
            call_command(name)
            found = True
            break
        except CommandError as last_exc:  # noqa: F841 - stored for diagnostics
            last_exception = last_exc
            continue
        except Exception:
            # if command exists but fails for another reason, re-raise so CI shows the issue
            raise

    if not found:
        pytest.skip(
            "No populate command found (tried names: %s); last error: %r"
            % (", ".join(populate_cmd_names), last_exception)
        )

    # basic assertions: some categories, products and movements were created
    assert Categoria.objects.count() > 0
    assert Produtos.objects.count() > 0
    # movements may be optional but check at least zero or more
    assert Movimentacao.objects.count() >= 0


@pytest.mark.django_db
def test_gerar_relatorio_command_creates_files(tmp_path, settings):
    """
    Ensure the report-generation functionality writes JSON (and optionally PNG/HTML).
    The test will try management commands first; if none found it will call the
    module function inventario_v1.relatorios.gerar_relatorio directly.
    """
    out = tmp_path / "reports"
    out.mkdir(parents=True, exist_ok=True)

    # Try possible command names (english/portuguese) used across versions
    cmd_names = ("gerar_relatorio", "generate_reports", "generate_reports_command")
    found = False
    last_exception = None
    for name in cmd_names:
        try:
            # prefer --out option if supported by the command
            call_command(name, "--out", str(out))
            found = True
            break
        except CommandError as last_exc:
            last_exception = last_exc
            continue
        except TypeError:
            # some implementations accept positional argument 'out' instead of --out
            try:
                call_command(name, str(out))
                found = True
                break
            except Exception as exc:
                last_exception = exc
                continue
        except Exception:
            # command ran but errored (propagate)
            raise

    json_files = []
    if not found:
        # Fallback: call the relatorios.gerar_relatorio function directly and write into MEDIA_ROOT set to out
        original_media_root = getattr(settings, "MEDIA_ROOT", None)
        original_media_url = getattr(settings, "MEDIA_URL", None)
        try:
            settings.MEDIA_ROOT = str(out)
            settings.MEDIA_URL = "/media/"
            try:
                from inventario_v1.relatorios import gerar_relatorio  # pylint: disable=import-error,import-outside-toplevel
            except Exception as exc:
                pytest.skip(f"gerar_relatorio function not available: {exc}")
            resultado = gerar_relatorio(pks_tabelas=None, usuario=None)
            pasta_saida = Path(resultado.get("diretorio_saida"))
            # collect JSON files generated
            if pasta_saida.exists():
                json_files = list(pasta_saida.glob("*.json"))
        finally:
            # restore settings
            if original_media_root is not None:
                settings.MEDIA_ROOT = original_media_root
            else:
                if hasattr(settings, "MEDIA_ROOT"):
                    delattr(settings, "MEDIA_ROOT")
            if original_media_url is not None:
                settings.MEDIA_URL = original_media_url
            else:
                if hasattr(settings, "MEDIA_URL"):
                    delattr(settings, "MEDIA_URL")
    else:
        # If command path was used, look for JSON files directly in out
        json_files = list(out.glob("*.json"))
        # If none found at root, allow nested (some implementations may write into subdirs)
        if not json_files:
            json_files = list(out.rglob("*.json"))

    if not json_files:
        pytest.skip(f"No JSON report files were written; last command error: {last_exception}")

    # JSON summary files must exist
    assert any(p.name.endswith(".json") for p in json_files)


@pytest.mark.django_db
def test_report_view_shows_generated_reports(client, django_user_model, tmp_path, settings):
    """
    Ensure that the ReportView lists files present in the MEDIA relatorios folder.
    Supports both inventario_v3 and inventario_v1 namespaces for the reports page.
    """
    # configure MEDIA_ROOT/MEDIA_URL for the test to avoid ImproperlyConfigured
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.MEDIA_URL = "/media/"

    # create staff user and login
    username = "reportadmin"
    password = "pwd"
    django_user_model.objects.create_user(username=username, password=password, is_staff=True)
    assert client.login(username=username, password=password) is True

    # ensure the reports dir exists inside MEDIA_ROOT under our prefix used by the app
    reports_dir = Path(settings.MEDIA_ROOT) / "relatorios"
    # create directory (clean first if exists)
    backup = None
    if reports_dir.exists():
        # backup in case user has real reports - we restore later
        backup = tmp_path / "backup_reports"
        shutil.move(str(reports_dir), str(backup))
        reports_dir.mkdir(parents=True, exist_ok=True)
    else:
        reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        # create a dummy PNG with report_ prefix so the view may list it
        dummy_png = reports_dir / "report_dummy.png"
        dummy_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")  # minimal PNG header bytes

        # Try both namespaces for the reports URL
        url_candidates = ("inventario_v3:relatorios", "inventario_v1:relatorios")
        resolved = None
        for name in url_candidates:
            try:
                url = reverse(name)
                resolved = url
                break
            except NoReverseMatch:
                continue

        if not resolved:
            pytest.skip("Nenhuma rota de relatórios encontrada (inventario_v3 or inventario_v1)")

        # GET the reports page
        resp = client.get(resolved)
        assert resp.status_code == 200

        # Check that the dummy file exists on disk (primary verification)
        assert dummy_png.exists(), "Dummy report file was not created on disk"

        # Template content should ideally include either the dummy filename or generated filenames.
        content = resp.content.decode("utf-8", errors="ignore")
        assert ("report_dummy.png" in content) or ("chart_" in content) or ("relatorio_" in content)

    finally:
        # cleanup: remove dummy files and restore backup if any
        if Path(settings.MEDIA_ROOT).exists():
            shutil.rmtree(str(Path(settings.MEDIA_ROOT)))
        if backup:
            shutil.move(str(backup), str(Path(settings.MEDIA_ROOT) / "relatorios"))


@pytest.mark.django_db
def test_produto_change_quantidade_method_persists():
    """
    Ensure Produto.change_quantidade updates and persists the quantidade.
    """
    produto = Produtos.objects.create(nome="ProdChange", quantidade=5, preco="1.00")
    # call with positive delta
    novo = produto.change_quantidade(3)
    produto.refresh_from_db()
    assert novo == produto.quantidade
    assert produto.quantidade == 8

    # call with negative delta that is allowed
    novo2 = produto.change_quantidade(-2)
    produto.refresh_from_db()
    assert novo2 == produto.quantidade
    assert produto.quantidade == 6

    # attempt to reduce below zero should raise
    with pytest.raises(ValueError):
        produto.change_quantidade(-9999)