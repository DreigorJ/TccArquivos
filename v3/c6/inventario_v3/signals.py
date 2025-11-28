# inventario_v3/signals.py
import logging
from pathlib import Path
from django.conf import settings
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import m2m_changed, pre_delete
from django.core.management import call_command

from .models import TabelaProdutos, AcessoTabela, Produto, Movimento

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def gerar_relatorio_no_login(sender, user, request, **kwargs):
    """
    Ao logar, gera um relatório (HTML+PNGs+JSON) para o usuário contendo apenas as tabelas
    que ele tem acesso (ou todas se staff/superuser).

    Nota: o comando 'gerar_relatorio' aceita somente --out (e --top). Não passamos
    opções não suportadas (tabelas/usuario) para evitar TypeError.
    """
    try:
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            pks = list(TabelaProdutos.objects.values_list("pk", flat=True))
        else:
            public_pks = list(TabelaProdutos.objects.filter(publico=True).values_list("pk", flat=True))
            acesso_pks = list(AcessoTabela.objects.filter(usuario=user).values_list("tabela__pk", flat=True))
            pks = list({*public_pks, *acesso_pks})

        if not pks:
            logger.debug("Usuario %s não tem tabelas para gerar relatório.", getattr(user, "pk", "<unknown>"))
            return

        out_dir = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "resultados" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Chama o comando apenas com opções suportadas
        call_command("gerar_relatorio", out=str(out_dir))
        logger.info("Relatório gerado no login do user %s (tabelas: %s)", getattr(user, "pk", ""), ",".join(map(str, pks)))
    except Exception as e:
        logger.exception("Falha ao gerar relatório no login do usuário %s: %s", getattr(user, "pk", ""), e)


# --- handlers to remove orphan products and their movimentos ---


@receiver(m2m_changed, sender=Produto.tabelas.through)
def produto_tabelas_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    When a product's tabelas M2M is changed, if it no longer belongs to any tabela,
    delete the product (and its movimentos, via cascade).
    """
    # only act after relations are removed
    if action not in ("post_remove", "post_clear"):
        return

    try:
        # refresh from DB to get current relations
        inst = Produto.objects.filter(pk=instance.pk).first()
        if not inst:
            return
        if inst.tabelas.count() == 0:
            logger.info("Produto %s tornou-se órfão após m2m change — removendo", inst)
            inst.delete()
    except Exception:
        logger.exception("Erro ao processar m2m_changed para Produto %s", getattr(instance, "pk", "<unknown>"))


@receiver(pre_delete, sender=TabelaProdutos)
def tabela_pre_delete(sender, instance, **kwargs):
    """
    Before a TabelaProdutos is deleted, remove products that will become orphan
    (i.e., products that are only in this tabela).
    """
    try:
        # iterate products related to the tabela about to be deleted
        for p in instance.produtos.all():
            # check if product belongs to other tabelas (excluding the one being removed)
            other = p.tabelas.exclude(pk=instance.pk)
            if not other.exists():
                logger.info("Produto %s ficará órfão após exclusão da tabela %s — removendo", p, instance)
                p.delete()
    except Exception:
        logger.exception("Erro ao processar pre_delete para TabelaProdutos %s", getattr(instance, "pk", "<unknown>"))