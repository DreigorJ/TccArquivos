from pathlib import Path
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .models import Produtos as Produto  # usar modelo local Produtos

PREFIX_RELATORIOS = "relatorios"


def _assegura_media_root():
    if not getattr(settings, "MEDIA_ROOT", None):
        raise ImproperlyConfigured("settings.MEDIA_ROOT precisa estar configurado para guardar relatórios.")
    if not getattr(settings, "MEDIA_URL", None):
        raise ImproperlyConfigured("settings.MEDIA_URL precisa estar configurado para servir relatórios.")
    return Path(settings.MEDIA_ROOT)


def gerar_relatorio(pks_tabelas=None, usuario: str | None = None) -> dict:
    """
    Gera gráficos e um relatório HTML/JSON para as tabelas indicadas (lista de PKs).
    Se pks_tabelas for None ou vazio, usa todos os produtos.

    Retorna um dicionário com metadados e caminhos relativos.
    """
    raiz_media = _assegura_media_root()
    pasta_base = raiz_media / PREFIX_RELATORIOS
    pasta_base.mkdir(parents=True, exist_ok=True)

    agora = timezone.localtime(timezone.now())
    carimbo = agora.strftime("%Y%m%dT%H%M%S")
    data_hora_legivel = agora.strftime("%Y-%m-%d %H:%M:%S")

    # selecionar produtos, filtrando por tabelas se fornecido
    if pks_tabelas:
        try:
            # se o modelo Produto tiver relacionamento 'tabelas', aplicamos filtro; senão usamos todos
            if hasattr(Produto, "tabelas"):
                produtos_qs = Produto.objects.filter(tabelas__pk__in=pks_tabelas).distinct()
            else:
                produtos_qs = Produto.objects.all()
        except Exception:
            produtos_qs = Produto.objects.all()
    else:
        produtos_qs = Produto.objects.all()

    produtos = list(produtos_qs.select_related("categoria"))

    # 1) Produtos por categoria (contagem por categoria)
    categoria_para_produtos = {}
    for p in produtos:
        cat = p.categoria.nome if getattr(p, "categoria", None) else "Sem categoria"
        categoria_para_produtos.setdefault(cat, set()).add(p.pk)

    categorias = list(categoria_para_produtos.keys())
    contagens = [len(categoria_para_produtos[c]) for c in categorias]
    if not categorias:
        categorias = ["(nenhum)"]
        contagens = [0]

    # criar subpasta por carimbo
    pasta_saida = pasta_base / carimbo
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # Gráfico 1
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.bar(range(len(categorias)), contagens, color="#2e86c1")
    ax1.set_xticks(range(len(categorias)))
    ax1.set_xticklabels(categorias, rotation=35, ha="right")
    ax1.set_title("Produtos por Categoria")
    ax1.set_ylabel("Quantidade")
    ax1.set_ylim(0, (max(contagens) * 1.15) if any(contagens) else 1)
    plt.tight_layout()
    nome_chart1 = f"chart_produtos_por_categoria_{carimbo}.png"
    caminho_chart1 = pasta_saida / nome_chart1
    fig1.savefig(caminho_chart1, dpi=100)
    plt.close(fig1)

    # 2) Produtos com menor estoque (top 10)
    produtos_ordenados = sorted(produtos, key=lambda x: (x.quantidade if x.quantidade is not None else 0))
    mais_baixos = produtos_ordenados[:10]
    nomes_baixos = [f"{(p.categoria.nome if getattr(p,'categoria',None) else 'Sem categoria')} - {p.nome}" for p in mais_baixos]
    valores_baixos = [p.quantidade for p in mais_baixos]
    if not nomes_baixos:
        nomes_baixos = ["(nenhum)"]
        valores_baixos = [0]

    fig2, ax2 = plt.subplots(figsize=(9, 5))
    y_pos = list(range(len(nomes_baixos)-1, -1, -1))
    ax2.barh(y_pos, valores_baixos, color="#ff8c00")
    ax2.set_yticks(range(len(nomes_baixos)))
    ax2.set_yticklabels(list(reversed(nomes_baixos)))
    ax2.set_xlabel("Quantidade")
    ax2.set_title("Produtos com menor estoque (top 10)")
    plt.tight_layout()
    nome_chart2 = f"chart_estoque_baixo_{carimbo}.png"
    caminho_chart2 = pasta_saida / nome_chart2
    fig2.savefig(caminho_chart2, dpi=100)
    plt.close(fig2)

    # 3) Estoque por Categoria (soma das quantidades)
    estoque_por_categoria = {}
    for p in produtos:
        cat = p.categoria.nome if getattr(p, "categoria", None) else "Sem categoria"
        estoque_por_categoria[cat] = estoque_por_categoria.get(cat, 0) + (p.quantidade or 0)

    categorias3 = list(estoque_por_categoria.keys())
    valores3 = [estoque_por_categoria[c] for c in categorias3]
    if not categorias3:
        categorias3 = ["(nenhum)"]
        valores3 = [0]

    fig3, ax3 = plt.subplots(figsize=(8, 4))
    ax3.bar(range(len(categorias3)), valores3, color="#2ca02c")
    ax3.set_xticks(range(len(categorias3)))
    ax3.set_xticklabels(categorias3, rotation=35, ha="right")
    ax3.set_title("Estoque por Categoria (unidades)")
    ax3.set_ylabel("Unidades")
    ax3.set_ylim(0, max(valores3) * 1.15 if any(valores3) else 1)
    plt.tight_layout()
    nome_chart3 = f"chart_estoque_por_categoria_{carimbo}.png"
    caminho_chart3 = pasta_saida / nome_chart3
    fig3.savefig(caminho_chart3, dpi=100)
    plt.close(fig3)

    # Montar HTML
    nome_base = f"relatorio_usuario{usuario}_{carimbo}" if usuario else f"relatorio_{carimbo}"
    nome_html = f"{nome_base}.html"
    nome_json = f"{nome_base}.json"

    media_url = settings.MEDIA_URL.rstrip("/")
    prefix_url = f"{media_url}/{PREFIX_RELATORIOS}/{carimbo}"

    partes_html = []
    partes_html.append("<!doctype html><html lang='pt-br'><head><meta charset='utf-8'>")
    partes_html.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    partes_html.append(f"<title>Relatório gerado {data_hora_legivel}</title>")
    partes_html.append("<style>"
                       "body{font-family:Arial,Helvetica,sans-serif;color:#222;background:#fff;padding:18px}"
                       ".report-header{margin-bottom:16px}"
                       ".report-header h1{margin:0 0 6px 0;font-size:18px}"
                       ".chart{max-width:1000px;margin-bottom:28px;border:1px solid #eee;padding:8px;background:#fafafa}"
                       ".muted{color:#666;font-size:13px}"
                       "</style></head><body>")
    partes_html.append(f"<div class='report-header'><h1>Relatório gerado: {data_hora_legivel}</h1>")
    partes_html.append(f"<div class='muted'>Gerado para: tabelas selecionadas ({len(pks_tabelas) if pks_tabelas else 'todas'})</div></div>")

    partes_html.append("<div class='chart'><h2>Produtos por Categoria</h2>")
    partes_html.append(f"<img src='{prefix_url}/{nome_chart1}' alt='Produtos por Categoria' style='width:100%;height:auto;'></div>")

    partes_html.append("<div class='chart'><h2>Produtos com menor estoque (top 10)</h2>")
    partes_html.append(f"<img src='{prefix_url}/{nome_chart2}' alt='Produtos com menor estoque' style='width:100%;height:auto;'></div>")

    partes_html.append("<div class='chart'><h2>Estoque por Categoria (unidades)</h2>")
    partes_html.append(f"<img src='{prefix_url}/{nome_chart3}' alt='Estoque por Categoria' style='width:100%;height:auto;'></div>")

    partes_html.append("</body></html>")

    caminho_html = pasta_saida / nome_html
    caminho_html.write_text("\n".join(partes_html), encoding="utf-8")

    metadados = {
        "gerado_em": data_hora_legivel,
        "usuario": usuario or None,
        "tabelas": pks_tabelas or [],
        "arquivos": [nome_chart1, nome_chart2, nome_chart3, nome_html],
    }
    caminho_json = pasta_saida / nome_json
    with caminho_json.open("w", encoding="utf-8") as fh:
        json.dump(metadados, fh, ensure_ascii=False, indent=2)

    # Lista de arquivos relativa à raiz do MEDIA
    arquivos_gerados = [
        f"{PREFIX_RELATORIOS}/{carimbo}/{nome_chart1}",
        f"{PREFIX_RELATORIOS}/{carimbo}/{nome_chart2}",
        f"{PREFIX_RELATORIOS}/{carimbo}/{nome_chart3}",
        f"{PREFIX_RELATORIOS}/{carimbo}/{nome_html}",
        f"{PREFIX_RELATORIOS}/{carimbo}/{nome_json}",
    ]

    return {
        "diretorio_saida": pasta_saida,
        "arquivos": arquivos_gerados,
        "url_html_relativa": f"{PREFIX_RELATORIOS}/{carimbo}/{nome_html}",
        "url_json_relativa": f"{PREFIX_RELATORIOS}/{carimbo}/{nome_json}",
        "carimbo": carimbo,
    }