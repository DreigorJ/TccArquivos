from django.db import models

class Produtos(models.Model):
    nome = models.CharField("Nome", max_length=200)
    descricao = models.TextField("Descrição", blank=True)
    quantidade = models.IntegerField("Quantidade", default=0)
    preco = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2, default=0.00)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"