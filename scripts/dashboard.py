from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera CSVs de dashboard (resumo + distribuição).")
    ap.add_argument("--agressivo", required=True, help="CSV backtest agressivo")
    ap.add_argument("--conservador", required=True, help="CSV backtest conservador")
    ap.add_argument("--out-resumo", required=True, help="CSV resumo geral")
    ap.add_argument("--out-dist", required=True, help="CSV distribuição de acertos")
    args = ap.parse_args()

    a = pd.read_csv(args.agressivo)
    c = pd.read_csv(args.conservador)

    def resumo(df: pd.DataFrame, modo: str) -> dict:
        return {
            "modo": modo,
            "jogos_avaliados": int(len(df)),
            "media_acertos": float(df["media_acertos"].mean()),
            "mediana_acertos": float(df["media_acertos"].median()),
            "max_acertos": int(df["max_acertos"].max()),
            "min_acertos": int(df["max_acertos"].min()),
        }

    df_resumo = pd.DataFrame([resumo(a, "agressivo"), resumo(c, "conservador")])
    out_resumo = Path(args.out_resumo)
    out_resumo.parent.mkdir(parents=True, exist_ok=True)
    df_resumo.to_csv(out_resumo, index=False)

    # distribuição do max_acertos (quantos jogos atingiram 11, 12, 13 etc)
    dist_a = a["max_acertos"].value_counts().sort_index().reset_index()
    dist_a.columns = ["max_acertos", "qtd"]
    dist_a.insert(0, "modo", "agressivo")

    dist_c = c["max_acertos"].value_counts().sort_index().reset_index()
    dist_c.columns = ["max_acertos", "qtd"]
    dist_c.insert(0, "modo", "conservador")

    df_dist = pd.concat([dist_a, dist_c], ignore_index=True)
    out_dist = Path(args.out_dist)
    out_dist.parent.mkdir(parents=True, exist_ok=True)
    df_dist.to_csv(out_dist, index=False)

    print(f"✅ dashboard resumo: {out_resumo}")
    print(f"✅ dashboard dist:   {out_dist}")


if __name__ == "__main__":
    main()