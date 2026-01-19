from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _read_backtest_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    df = pd.read_csv(path)
    # normaliza nomes
    df.columns = [c.strip() for c in df.columns]
    return df


def _pick_best(df: pd.DataFrame) -> pd.Series:
    df2 = df.sort_values(["media_acertos", "max_acertos", "min_acertos"], ascending=[False, False, False])
    return df2.iloc[0]


def _pick_stable(df: pd.DataFrame) -> pd.Series:
    # estabilidade = maior mínimo, depois maior média
    df2 = df.sort_values(["min_acertos", "media_acertos", "max_acertos"], ascending=[False, False, False])
    return df2.iloc[0]


def build_report(df_ag: pd.DataFrame, df_cons: pd.DataFrame, data: str) -> str:
    best_ag = _pick_best(df_ag)
    best_cons = _pick_best(df_cons)
    stable_cons = _pick_stable(df_cons)

    lines = []
    lines.append("=" * 46)
    lines.append("RELATÓRIO MASTIGADO DO BACKTEST")
    lines.append(f"DATA: {data}")
    lines.append("=" * 46)
    lines.append("")

    lines.append("TOP 5 — AGRESSIVO (por média)")
    lines.append(df_ag.sort_values("media_acertos", ascending=False).head(5).to_string(index=False))
    lines.append("")

    lines.append("TOP 5 — CONSERVADOR (por média)")
    lines.append(df_cons.sort_values("media_acertos", ascending=False).head(5).to_string(index=False))
    lines.append("")

    lines.append("INTERPRETAÇÃO (mastigada)")
    lines.append(f"- Melhor do AGRESSIVO: jogo {int(best_ag['jogo'])} | média {best_ag['media_acertos']:.4f} | max {int(best_ag['max_acertos'])} | min {int(best_ag['min_acertos'])}")
    lines.append(f"- Melhor do CONSERVADOR: jogo {int(best_cons['jogo'])} | média {best_cons['media_acertos']:.4f} | max {int(best_cons['max_acertos'])} | min {int(best_cons['min_acertos'])}")
    lines.append(f"- Mais estável no CONSERVADOR: jogo {int(stable_cons['jogo'])} | min {int(stable_cons['min_acertos'])} | média {stable_cons['media_acertos']:.4f}")
    lines.append("")

    lines.append("RECOMENDAÇÃO PRÁTICA")
    lines.append("✔ Se for apostar 1 jogo (explosão): use o melhor do AGRESSIVO")
    lines.append("✔ Se for apostar 2 jogos: melhor AGRESSIVO + mais estável CONSERVADOR")
    lines.append("✔ Se for apostar 3 jogos: melhor AGRESSIVO + melhor CONSERVADOR + mais estável CONSERVADOR")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agressivo", required=True, help="CSV do backtest agressivo")
    ap.add_argument("--conservador", required=True, help="CSV do backtest conservador")
    ap.add_argument("--out", required=True, help="Arquivo TXT de saída")
    ap.add_argument("--data", default="", help="Data para o relatório (ex: 15-01-2026)")
    args = ap.parse_args()

    df_ag = _read_backtest_csv(Path(args.agressivo))
    df_cons = _read_backtest_csv(Path(args.conservador))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    txt = build_report(df_ag, df_cons, args.data or "-")
    out_path.write_text(txt, encoding="utf-8")

    print(f"OK - Relatório mastigado gerado: {out_path}")


if __name__ == "__main__":
    main()