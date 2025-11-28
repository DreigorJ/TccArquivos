#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from pathlib import Path
import json

# Force non-interactive backend for matplotlib (avoids issues on CI/headless)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class Command(BaseCommand):
    help = "Generate inventory reports (PNGs + JSON) and save to results directory."

    def add_arguments(self, parser):
        parser.add_argument("--out", type=str, default="resultados/reports", help="Output folder for reports")
        parser.add_argument("--top", type=int, default=10, help="Top N products for low-stock report")

    def handle(self, *args, **options):
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)

        # Import models lazily (app may be different in tests)
        from inventario_v3.models import Produto
        try:
            from inventario_v3.models import Categoria
        except Exception:
            Categoria = None

        # 1) Produtos por categoria (se Categoria existir)
        if Categoria:
            per_cat = (
                Produto.objects.values("categoria__nome")
                .annotate(products=Count("id"), stock=Sum("quantidade"))
                .order_by("-products")
            )
            labels = [p["categoria__nome"] or "Sem categoria" for p in per_cat]
            counts = [int(p["products"] or 0) for p in per_cat]

            try:
                (out / "by_category_products.json").write_text(
                    json.dumps(
                        {"by_category": [{"categoria": l, "products": c} for l, c in zip(labels, counts)]},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as e:
                self.stderr.write(f"Erro escrevendo JSON by_category_products: {e}")

            if labels:
                try:
                    plt.figure(figsize=(8, max(4, len(labels) * 0.5)))
                    plt.bar(labels, counts, color="tab:blue")
                    plt.xticks(rotation=45, ha="right")
                    plt.title("Produtos por Categoria")
                    plt.tight_layout()
                    path1 = out / "produtos_por_categoria.png"
                    plt.savefig(path1)
                    plt.close()
                    self.stdout.write(self.style.SUCCESS(f"Wrote {path1}"))
                except Exception as e:
                    self.stderr.write(f"Erro gerando PNG produtos_por_categoria: {e}")

            # estoque por categoria
            counts2 = [int(p["stock"] or 0) for p in per_cat]
            try:
                (out / "stock_por_categoria.json").write_text(
                    json.dumps(
                        {"by_category_stock": [{"categoria": l, "stock": s} for l, s in zip(labels, counts2)]},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as e:
                self.stderr.write(f"Erro escrevendo JSON stock_por_categoria: {e}")

            if labels:
                try:
                    plt.figure(figsize=(8, max(4, len(labels) * 0.5)))
                    plt.bar(labels, counts2, color="tab:green")
                    plt.xticks(rotation=45, ha="right")
                    plt.title("Estoque por Categoria (unidades)")
                    plt.tight_layout()
                    path2 = out / "estoque_por_categoria.png"
                    plt.savefig(path2)
                    plt.close()
                    self.stdout.write(self.style.SUCCESS(f"Wrote {path2}"))
                except Exception as e:
                    self.stderr.write(f"Erro gerando PNG estoque_por_categoria: {e}")

        # Low stock products (top N)
        low_qs = Produto.objects.order_by("quantidade").values("id", "nome", "quantidade")[: options["top"]]
        low_list = []
        for item in low_qs:
            # garantir tipos serializáveis
            low_list.append({"id": int(item["id"]), "nome": item["nome"], "quantidade": int(item["quantidade"] or 0)})

        try:
            (out / "low_stock.json").write_text(
                json.dumps({"low_stock": low_list}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            self.stderr.write(f"Erro escrevendo JSON low_stock: {e}")

        if low_list:
            try:
                names = [p["nome"] for p in low_list]
                quants = [p["quantidade"] for p in low_list]
                plt.figure(figsize=(8, max(4, len(names) * 0.4)))
                plt.barh(names, quants, color="tab:orange")
                plt.title(f"Produtos com menor estoque (top {options['top']})")
                plt.tight_layout()
                path3 = out / "low_stock_top.png"
                plt.savefig(path3)
                plt.close()
                self.stdout.write(self.style.SUCCESS(f"Wrote {path3}"))
            except Exception as e:
                self.stderr.write(f"Erro gerando PNG low_stock_top: {e}")

        self.stdout.write(self.style.SUCCESS("All reports generated."))