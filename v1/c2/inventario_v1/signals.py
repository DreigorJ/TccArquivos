from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Produtos, Movimentacao

@receiver(post_delete, sender=Movimentacao)
def ajustar_estoque_apos_exclusao(sender, instance, **kwargs):
    """
    Sempre que uma Movimentacao for excluída (por view, admin, shell, tests),
    ajustamos o estoque no produto de forma atômica usando F-expressions.
    """
    produto_pk = instance.produto_id
    if produto_pk is None:
        return

    with transaction.atomic():
        if instance.tipo == Movimentacao.TIPO_ENTRADA:
            Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") - int(instance.quantidade))
        else:
            Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") + int(instance.quantidade))

        # validar e, se necessário, reverter e lançar
        produto_atual = Produtos.objects.select_for_update().get(pk=produto_pk)
        if produto_atual.quantidade < 0:
            # reverter a alteração
            if instance.tipo == Movimentacao.TIPO_ENTRADA:
                Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") + int(instance.quantidade))
            else:
                Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") - int(instance.quantidade))
            raise ValueError("Reversão após exclusão resultaria em quantidade negativa.")