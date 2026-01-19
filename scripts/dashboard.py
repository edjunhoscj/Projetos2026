# scripts/dashboard.py
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _read_backtest_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Backtest CSV não encontrado: {path}")

    df = pd.read_csv(path)

    # Sanidade: garantir colunas essenciais
    required = {"jogo", "media_acertos", "max_acertos", "min_acertos"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV {path} sem colunas esperadas: {sorted(missing)}")

    return df


def gerar_dashboard(ag_csv: Path, cons_csv: Path, out_resumo: Path, out_dist: Path) -> None:
    ag = _read_backtest_csv(ag_csv).copy()
    cons = _read_backtest_csv(cons_csv).copy()

    ag["modo"] = "agressivo"
    cons["modo"] = "conservador"

    all_df = pd.concat([ag, cons], ignore_index=True)

    # -------------------------
    # RESUMO GERAL (por modo)
    # -------------------------
    resumo = (
        all_df.groupby("modo", as_index=False)
        .agg(
            jogos_avaliados=("jogo", "count"),
            media_acertos=("media_acertos", "mean"),
            mediana_acertos=("media_acertos", "median"),
            max_acertos=("max_acertos", "max"),
            min_acertos=("min_acertos", "min"),
        )
    )

    out_resumo.parent.mkdir(parents=True, exist_ok=True)
    resumo.to_csv(out_resumo, index=False)

    # -------------------------
    # DISTRIBUIÇÃO de pico (max_acertos)
    # -------------------------
    dist = (
        all_df.groupby(["modo", "max_acertos"], as_index=False)
        .size()
        .rename(columns={"size": "qtd"})
        .sort_values(["modo", "max_acertos"])
    )

    dist.to_csv(out_dist, index=False)

    print("✅ Dashboard gerado:")
    print(f" - Resumo: {out_resumo}")
    print(f" - Distribuição: {out_dist}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera CSVs de dashboard a partir dos backtests.")
    parser.add_argument("--agressivo", default="outputs/backtest_agressivo.csv", help="CSV do backtest agressivo")
    parser.add_argument("--conservador", default="outputs/backtest_conservador.csv", help="CSV do backtest conservador")
    parser.add_argument("--out-resumo", default="outputs/dashboard_resumo_geral.csv", help="CSV resumo geral")
    parser.add_argument("--out-dist", default="outputs/dashboard_distribuicao_acertos.csv", help="CSV distribuição")

    args = parser.parse_args()

    gerar_dashboard(
        ag_csv=Path(args.agressivo),
        cons_csv=Path(args.conservador),
        out_resumo=Path(args.out_resumo),
        out_dist=Path(args.out_dist),
    )


if __name__ == "__main__":
    main()