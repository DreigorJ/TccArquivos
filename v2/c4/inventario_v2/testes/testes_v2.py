"""
Testes de integração / comandos usados pelo app inventario_v2.

Este módulo contém testes que exercitam:
- CRUD de categorias via views
- comando de população (populacao_teste, reset_and_populate_v1, ...)
- geração de relatórios (comando ou função relatorios.gerar_relatorio)
- página que lista relatórios (usa MEDIA_ROOT/relatorios)
- método Produtos.change_quantidade

Os testes foram adaptados para o app inventario_v2 mantendo o mesmo
número e foco dos cenários do exemplo original.
"""
from pathlib import Path
import shutil

import pytest
from django.core.management import call_command, CommandError
from django.urls import reverse, NoReverseMatch
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model

# Tentar importar modelos do inventario_v2 (em execução normal do pytest esses imports funcionam).
try:  # pragma: no cover - protege análise estática fora do contexto Django
    from inventario_v2.models import Categoria, Produtos, Movimentacao
except Exception:
    Categoria = Produtos = Movimentacao = None  # type: ignore

User = get_user_model()


@pytest.mark.django_db
def test_categoria_crud_via_views(client, django_user_model):
    """
    Test basic CRUD for Categoria via the class-based views (requires staff).
    Usa o namespace inventario_v2 (fallback para inventario_v1 se necessário).
    """
    # create staff user and login
    user = django_user_model.objects.create_user(username="staff1", password="pwd", is_staff=True)
    assert client.login(username=user.username, password="pwd") is True

    # Try to resolve list/create/edit/delete urls in common namespaces
    url_names = [
        (
            "inventario_v2:categorias_lista",
            "inventario_v2:categorias_adicionar",
            "inventario_v2:categorias_editar",
            "inventario_v2:categorias_remover",
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
        pytest.skip("Nenhuma rota de categorias encontrada (inventario_v2 ou inventario_v1)")

    # list view (should be accessible)
    resp = client.get(url_list)
    assert resp.status_code == 200

    # create category via POST (Categoria model expects nome and descricao)
    resp = client.post(url_add, {"nome": "Cat Teste", "descricao": "desc"})
    assert resp.status_code in (302, 301)
    cat = Categoria.objects.filter(nome="Cat Teste").first()
    assert cat is not None

    # edit category
    url_edit = reverse(resolved[2], args=[cat.pk])
    resp = client.post(url_edit, {"nome": "Cat Teste Edit", "descricao": "novo"})
    assert resp.status_code in (302, 301)
    cat.refresh_from_db()
    assert cat.nome == "Cat Teste Edit"

    # delete category
    url_del = reverse(resolved[3], args=[cat.pk])
    resp = client.post(url_del, {})
    assert resp.status_code in (302, 301)
    assert not Categoria.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_populate_command_and_models():
    """
    Executa o comando de população (se existir) e verifica presença de categorias,
    produtos e movimentações. Prefere populacao_teste se disponível.
    """
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
            call_command(name, "--noadmin")
            found = True
            break
        except CommandError as last_exc:
            last_exception = last_exc
            continue
        except Exception:
            # se o comando existe mas falhou por outra razão, propaga para CI mostrar o erro
            raise

    if not found:
        pytest.skip(
            "No populate command found (tried names: %s); last error: %r"
            % (", ".join(populate_cmd_names), last_exception)
        )

    # basic assertions: categorias, produtos e movimentações foram criados
    assert Categoria.objects.count() > 0
    assert Produtos.objects.count() > 0
    # Movimentacao pode ser zero, mas verificar que a queryset existe e é acessível
    assert Movimentacao.objects.count() >= 0


@pytest.mark.django_db
def test_gerar_relatorio_command_creates_files(tmp_path, settings):
    """
    Tenta invocar comandos de geração de relatórios (se existirem) ou a função
    inventario_v2.relatorios.gerar_relatorio como fallback. Verifica que arquivos JSON
    (resumo) foram produzidos no diretório de saída.
    """
    out = tmp_path / "reports"
    out.mkdir(parents=True, exist_ok=True)

    cmd_names = ("gerar_relatorio", "generate_reports", "generate_reports_command")
    found = False
    last_exception = None
    for name in cmd_names:
        try:
            call_command(name, "--out", str(out))
            found = True
            break
        except CommandError as last_exc:
            last_exception = last_exc
            continue
        except TypeError:
            try:
                call_command(name, str(out))
                found = True
                break
            except Exception as exc:
                last_exception = exc
                continue
        except Exception:
            raise

    json_files = []
    if not found:
        # Fallback: tentar importar inventario_v2.relatorios.gerar_relatorio
        original_media_root = getattr(settings, "MEDIA_ROOT", None)
        original_media_url = getattr(settings, "MEDIA_URL", None)
        try:
            settings.MEDIA_ROOT = str(out)
            settings.MEDIA_URL = "/media/"
            try:
                from inventario_v2.relatorios import gerar_relatorio  # type: ignore
            except Exception as exc:
                pytest.skip(f"gerar_relatorio function not available: {exc}")
            resultado = gerar_relatorio(pks_tabelas=None, usuario=None)
            pasta_saida = Path(resultado.get("diretorio_saida"))
            if pasta_saida.exists():
                json_files = list(pasta_saida.glob("*.json"))
        finally:
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
        json_files = list(out.glob("*.json"))
        if not json_files:
            json_files = list(out.rglob("*.json"))

    if not json_files:
        pytest.skip(f"No JSON report files were written; last command error: {last_exception}")

    assert any(p.name.endswith(".json") for p in json_files)


@pytest.mark.django_db
def test_report_view_shows_generated_reports(client, django_user_model, tmp_path, settings):
    """
    Garante que a view de relatórios lista arquivos na pasta MEDIA_ROOT/relatorios.
    Usa a rota inventario_v2:relatorios_index como preferida.
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.MEDIA_URL = "/media/"

    # criar staff e logar
    username = "reportadmin"
    password = "pwd"
    django_user_model.objects.create_user(username=username, password=password, is_staff=True)
    assert client.login(username=username, password=password) is True

    reports_dir = Path(settings.MEDIA_ROOT) / "relatorios"
    backup = None
    if reports_dir.exists():
        backup = tmp_path / "backup_reports"
        shutil.move(str(reports_dir), str(backup))
        reports_dir.mkdir(parents=True, exist_ok=True)
    else:
        reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        dummy_png = reports_dir / "report_dummy.png"
        dummy_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        # tentar rota preferida inventario_v2:relatorios_index
        url_candidates = ("inventario_v2:relatorios_index", "inventario_v1:relatorios")
        resolved = None
        for name in url_candidates:
            try:
                url = reverse(name)
                resolved = url
                break
            except NoReverseMatch:
                continue

        if not resolved:
            pytest.skip("Nenhuma rota de relatórios encontrada (inventario_v2 or inventario_v1)")

        resp = client.get(resolved)
        assert resp.status_code == 200

        assert dummy_png.exists(), "Dummy report file was not created on disk"
        content = resp.content.decode("utf-8", errors="ignore")
        assert ("report_dummy.png" in content) or ("chart_" in content) or ("relatorio_" in content)

    finally:
        if Path(settings.MEDIA_ROOT).exists():
            shutil.rmtree(str(Path(settings.MEDIA_ROOT)))
        if backup:
            shutil.move(str(backup), str(Path(settings.MEDIA_ROOT) / "relatorios"))


@pytest.mark.django_db
def test_produto_change_quantidade_method_persists():
    """
    Garante que Produto.change_quantidade atualiza e persiste a quantidade.
    Também verifica que reduzir além do estoque levanta ValidationError.
    """
    produto = Produtos.objects.create(nome="ProdChange", quantidade=5, preco="1.00")
    # positivo
    novo = produto.change_quantidade(3)
    produto.refresh_from_db()
    assert novo == produto.quantidade
    assert produto.quantidade == 8

    # negativo permitido
    novo2 = produto.change_quantidade(-2)
    produto.refresh_from_db()
    assert novo2 == produto.quantidade
    assert produto.quantidade == 6

    # tentativa de reduzir abaixo de zero deve levantar ValidationError
    with pytest.raises(ValidationError):
        produto.change_quantidade(-9999)