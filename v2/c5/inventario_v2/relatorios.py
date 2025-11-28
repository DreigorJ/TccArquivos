from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any

from django.conf import settings
from django.utils import timezone


def gerar_relatorio(pks_tabelas: Optional[list] = None, usuario: Optional[object] = None, out_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Função simples de geração de relatórios usada como fallback pelos testes.
    - Cria um diretório MEDIA_ROOT/relatorios (ou out_dir se informado)
    - Gera um arquivo JSON de exemplo (resumo) com timestamp
    - Retorna um dicionário contendo 'diretorio_saida' (string path)

    Observação: esta implementação é propositalmente simples — você pode estender
    para produzir CSV/PNG/PDF conforme necessidade do app.
    """
    if out_dir:
        base = Path(out_dir)
    else:
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            raise RuntimeError("MEDIA_ROOT not configured; pass out_dir or set settings.MEDIA_ROOT")
        base = Path(media_root) / "relatorios"

    base.mkdir(parents=True, exist_ok=True)

    # usar timezone.now() (aware) em vez de datetime.utcnow() para evitar DeprecationWarning
    now_dt = timezone.now()
    now_stamp = now_dt.strftime("%Y%m%dT%H%M%S")
    filename = f"relatorio_summary_{now_stamp}.json"
    filepath = base / filename

    summary = {
        "gerado_em": now_dt.isoformat(),
        "usuario": getattr(usuario, "username", None) if usuario is not None else None,
        "tabelas": pks_tabelas or [],
        "meta": {"descricao": "Relatório de exemplo gerado pela função gerar_relatorio"}
    }

    with filepath.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    return {"diretorio_saida": str(base), "arquivo": str(filepath)}