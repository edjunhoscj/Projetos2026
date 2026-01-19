#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional


def _read_text(p: Optional[str]) -> str:
    if not p:
        return ""
    path = Path(p)
    if not path.exists():
        return f"[AVISO] Arquivo não encontrado: {p}\n"
    txt = path.read_text(encoding="utf-8", errors="ignore")
    # Detecta ponteiro de Git LFS
    if txt.strip().startswith("version https://git-lfs.github.com/spec/v1"):
        return (
            "[AVISO] Este arquivo parece ser um ponteiro do Git LFS (não foi baixado no Actions).\n"
            "        Solução: habilitar checkout com LFS (git lfs) ou remover LFS desses CSV/PNG.\n\n"
            + txt
        )
    return txt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gera um relatório completo (TXT único) do Wizard Lotofácil")
    p.add_argument("--data", required=False, help="Data DD-MM-AAAA (opcional)")

    p.add_argument("--jogos-ag", required=True, help="TXT de jogos agressivo (com timestamp)")
    p.add_argument("--jogos-cons", required=True, help="TXT de jogos conservador (com timestamp)")

    p.add_argument("--bt-ag-txt", required=False, help="TXT formatado do backtest agressivo")
    p.add_argument("--bt-cons-txt", required=False, help="TXT formatado do backtest conservador")

    p.add_argument("--dash-resumo", required=False, help="CSV do dashboard resumo geral")
    p.add_argument("--dash-dist", required=False, help="CSV do dashboard distribuição de acertos")

    p.add_argument("--out", required=False, default="outputs/relatorio_completo.txt", help="Saída TXT")
    return p


def main() -> None:
    args = build_parser().parse_args()

    data = args.data or ""
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parts = []
    parts.append("==============================================\n"
                 "        RELATÓRIO COMPLETO DO WIZARD\n"
                 f"        DATA: {data}\n"
                 "==============================================\n\n")

    parts.append("------------ BACKTEST — MODO AGRESSIVO ------------\n")
    parts.append(_read_text(args.bt_ag_txt) + "\n\n")

    parts.append("------------ BACKTEST — MODO CONSERVADOR ------------\n")
    parts.append(_read_text(args.bt_cons_txt) + "\n\n")

    parts.append("------------ DISTRIBUIÇÃO DE ACERTOS ------------\n")
    parts.append(_read_text(args.dash_dist) + "\n\n")

    parts.append("------------ JOGOS GERADOS — AGRESSIVO ------------\n")
    parts.append(_read_text(args.jogos_ag) + "\n\n")

    parts.append("------------ JOGOS GERADOS — CONSERVADOR ------------\n")
    parts.append(_read_text(args.jogos_cons) + "\n\n")

    # Interpretação simples do melhor do dia (se tiver backtest txt legível)
    parts.append("============ RECOMENDAÇÃO FINAL ============\n")
    parts.append("✔ Use o melhor jogo do agressivo para explosão\n")
    parts.append("✔ Combine com o mais estável do conservador\n")
    parts.append("✔ Para apostar só 1 jogo: use o melhor agressivo\n")
    parts.append("✔ Para 3 jogos: melhor agressivo + mais estável conservador + melhor equilíbrio\n\n")

    out_path.write_text("".join(parts), encoding="utf-8")
    print(f"OK: gerou {out_path}")


if __name__ == "__main__":
    main()