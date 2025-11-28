from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, post_delete, m2m_changed, pre_delete
from django.dispatch import receiver
from django.core.management import call_command
from django.db.models import Count
from django.apps import apps
from django.db import transaction
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

_TABELA_TO_PRODUTOS_BEFORE_DELETE = {}


@receiver(post_save, sender=User)
def ensure_perfil_usuario(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        PerfilUsuario = apps.get_model("inventario_v1", "PerfilUsuario")
    except LookupError:
        logger.debug("PerfilUsuario model not available; skipping ensure_perfil_usuario")
        return
    try:
        PerfilUsuario.objects.get_or_create(usuario=instance)
        logger.debug("PerfilUsuario criado para user %s", instance.username)
    except Exception:
        logger.exception("Falha ao criar PerfilUsuario para user %s", instance.username)


def _delete_orphan_produtos(produtos_qs):
    try:
        Movimentacao = apps.get_model("inventario_v1", "Movimentacao")
    except LookupError:
        Movimentacao = None
    for p in produtos_qs:
        try:
            if Movimentacao is not None:
                Movimentacao.objects.filter(produto=p).delete()
            p.delete()
            logger.debug("Produto órfão removido: %s", p)
        except Exception:
            logger.exception("Erro ao remover produto órfão %s", p)


def _connect_optional_handlers():
    try:
        Produtos = apps.get_model("inventario_v1", "Produtos")
    except LookupError:
        Produtos = None
    if Produtos is not None and hasattr(Produtos, "tabelas"):
        try:
            through = Produtos.tabelas.through
            m2m_changed.connect(produtos_tabelas_changed, sender=through)
        except Exception:
            logger.exception("Não foi possível conectar handler m2m_changed para Produtos.tabelas")


def produtos_tabelas_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in ("post_remove", "post_clear"):
        return
    try:
        ProdutosLocal = apps.get_model("inventario_v1", "Produtos")
        if reverse:
            produtos_pks = pk_set or set()
            orphan_qs = ProdutosLocal.objects.filter(pk__in=produtos_pks).annotate(n_tabelas=Count("tabelas")).filter(n_tabelas=0)
        else:
            orphan_qs = ProdutosLocal.objects.filter(pk=instance.pk).annotate(n_tabelas=Count("tabelas")).filter(n_tabelas=0)
        if orphan_qs.exists():
            _delete_orphan_produtos(orphan_qs)
    except Exception:
        logger.exception("Erro no handler m2m_changed para Produtos.tabelas")


@receiver(pre_delete)
def tabela_pre_delete_capture(sender, instance, **kwargs):
    try:
        TabelaProdutos = apps.get_model("inventario_v1", "TabelaProdutos")
    except LookupError:
        return
    if sender != TabelaProdutos:
        return
    try:
        produtos_qs = instance.produtos.all()
        pks = list(produtos_qs.values_list("pk", flat=True))
        _TABELA_TO_PRODUTOS_BEFORE_DELETE[instance.pk] = pks
    except Exception:
        logger.exception("Erro ao capturar produtos antes de deletar a tabela %s", getattr(instance, "pk", None))


@receiver(post_delete)
def tabela_post_delete_cleanup(sender, instance, **kwargs):
    try:
        TabelaProdutos = apps.get_model("inventario_v1", "TabelaProdutos")
    except LookupError:
        TabelaProdutos = None
    if sender != TabelaProdutos:
        return

    def _after_commit():
        try:
            ProdutosLocal = apps.get_model("inventario_v1", "Produtos")
            pks = _TABELA_TO_PRODUTOS_BEFORE_DELETE.pop(instance.pk, None) or []
            if pks:
                candidate_qs = ProdutosLocal.objects.filter(pk__in=pks).annotate(n_tabelas=Count("tabelas")).filter(n_tabelas=0)
                if candidate_qs.exists():
                    _delete_orphan_produtos(candidate_qs)
            else:
                orphan_qs = ProdutosLocal.objects.annotate(n_tabelas=Count("tabelas")).filter(n_tabelas=0)
                if orphan_qs.exists():
                    _delete_orphan_produtos(orphan_qs)
        except Exception:
            logger.exception("Erro no cleanup após exclusão de tabela %s", instance)

    try:
        # agenda para execução após commit (quando aplicável)
        transaction.on_commit(_after_commit)
    except Exception:
        # se on_commit não estiver disponível/executado, execute imediatamente
        _after_commit()

    # garantir execução imediata também — útil em ambientes de teste
    try:
        _after_commit()
    except Exception:
        logger.exception("Erro ao executar cleanup imediato após exclusão de tabela %s", instance)


def _connect_movimentacao_post_delete():
    try:
        Movimentacao = apps.get_model("inventario_v1", "Movimentacao")
        Produtos = apps.get_model("inventario_v1", "Produtos")
    except LookupError:
        return

    @receiver(post_delete, sender=Movimentacao)
    def ajustar_estoque_apos_exclusao(sender, instance, **kwargs):
        from django.db import transaction
        from django.db.models import F

        produto_pk = instance.produto_id
        if produto_pk is None:
            return

        with transaction.atomic():
            if instance.tipo == Movimentacao.TIPO_ENTRADA:
                Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") - int(instance.quantidade))
            else:
                Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") + int(instance.quantidade))

            produto_atual = Produtos.objects.select_for_update().get(pk=produto_pk)
            if produto_atual.quantidade < 0:
                if instance.tipo == Movimentacao.TIPO_ENTRADA:
                    Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") + int(instance.quantidade))
                else:
                    Produtos.objects.filter(pk=produto_pk).update(quantidade=F("quantidade") - int(instance.quantidade))
                raise ValueError("Reversão após exclusão resultaria em quantidade negativa.")


def gerar_relatorio(*args, **kwargs):
    try:
        try:
            from .relatorios import gerar_relatorio as _gr
            return _gr(*args, **kwargs)
        except Exception:
            call_command("gerar_relatorio", *args, **kwargs)
    except Exception:
        logger.exception("Erro ao gerar relatorio via signals.gerar_relatorio")


@receiver(user_logged_in)
def on_user_logged_in(sender, user, request, **kwargs):
    try:
        gerar_relatorio(usuario=str(getattr(user, "pk", "")))
        logger.debug("Geração de relatório acionada em login para user %s", user)
    except Exception:
        logger.exception("Erro ao processar on_user_logged_in")


_connect_optional_handlers()
_connect_movimentacao_post_delete()