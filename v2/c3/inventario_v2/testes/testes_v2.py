# inventario_v2/testes/test_populacao_categorias.py
import pytest
from django.core.management import call_command
from django.apps import apps

@pytest.mark.django_db
def test_reset_and_populate_creates_categories_products_and_movements():
    """
    Executa o comando de reset e população e verifica se categorias, produtos
    e movimentações de exemplo foram criadas.
    """
    # rodar sem criar/atualizar superuser para não interferir em ambientes CI
    call_command("populacao_teste", "--noadmin")

    Categoria = apps.get_model("inventario_v2", "Categoria")
    Produtos = apps.get_model("inventario_v2", "Produtos")
    Movimentacao = apps.get_model("inventario_v2", "Movimentacao")

    # pelo menos uma categoria deve existir (se modelo presente)
    if Categoria.objects.exists():
        assert Categoria.objects.count() >= 1

    # produtos foram criados
    assert Produtos.objects.count() >= 1

    # ao menos um produto deve ter categoria não-nula (pois amostras atribuíram categorias)
    assert Produtos.objects.filter(categoria__isnull=False).exists()

    # movimentações devem ter sido criadas conforme a amostra
    assert Movimentacao.objects.exists()


@pytest.mark.django_db
def test_deleting_category_sets_products_category_null():
    """
    Verifica o comportamento on_delete=SET_NULL:
    - cria categoria e produto associado
    - deleta a categoria
    - produto deve ficar com categoria NULL
    """
    Categoria = apps.get_model("inventario_v2", "Categoria")
    Produtos = apps.get_model("inventario_v2", "Produtos")

    cat = Categoria.objects.create(nome="TesteCat", descricao="cat teste")
    prod = Produtos.objects.create(nome="ProdutoComCat", quantidade=5, preco=1.23, categoria=cat)

    # sanity checks
    assert prod.categoria_id == cat.id

    # delete category
    cat.delete()

    prod.refresh_from_db()
    assert prod.categoria is None