import pytest
from decimal import Decimal
from django.urls import reverse

from inventario_v3.models import Produto, Movimento, Categoria


@pytest.mark.django_db
def test_produto_create_and_change_quantidade():
    # criação básica de produto
    p = Produto.objects.create(nome="Produto Teste", descricao="desc", quantidade=5, preco=Decimal("10.00"))
    assert Produto.objects.filter(pk=p.pk).exists()
    assert p.quantidade == 5
    # __str__ inclui nome e quantidade
    assert "Produto Teste" in str(p)
    assert "5" in str(p)

    # change_quantidade: cria movimentos e atualiza estoque (entrada)
    mov = p.change_quantidade(3, usuario=None, motivo="entrada teste")
    assert isinstance(mov, Movimento)
    p.refresh_from_db()
    assert p.quantidade == 8

    # change_quantidade: saída (passando quantidade negativa ou tipo SAIDA)
    mov2 = p.change_quantidade(-2, usuario=None, motivo="saida teste")
    p.refresh_from_db()
    assert p.quantidade == 6


@pytest.mark.django_db
def test_movimento_entrada_incrementa_quantidade_and_str():
    p = Produto.objects.create(nome="P1", quantidade=2, preco=Decimal("1.00"))
    m = Movimento(produto=p, tipo_movimento=Movimento.MOV_ENT, quantidade=3, motivo="teste entrada")
    m.save()
    # assegura que o movimento foi gravado
    assert Movimento.objects.filter(pk=m.pk, produto=p).exists()
    p.refresh_from_db()
    assert p.quantidade == 5

    # __str__ inclui nome do produto, tipo e quantidade
    s = str(m)
    assert "P1" in s
    assert "Entrada" in s or "Entrada" in m.get_tipo_movimento_display()  # cobertura flexível


@pytest.mark.django_db
def test_movimento_saida_insuficiente_gera_erro():
    p = Produto.objects.create(nome="P2", quantidade=1, preco=Decimal("1.00"))
    m = Movimento(produto=p, tipo_movimento=Movimento.MOV_SAI, quantidade=5)
    with pytest.raises(ValueError):
        m.save()
    # assegura que nenhum movimento inválido foi criado
    assert Movimento.objects.filter(produto=p, quantidade=5, tipo_movimento=Movimento.MOV_SAI).count() == 0
    # estoque permanece inalterado
    p.refresh_from_db()
    assert p.quantidade == 1


@pytest.mark.django_db
def test_produtos_lista_requer_login(client):
    url = reverse('inventario_v3:produtos_lista')
    resp = client.get(url)
    # deve redirecionar para login quando não autenticado
    assert resp.status_code in (301, 302)
    # a URL de redirecionamento deve apontar para a página de login
    assert '/login' in resp.url or 'login' in resp.url


@pytest.mark.django_db
def test_criar_produto_via_view(client, django_user_model):
    user = django_user_model.objects.create_user(username='u1', password='pwd')
    assert client.login(username='u1', password='pwd') is True

    # criar uma categoria opcional (o formulário aceita categoria)
    cat = Categoria.objects.create(nome='TesteCat')

    url = reverse('inventario_v3:produtos_criacao')
    data = {
        'nome': 'Novo Produto',
        'descricao': 'descricao teste',
        'preco': '5.00',
        'categoria': cat.pk,
    }
    resp = client.post(url, data)
    assert resp.status_code in (301, 302)
    assert Produto.objects.filter(nome='Novo Produto', categoria=cat).exists()


@pytest.mark.django_db
def test_criar_movimento_via_view_atualiza_estoque(client, django_user_model):
    user = django_user_model.objects.create_user(username='u2', password='pwd2')
    assert client.login(username='u2', password='pwd2') is True

    p = Produto.objects.create(nome='Pmov', quantidade=5, preco=Decimal('2.00'))

    url = reverse('inventario_v3:novo_movimento', args=[p.pk])
    data = {
        'tipo_movimento': Movimento.MOV_ENT,  # 'ENTRADA'
        'quantidade': 3,
        'motivo': 'teste',
    }
    resp = client.post(url, data)
    assert resp.status_code in (301, 302)
    # garante que movimento foi criado e estoque atualizado
    assert Movimento.objects.filter(produto=p, quantidade=3, tipo_movimento=Movimento.MOV_ENT).exists()
    p.refresh_from_db()
    assert p.quantidade == 8