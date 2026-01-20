# scripts/dashboard.py
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _load(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Arquivo não encontrado: {p}")
    df = pd.read_csv(p)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _summary(modo: str, df: pd.DataFrame) -> dict:
    # espera colunas do backtest: jogo, media_acertos, max_acertos, min_acertos, ...
    if "media_acertos" not in df.columns:
        raise SystemExit(f"CSV de backtest sem coluna 'media_acertos'. Colunas: {list(df.columns)}")

    return {
        "modo": modo,
        "jogos_avaliados": int(df["jogo"].nunique()) if "jogo" in df.columns else int(len(df)),
        "media_acertos": float(df["media_acertos"].mean()),
        "mediana_acertos": float(df["media_acertos"].median()),
        "max_acertos": int(df["max_acertos"].max()) if "max_acertos" in df.columns else None,
        "min_acertos": int(df["min_acertos"].min()) if "min_acertos" in df.columns else None,
    }


def _dist_max(modo: str, df: pd.DataFrame) -> pd.DataFrame:
    # Distribuição do "max_acertos" por jogo (útil pra ver potencial do conjunto)
    if "max_acertos" not in df.columns:
        return pd.DataFrame(columns=["modo", "max_acertos", "qtd"])
    c = df["max_acertos"].value_counts().sort_index()
    out = pd.DataFrame({"max_acertos": c.index.astype(int), "qtd": c.values.astype(int)})
    out.insert(0, "modo", modo)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agressivo", required=True)
    ap.add_argument("--conservador", required=True)
    ap.add_argument("--out-resumo", required=True)
    ap.add_argument("--out-dist", required=True)
    args = ap.parse_args()

    df_a = _load(args.agressivo)
    df_c = _load(args.conservador)

    resumo = pd.DataFrame([_summary("agressivo", df_a), _summary("conservador", df_c)])
    dist = pd.concat([_dist_max("agressivo", df_a), _dist_max("conservador", df_c)], ignore_index=True)

    Path(args.out_resumo).parent.mkdir(parents=True, exist_ok=True)
    resumo.to_csv(args.out_resumo, index=False)
    dist.to_csv(args.out_dist, index=False)

    print(f"✅ Dashboard resumo: {args.out_resumo}")
    print(f"✅ Dashboard dist:   {args.out_dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())