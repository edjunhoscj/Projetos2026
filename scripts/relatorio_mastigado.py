from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def ler_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for c in ["score_alvo", "score_13plus", "media_acertos", "max_acertos", "min_acertos"]:
        if c not in df.columns:
            df[c] = 0
    return df


def top_alvo(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    return df.sort_values(
        by=["score_alvo", "score_13plus", "max_acertos", "media_acertos"],
        ascending=[False, False, False, False],
    ).head(n)


def fmt(df: pd.DataFrame) -> str:
    cols = [
        "jogo",
        "media_acertos",
        "max_acertos",
        "min_acertos",
        "11.0",
        "12.0",
        "13.0",
        "14.0",
        "15.0",
        "score_alvo",
        "score_13plus",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].to_string(index=False)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agressivo", required=True)
    p.add_argument("--conservador", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--data", required=True)
    args = p.parse_args()

    ag = ler_csv(Path(args.agressivo))
    co = ler_csv(Path(args.conservador))

    out = []
    out.append("==============================================")
    out.append("RELATÓRIO MASTIGADO — FOCO EM 14/15")
    out.append(f"DATA: {args.data}")
    out.append("==============================================")
    out.append("")
    out.append("Ranking principal:")
    out.append("score_alvo = 100*(15) + 40*(14) + 10*(13) + 2*(12) + 0*(11)")
    out.append("Desempate: 13+ > max > média")
    out.append("")

    out.append("------------ TOP (AGRESSIVO) ------------")
    out.append(fmt(top_alvo(ag, 5)))
    out.append("")
    out.append("------------ TOP (CONSERVADOR) ------------")
    out.append(fmt(top_alvo(co, 5)))
    out.append("")

    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()