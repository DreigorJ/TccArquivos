from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError


class Categoria(models.Model):
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, default="")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("nome",)
        verbose_name_plural = "categorias"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome) or "categoria"
            slug = base
            counter = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    quantidade = models.IntegerField(default=0)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("nome",)

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"

    # compatibilidade com templates que usam produto.name / produto.price
    @property
    def name(self):
        return self.nome

    @property
    def price(self):
        return self.preco

    def change_quantidade(self, delta):
        new_q = int(self.quantidade) + int(delta)
        if new_q < 0:
            raise ValueError("Quantidade resultante não pode ser negativa.")
        self.quantidade = new_q
        self.save(update_fields=["quantidade"])
        return self.quantidade


class Movimento(models.Model):
    MOV_ENT = "ENTRADA"
    MOV_SAI = "SAIDA"
    TIPO_CHOICES = ((MOV_ENT, "Entrada"), (MOV_SAI, "Saída"))

    # related_name para permitir produto.movimentos.all() nos templates
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="movimentos")
    quantidade = models.PositiveIntegerField()
    tipo_movimento = models.CharField(max_length=10, choices=TIPO_CHOICES)
    motivo = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ("-criado_em",)

    def __str__(self):
        return f"{self.produto} - {self.tipo_movimento} {self.quantidade}"

    def clean(self):
        if self.quantidade is None:
            raise ValidationError("Quantidade deve ser informada e positiva.")
        if int(self.quantidade) <= 0:
            raise ValidationError("Quantidade deve ser um inteiro positivo.")
        if getattr(self, "produto_id", None) is None:
            return
        try:
            produto = Produto.objects.get(pk=self.produto_id)
        except Produto.DoesNotExist:
            raise ValidationError("Produto inválido.")
        if self.tipo_movimento == self.MOV_SAI and int(self.quantidade) > int(produto.quantidade):
            raise ValidationError(f"Não há estoque suficiente em '{produto.nome}' para criar movimento de saída.")

    def save(self, *args, **kwargs):
        is_create = self.pk is None
        self.full_clean()
        if is_create and getattr(self, "produto_id", None) is not None:
            produto = Produto.objects.get(pk=self.produto_id)
            if self.tipo_movimento == self.MOV_ENT:
                produto.quantidade = int(produto.quantidade) + int(self.quantidade)
                produto.save(update_fields=["quantidade"])
            elif self.tipo_movimento == self.MOV_SAI:
                if int(self.quantidade) > int(produto.quantidade):
                    raise ValidationError(f"Não há estoque suficiente em '{produto.nome}' para criar movimento de saída.")
                produto.quantidade = int(produto.quantidade) - int(self.quantidade)
                produto.save(update_fields=["quantidade"])
        super().save(*args, **kwargs)