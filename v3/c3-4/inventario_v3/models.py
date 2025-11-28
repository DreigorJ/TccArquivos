from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone

Usuario = get_user_model()

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)[:100]
            slug = base
            i = 1
            # evita colisões com outro registro (exclui self)
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    quantidade = models.IntegerField(default=0)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"

    def change_quantidade(self, quantidade, usuario=None, motivo=''):
        """
        Ajusta a quantidade do produto de forma simples e previsível:
        - aceita positivo para entrada e negativo para saída
        - valida para não ficar negativo
        - persiste a quantidade e retorna o novo valor
        """
        new = (self.quantidade or 0) + int(quantidade)
        if new < 0:
            raise ValueError("Quantidade não pode ficar negativa")
        self.quantidade = new
        self.save(update_fields=["quantidade"])
        return self.quantidade

class Movimento(models.Model):
    MOV_ENT = 'ENTRADA'
    MOV_SAI = 'SAIDA'
    TIPOS_DE_MOVIMENTOS = [
        (MOV_ENT, 'Entrada'),
        (MOV_SAI, 'Saída'),
    ]

    produto = models.ForeignKey(Produto, related_name='movimentos', on_delete=models.CASCADE)
    tipo_movimento = models.CharField(max_length=50, choices=TIPOS_DE_MOVIMENTOS)
    quantidade = models.PositiveIntegerField()
    motivo = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        t = 'Entrada' if self.tipo_movimento == self.MOV_ENT else 'Saída'
        criado = self.criado_em.strftime('%d-%m-%Y - %H:%M') if self.criado_em else 'n/a'
        produto_nome = self.produto.nome if self.produto_id else 'n/a'
        return f"{produto_nome}: {t} {self.quantidade} @ {criado}"

    def clean(self):
        # validação antes de salvar
        if self.quantidade is None:
            raise ValidationError({"quantidade": "Obrigatório"})
        try:
            qtd = int(self.quantidade)
        except Exception:
            raise ValidationError({"quantidade": "Deve ser número inteiro"})
        if qtd <= 0:
            raise ValidationError({"quantidade": "Quantidade deve ser positiva"})

    def save(self, *args, **kwargs):
        """
        Ao salvar um Movimento novo, atualiza a quantidade do produto
        (evita criar movimentos duplicados em updates).
        """
        novo_movimento = self.pk is None
        if not novo_movimento:
            # update: apenas salva o movimento sem tocar no estoque
            return super().save(*args, **kwargs)

        # valida antes de tocar no banco
        self.full_clean()  # levantará ValidationError se inválido

        # atualiza produto e grava movimento atomically
        with transaction.atomic():
            produto = self.produto
            if self.tipo_movimento == self.MOV_ENT:
                produto.quantidade = produto.quantidade + self.quantidade
                produto.save(update_fields=["quantidade"])
                super().save(*args, **kwargs)
            elif self.tipo_movimento == self.MOV_SAI:
                if produto.quantidade < self.quantidade:
                    raise ValueError("Estoque insuficiente")
                produto.quantidade = produto.quantidade - self.quantidade
                produto.save(update_fields=["quantidade"])
                super().save(*args, **kwargs)
            else:
                raise ValidationError({"tipo_movimento": "Tipo inválido"})