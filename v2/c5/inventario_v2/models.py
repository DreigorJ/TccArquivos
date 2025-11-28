from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Categoria(models.Model):
    nome = models.CharField("Nome", max_length=120, unique=True)
    descricao = models.TextField("Descrição", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TabelaProdutos(models.Model):
    """
    'Tables' of products: permite segregar produtos em tabelas diferentes e controlar
    acesso por usuário. Um usuário pode ter acesso a várias tabelas.
    """
    nome = models.CharField("Nome da tabela", max_length=150, unique=True)
    descricao = models.TextField("Descrição", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Proprietário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tabelas_own"
    )
    acessos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuários com acesso",
        blank=True,
        related_name="tabelas_acesso"
    )

    class Meta:
        verbose_name = "Tabela de Produtos"
        verbose_name_plural = "Tabelas de Produtos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class PerfilUsuario(models.Model):
    """
    Perfil associado ao usuário para controle de papéis (roles).
    """
    ROLE_ADMIN = "ADMIN"
    ROLE_OPERATOR = "OPERATOR"
    ROLE_VIEWER = "VIEWER"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrador"),
        (ROLE_OPERATOR, "Operador"),
        (ROLE_VIEWER, "Leitor"),
    ]

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    papel = models.CharField("Papel", max_length=20, choices=ROLE_CHOICES, default=ROLE_OPERATOR)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Perfil do Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return f"{self.usuario.username} — {self.get_papel_display()}"


class Produtos(models.Model):
    nome = models.CharField("Nome", max_length=200)
    descricao = models.TextField("Descrição", blank=True)
    categoria = models.ForeignKey(Categoria, verbose_name="Categoria", null=True, blank=True, on_delete=models.SET_NULL, related_name="produtos")
    tabela = models.ForeignKey(TabelaProdutos, verbose_name="Tabela", null=True, blank=True, on_delete=models.SET_NULL, related_name="produtos")
    quantidade = models.IntegerField("Quantidade", default=0)
    preco = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2, default=0.00)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"

    def change_quantidade(self, delta, allow_negative=False):
        novo_valor = (self.quantidade or 0) + int(delta)
        if not allow_negative and novo_valor < 0:
            raise ValidationError("Operação resultaria em quantidade negativa.")
        self.quantidade = novo_valor
        self.save(update_fields=["quantidade", "atualizado_em"])
        logger.info("Produto %s: quantidade alterada em %s -> %s", self.pk, delta, self.quantidade)
        return self.quantidade


class Movimentacao(models.Model):
    TIPO_ENTRADA = "ENTRADA"
    TIPO_SAIDA = "SAIDA"
    TIPO_CHOICES = [
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SAIDA, "Saída"),
    ]

    produto = models.ForeignKey(Produtos, on_delete=models.PROTECT, related_name="movimentacoes")
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField("Quantidade")
    descricao = models.TextField("Descrição", blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    # auditoria de estoque
    quantidade_antes = models.IntegerField("Quantidade antes", null=True, blank=True)
    quantidade_depois = models.IntegerField("Quantidade depois", null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def clean(self):
        if self.tipo == self.TIPO_SAIDA and self.pk is None:
            if self.produto and self.quantidade > self.produto.quantidade:
                raise ValidationError("Quantidade de saída maior que o estoque disponível.")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        produto = self.produto
        self.quantidade_antes = produto.quantidade

        if not is_new:
            previous = Movimentacao.objects.get(pk=self.pk)
            if previous.tipo == self.TIPO_ENTRADA:
                produto.quantidade -= previous.quantidade
            else:
                produto.quantidade += previous.quantidade

        if self.tipo == self.TIPO_ENTRADA:
            produto.quantidade += self.quantidade
        else:
            if self.quantidade > produto.quantidade:
                raise ValidationError("Não é possível realizar saída: estoque insuficiente.")
            produto.quantidade -= self.quantidade

        produto.save()
        self.quantidade_depois = produto.quantidade

        super().save(*args, **kwargs)

        logger.info(
            "Movimentação %s: produto=%s, tipo=%s, qtd=%s, antes=%s, depois=%s, usuario=%s",
            self.pk, produto.pk, self.tipo, self.quantidade, self.quantidade_antes, self.quantidade_depois, getattr(self.usuario, "username", None),
        )

    def delete(self, *args, **kwargs):
        produto = self.produto
        if self.tipo == self.TIPO_ENTRADA:
            produto.quantidade -= self.quantidade
        else:
            produto.quantidade += self.quantidade
        produto.save()
        logger.info("Deletando movimentação %s: revertendo estoque produto=%s, nova_qtd=%s", self.pk, produto.pk, produto.quantidade)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.quantidade} — {self.produto.nome}"