#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def formatar_csv_para_txt(csv_path: Path, out_path: Path, titulo: str = "BACKTEST") -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")

    df = pd.read_csv(csv_path)

    # se vier com colunas 11.0/12.0/13.0 etc já ok
    # ordena por média desc
    if "media_acertos" in df.columns:
        df = df.sort_values(["media_acertos", "max_acertos", "min_acertos"], ascending=[False, False, False])

    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("=" * 46)
    lines.append(f"{titulo}")
    lines.append("=" * 46)
    lines.append("")
    lines.append(df.to_string(index=False))
    lines.append("")
    lines.append("Legenda:")
    lines.append(" - media_acertos : média de acertos nos concursos analisados")
    lines.append(" - max_acertos   : maior número de acertos que o jogo fez")
    lines.append(" - min_acertos   : menor número de acertos que o jogo fez")
    lines.append(" - colunas 11.0, 12.0, 13.0...: quantas vezes fez exatamente 11, 12, 13...")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Formatar backtest CSV para TXT (mastigado)")
    p.add_argument("--csv", required=True, help="Caminho do CSV do backtest")
    p.add_argument("--out", required=True, help="Caminho do TXT de saída")
    p.add_argument("--titulo", default="BACKTEST", help="Título do bloco")
    return p


def main() -> None:
    args = build_parser().parse_args()
    formatar_csv_para_txt(Path(args.csv), Path(args.out), args.titulo)
    print(f"OK: gerou {args.out}")


if __name__ == "__main__":
    main()