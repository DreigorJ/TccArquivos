from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import F

modeloUsuario = get_user_model()

class Produtos(models.Model):
    nome = models.CharField("Nome", max_length=200)
    descricao = models.TextField("Descrição", blank=True)
    quantidade = models.IntegerField("Quantidade", default=0)
    preco = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2, default=0.00)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"

    def change_quantidade(self, delta: int):
        """
        Ajusta a quantidade do produto em delta (positivo para aumentar, negativo para diminuir).
        Executa a atualização com F-expression dentro de uma transação atômica para evitar
        condições de corrida e garantir visibilidade entre conexões.
        Lança ValueError se a operação resultaria em quantidade negativa.
        Retorna a nova quantidade (int).
        """
        if not isinstance(delta, int):
            raise TypeError("delta deve ser inteiro")

        with transaction.atomic():
            # aplica a alteração com F expression
            Produtos.objects.filter(pk=self.pk).update(quantidade=F("quantidade") + int(delta))
            # buscar com select_for_update para validar e obter valor atualizado
            produto_atual = Produtos.objects.select_for_update().get(pk=self.pk)
            if produto_atual.quantidade < 0:
                # reverter a alteração realizada
                Produtos.objects.filter(pk=self.pk).update(quantidade=F("quantidade") - int(delta))
                raise ValueError("Operação resultaria em quantidade negativa.")
            # atualizar a instância em memória para refletir o novo valor
            self.quantidade = produto_atual.quantidade
            return int(self.quantidade)


class PerfilUsuario(models.Model):
    ROLE_ADMINISTRADOR = "administrador"
    ROLE_OPERATOR = "operator"
    ROLE_CHOICES = [
        (ROLE_ADMINISTRADOR, "Administrador"),
        (ROLE_OPERATOR, "Operador"),
    ]

    usuario = models.OneToOneField(modeloUsuario, on_delete=models.CASCADE, related_name="perfil")
    papel = models.CharField("Papel", max_length=20, choices=ROLE_CHOICES, default=ROLE_OPERATOR)
    observacao = models.TextField("Observação", blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_papel_display()}"


class Movimentacao(models.Model):
    TIPO_ENTRADA = "E"
    TIPO_SAIDA = "S"
    TIPO_CHOICES = [
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SAIDA, "Saída"),
    ]

    produto = models.ForeignKey(Produtos, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField("Tipo", max_length=1, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField("Quantidade")
    usuario = models.ForeignKey(modeloUsuario, on_delete=models.SET_NULL, null=True, blank=True)
    observacao = models.TextField("Observação", blank=True)
    criado_em = models.DateTimeField("Registrado em", default=timezone.now)

    def __str__(self):
        return f"{self.get_tipo_display()} {self.quantidade} x {self.produto.nome}"

    def aplicar_no_estoque(self):
        """
        Atualiza o estoque usando F expressions dentro de uma transação.
        Reverte a operação se o resultado ficar negativo e levanta ValueError.
        """
        with transaction.atomic():
            if self.tipo == self.TIPO_ENTRADA:
                Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") + int(self.quantidade))
            else:
                Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") - int(self.quantidade))

            # verificar novo valor
            produto_atual = Produtos.objects.select_for_update().get(pk=self.produto_id)
            if produto_atual.quantidade < 0:
                # reverter a alteração feita
                if self.tipo == self.TIPO_ENTRADA:
                    Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") - int(self.quantidade))
                else:
                    Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") + int(self.quantidade))
                raise ValueError("Movimentação resultaria em quantidade negativa.")

    def reverter_no_estoque(self):
        """
        Reverte o efeito desta movimentação usando F expressions dentro de transação.
        Levanta ValueError se a reversão deixaria quantidade negativa.
        """
        with transaction.atomic():
            if self.tipo == self.TIPO_ENTRADA:
                Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") - int(self.quantidade))
            else:
                Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") + int(self.quantidade))

            produto_atual = Produtos.objects.select_for_update().get(pk=self.produto_id)
            if produto_atual.quantidade < 0:
                # reverter a reversão
                if self.tipo == self.TIPO_ENTRADA:
                    Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") + int(self.quantidade))
                else:
                    Produtos.objects.filter(pk=self.produto_id).update(quantidade=F("quantidade") - int(self.quantidade))
                raise ValueError("Reversão resultaria em quantidade negativa.")