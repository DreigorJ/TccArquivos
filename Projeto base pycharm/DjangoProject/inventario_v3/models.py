from decimal import Decimal
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class Categoria(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nome


class TabelaProdutos(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    publico = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.nome


class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    quantidade = models.IntegerField(default=0)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL)
    tabelas = models.ManyToManyField(TabelaProdutos, related_name="produtos", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # keep a useful representation used in logs/tests
        return f"{self.nome} ({self.quantidade})"

    # compatibility with templates that expect produto.name / produto.price
    @property
    def name(self):
        return self.nome

    @property
    def price(self):
        return self.preco

    def change_quantidade(self, delta: int):
        """
        Ajusta a quantidade do produto em `delta` (positivo ou negativo),
        valida para não ficar abaixo de zero e persiste a alteração.
        Retorna a nova quantidade.
        Lança ValueError se a operação deixaria a quantidade abaixo de zero.
        """
        if delta is None:
            raise ValueError("Delta inválido")
        new_q = self.quantidade + int(delta)
        if new_q < 0:
            raise ValueError("Quantidade resultante não pode ser negativa")
        self.quantidade = new_q
        self.save(update_fields=["quantidade"])
        return self.quantidade


class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    funcao = models.CharField(max_length=100, default="Usuário")
    ativo = models.BooleanField(default=True)
    current_tabela = models.ForeignKey(
        TabelaProdutos, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.get_username()} - {self.funcao}"


class AcessoTabela(models.Model):
    class Niveis:
        NENHUM = "nenhum"
        LEITURA = "leitura"
        ESCRITA = "escrita"
        ADMINISTRADOR = "administrador"

        CHOICES = (
            (NENHUM, "Nenhum"),
            (LEITURA, "Leitura"),
            (ESCRITA, "Escrita"),
            (ADMINISTRADOR, "Administrador"),
        )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="acessos")
    tabela = models.ForeignKey(TabelaProdutos, on_delete=models.CASCADE, related_name="acessos")
    nivel = models.CharField(max_length=16, choices=Niveis.CHOICES, default=Niveis.NENHUM)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.get_username()} -> {self.tabela.nome} ({self.nivel})"


class Movimento(models.Model):
    MOV_ENT = "ENTRADA"
    MOV_SAI = "SAIDA"
    MOV_CHOICES = ((MOV_ENT, "Entrada"), (MOV_SAI, "Saída"))

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="movimentos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    tipo_movimento = models.CharField(max_length=10, choices=MOV_CHOICES)
    quantidade = models.IntegerField()
    motivo = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo_movimento} {self.quantidade} - {self.produto.nome}"

    def clean(self):
        """
        Valida regras básicas antes de salvar:
        - quantidade deve ser positiva
        - em saída, produto deve ter estoque suficiente
        """
        if self.quantidade is None:
            raise ValidationError("Quantidade inválida")
        if not isinstance(self.quantidade, int):
            try:
                self.quantidade = int(self.quantidade)
            except Exception:
                raise ValidationError("Quantidade deve ser um inteiro")
        if self.quantidade <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")

        if not self.produto_id:
            raise ValidationError("Movimento precisa referenciar um produto")

        if self.tipo_movimento == self.MOV_SAI:
            prod = Produto.objects.select_for_update().filter(pk=self.produto_id).first()
            if prod is None:
                raise ValidationError("Produto inexistente")
            if prod.quantidade < self.quantidade:
                raise ValidationError("Estoque insuficiente para esta saída")

    def save(self, *args, **kwargs):
        """
        Valida, aplica a alteração de estoque de forma atômica e salva o movimento.
        Retorna a própria instância ao final.
        """
        # valida (pode levantar ValidationError)
        self.full_clean()

        with transaction.atomic():
            produto = Produto.objects.select_for_update().get(pk=self.produto_id)

            if self.tipo_movimento == self.MOV_ENT:
                produto.quantidade = produto.quantidade + int(self.quantidade)
            else:
                produto.quantidade = produto.quantidade - int(self.quantidade)

            if produto.quantidade < 0:
                raise ValidationError("Operação deixaria estoque negativo")

            produto.save(update_fields=["quantidade"])
            super().save(*args, **kwargs)

        return self


# Signal: criar PerfilUsuario automaticamente ao criar um User
@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance=None, created=False, **kwargs):
    """
    Defensive: try to create PerfilUsuario only when possible.
    If PerfilUsuario table/migration is not present yet, swallow the error
    (this allows commands that run before the app migrations to proceed).
    """
    if not created or instance is None:
        return
    try:
        # perform creation but guard against DB errors (table may not exist yet)
        PerfilUsuario.objects.get_or_create(usuario=instance)
    except Exception as e:
        # log debug and continue; do not raise to avoid breaking management commands
        logger.debug("PerfilUsuario creation skipped for user %s: %s", getattr(instance, "pk", "<no-pk>"), e)