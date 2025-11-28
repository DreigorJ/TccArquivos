from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.db.models import F

Usuario = get_user_model()

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'categories'

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
        Movimento.objects.create(produto=self, quantidade=quantidade, motivo=motivo, usuario=usuario)
        self.quantidade = models.F('quantidade') + quantidade
        self.save(update_fields=['quantidade'])

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
        return f"{self.produto.nome}: {t} {self.quantidade} @ {self.criado_em:%d-%m-%Y - %H:%M}"

    def save(self, *args, **kwargs):
        """
        Ao salvar um Movimento novo, atualiza a quantidade do produto
        (evita criar movimentos duplicados em updates).
        """
        novo_movimento = self.pk is None
        if not novo_movimento:
            # Se for update simples, não alteramos o estoque aqui.
            return super().save(*args, **kwargs)

        # Aplicar alteração no estoque de forma atômica e segura
        with transaction.atomic():
            # bloquear a linha do produto
            prod = Produto.objects.select_for_update().get(pk=self.produto.pk)
            if self.tipo_movimento == self.MOV_ENT:
                prod.quantidade = F('quantidade') + self.quantidade
                prod.save(update_fields=['quantidade'])
            else:  # saída
                # depois de usar F, para comparar precisamos fazer refresh_from_db ou checar antes
                # vamos checar quantidade corrente antes de usar F
                current_q = prod.quantidade
                if current_q < self.quantidade:
                    raise ValueError("Quantidade insuficiente em estoque para esta saída.")
                prod.quantidade = F('quantidade') - self.quantidade
                prod.save(update_fields=['quantidade'])
            # garante que o movimento é salvo após a atualização do produto
            return super().save(*args, **kwargs)