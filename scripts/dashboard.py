from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def ler_backtest(path: Path, modo: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["modo"] = modo
    for c in ["score_alvo", "score_13plus", "media_acertos", "max_acertos", "min_acertos"]:
        if c not in df.columns:
            df[c] = 0
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agressivo", required=True)
    p.add_argument("--conservador", required=True)
    p.add_argument("--out-resumo", required=True)
    p.add_argument("--out-dist", required=True)
    args = p.parse_args()

    ag = ler_backtest(Path(args.agressivo), "agressivo")
    co = ler_backtest(Path(args.conservador), "conservador")

    all_df = pd.concat([ag, co], ignore_index=True)

    # Resumo por modo
    resumo = (
        all_df.groupby("modo")
        .agg(
            jogos_avaliados=("jogo", "count"),
            media_acertos=("media_acertos", "mean"),
            mediana_acertos=("media_acertos", "median"),
            max_acertos=("max_acertos", "max"),
            min_acertos=("min_acertos", "min"),
            score_alvo_total=("score_alvo", "sum"),
            score_alvo_melhor=("score_alvo", "max"),
            score_13plus_total=("score_13plus", "sum"),
        )
        .reset_index()
    )

    # Distribuição do max_acertos
    dist = (
        all_df.groupby(["modo", "max_acertos"])
        .size()
        .reset_index(name="qtd")
        .sort_values(["modo", "max_acertos"])
        .reset_index(drop=True)
    )

    Path(args.out_resumo).parent.mkdir(parents=True, exist_ok=True)
    resumo.to_csv(args.out_resumo, index=False, encoding="utf-8-sig")

    Path(args.out_dist).parent.mkdir(parents=True, exist_ok=True)
    dist.to_csv(args.out_dist, index=False, encoding="utf-8-sig")

    print(f"OK: {args.out_resumo}")
    print(f"OK: {args.out_dist}")


if __name__ == "__main__":
    main()