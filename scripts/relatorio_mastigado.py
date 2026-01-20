from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _best(df: pd.DataFrame):
    df2 = df.sort_values(["media_acertos", "max_acertos"], ascending=[False, False]).reset_index(drop=True)
    return df2.iloc[0]


def _fmt(df: pd.DataFrame) -> str:
    return df.to_string(index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera relatório mastigado (TXT) a partir dos CSVs de backtest.")
    ap.add_argument("--agressivo", required=True, help="CSV agressivo")
    ap.add_argument("--conservador", required=True, help="CSV conservador")
    ap.add_argument("--out", required=True, help="TXT saída")
    ap.add_argument("--data", default="", help="Data (DD-MM-YYYY)")
    args = ap.parse_args()

    ag = pd.read_csv(args.agressivo)
    co = pd.read_csv(args.conservador)

    best_ag = _best(ag)
    best_co = _best(co)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("==============================================")
    lines.append("        RELATÓRIO MASTIGADO DO WIZARD")
    if args.data:
        lines.append(f"        DATA: {args.data}")
    lines.append("==============================================\n")

    lines.append("---- BACKTEST (AGRESSIVO) ----")
    lines.append(_fmt(ag.sort_values("media_acertos", ascending=False)))
    lines.append("\n---- BACKTEST (CONSERVADOR) ----")
    lines.append(_fmt(co.sort_values("media_acertos", ascending=False)))

    lines.append("\n==============================================")
    lines.append("MELHORES DO DIA (por média e máximo)")
    lines.append("==============================================")
    lines.append(
        f"Agressivo → jogo {int(best_ag['jogo'])} | média={float(best_ag['media_acertos']):.2f} | "
        f"max={int(best_ag['max_acertos'])} | min={int(best_ag['min_acertos'])}"
    )
    lines.append(
        f"Conservador → jogo {int(best_co['jogo'])} | média={float(best_co['media_acertos']):.2f} | "
        f"max={int(best_co['max_acertos'])} | min={int(best_co['min_acertos'])}"
    )

    lines.append("\nRECOMENDAÇÃO (simples e prática):")
    lines.append("✔ Se for apostar 1 jogo: use o melhor do AGRESSIVO (maior explosão).")
    lines.append("✔ Se for apostar 2–3 jogos: melhor AGRESSIVO + melhor CONSERVADOR + (opcional) o 2º melhor do conservador.")
    lines.append("✔ Se quiser estabilidade: priorize o CONSERVADOR com maior min_acertos.")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Relatório mastigado salvo: {out}")


if __name__ == "__main__":
    main()