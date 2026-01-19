from __future__ import annotations

import argparse
from pathlib import Path


def _read_optional(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return f"(arquivo não encontrado: {p})\n"
    return p.read_text(encoding="utf-8", errors="ignore").strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="", help="Data do relatório")
    ap.add_argument("--jogos-ag", required=True, help="TXT jogos agressivo (timestamp)")
    ap.add_argument("--jogos-cons", required=True, help="TXT jogos conservador (timestamp)")
    ap.add_argument("--bt-ag-txt", default=None, help="TXT backtest agressivo")
    ap.add_argument("--bt-cons-txt", default=None, help="TXT backtest conservador")
    ap.add_argument("--dash-resumo", default=None, help="CSV resumo do dashboard (opcional)")
    ap.add_argument("--dash-dist", default=None, help="CSV distribuição do dashboard (opcional)")
    ap.add_argument("--out", required=True, help="TXT final do relatório completo")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    header = []
    header.append("=" * 46)
    header.append("RELATÓRIO COMPLETO DO WIZARD")
    if args.data:
        header.append(f"DATA: {args.data}")
    header.append("=" * 46)
    header.append("")

    sections = []

    sections.append("------------ BACKTEST — MODO AGRESSIVO ------------\n" + _read_optional(args.bt_ag_txt))
    sections.append("------------ BACKTEST — MODO CONSERVADOR ------------\n" + _read_optional(args.bt_cons_txt))

    # dashboard csv (quando existir)
    dash_resumo = _read_optional(args.dash_resumo)
    dash_dist = _read_optional(args.dash_dist)

    if dash_resumo.strip():
        sections.append("------------ DASHBOARD — RESUMO GERAL (CSV) ------------\n" + dash_resumo)

    if dash_dist.strip():
        sections.append("------------ DISTRIBUIÇÃO DE ACERTOS (CSV) ------------\n" + dash_dist)

    sections.append("------------ JOGOS GERADOS — AGRESSIVO ------------\n" + _read_optional(args.jogos_ag))
    sections.append("------------ JOGOS GERADOS — CONSERVADOR ------------\n" + _read_optional(args.jogos_cons))

    # interpretação simples (texto) — você pode evoluir depois
    sections.append(
        "============ RECOMENDAÇÃO FINAL ============\n"
        "✔ Use o melhor jogo do agressivo para explosão\n"
        "✔ Combine com o mais estável do conservador\n"
        "✔ Para apostar só 1 jogo: use o melhor agressivo\n"
        "✔ Para 3 jogos: melhor agressivo + mais estável conservador + melhor equilíbrio\n"
    )

    txt = "\n".join(header) + "\n".join(sections).strip() + "\n"
    out.write_text(txt, encoding="utf-8")
    print(f"OK - Relatório completo gerado: {out}")


if __name__ == "__main__":
    main()