#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _carregar(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {csv_path}")
    df = pd.read_csv(csv_path)
    # garante ordenação
    if "media_acertos" in df.columns:
        df = df.sort_values(["media_acertos", "max_acertos", "min_acertos"], ascending=[False, False, False])
    return df


def _melhor_jogo(df: pd.DataFrame) -> pd.Series:
    return df.iloc[0]


def _mais_estavel(df: pd.DataFrame) -> pd.Series:
    """
    "Estável" aqui = maior min_acertos e depois melhor média.
    """
    if "min_acertos" not in df.columns:
        return df.iloc[0]
    df2 = df.sort_values(["min_acertos", "media_acertos", "max_acertos"], ascending=[False, False, False])
    return df2.iloc[0]


def gerar_relatorio(ag_csv: Path, cons_csv: Path, out_txt: Path, data: str | None = None) -> None:
    ag = _carregar(ag_csv)
    cons = _carregar(cons_csv)

    best_ag = _melhor_jogo(ag)
    best_cons = _melhor_jogo(cons)

    stable_ag = _mais_estavel(ag)
    stable_cons = _mais_estavel(cons)

    out_txt.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("=" * 60)
    lines.append("RELATÓRIO MASTIGADO DO BACKTEST")
    if data:
        lines.append(f"DATA: {data}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("== Melhor por média (AGRESSIVO) ==")
    lines.append(best_ag.to_string())
    lines.append("")

    lines.append("== Mais estável (AGRESSIVO) ==")
    lines.append(stable_ag.to_string())
    lines.append("")

    lines.append("== Melhor por média (CONSERVADOR) ==")
    lines.append(best_cons.to_string())
    lines.append("")

    lines.append("== Mais estável (CONSERVADOR) ==")
    lines.append(stable_cons.to_string())
    lines.append("")

    lines.append("=" * 60)
    lines.append("RECOMENDAÇÃO PRÁTICA")
    lines.append("=" * 60)
    lines.append("✔ Para apostar SÓ 1 jogo: pegue o melhor por média do AGRESSIVO.")
    lines.append("✔ Para apostar 2 jogos: melhor AGRESSIVO + mais estável CONSERVADOR.")
    lines.append("✔ Para apostar 3 jogos: melhor AGRESSIVO + mais estável CONSERVADOR + melhor do CONSERVADOR.")
    lines.append("")
    lines.append("Observação: backtest mede desempenho histórico; não garante resultado futuro.")
    lines.append("")

    out_txt.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gera relatório mastigado comparando dois backtests.")
    p.add_argument("--agressivo", required=True, help="CSV do backtest agressivo")
    p.add_argument("--conservador", required=True, help="CSV do backtest conservador")
    p.add_argument("--out", required=True, help="TXT de saída")
    p.add_argument("--data", required=False, help="Data DD-MM-AAAA (opcional)")
    return p


def main() -> None:
    args = build_parser().parse_args()
    gerar_relatorio(Path(args.agressivo), Path(args.conservador), Path(args.out), args.data)
    print(f"OK: gerou {args.out}")


if __name__ == "__main__":
    main()