from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


def _agora_sp() -> str:
    # sem depender de pytz; no GitHub Actions você já usa TZ no shell
    return datetime.now().strftime("%d-%m-%Y")


def _read_backtest_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    df = pd.read_csv(path)

    # normaliza nomes
    if "Jogo" not in df.columns and "jogo" in df.columns:
        df = df.rename(columns={"jogo": "Jogo"})

    return df


def _df_to_pretty(df: pd.DataFrame) -> str:
    # deixa as colunas 11.0 12.0 13.0… como inteiros
    for c in df.columns:
        if isinstance(c, str) and c.endswith(".0"):
            try:
                df[c] = df[c].fillna(0).astype(int)
            except Exception:
                pass

    # formata
    return df.to_string(index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera relatório TXT 'mastigado' a partir dos backtests CSV.")
    parser.add_argument("--agressivo", required=True, help="CSV backtest agressivo")
    parser.add_argument("--conservador", required=True, help="CSV backtest conservador")
    parser.add_argument("--out", required=False, help="TXT de saída (se omitido, gera automático em outputs/)")
    parser.add_argument("--data", required=False, help="Data (DD-MM-YYYY) para imprimir no topo")
    args = parser.parse_args()

    ag_csv = Path(args.agressivo)
    cons_csv = Path(args.conservador)

    df_ag = _read_backtest_csv(ag_csv)
    df_cons = _read_backtest_csv(cons_csv)

    data = args.data or _agora_sp()

    out = Path(args.out) if args.out else Path("outputs") / f"relatorio_mastigado_{data}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    linhas = []
    linhas.append("=" * 46)
    linhas.append(" RELATORIO MASTIGADO DO BACKTEST (TXT) ")
    linhas.append(f" DATA: {data}")
    linhas.append("=" * 46)
    linhas.append("")
    linhas.append("------------ BACKTEST — MODO AGRESSIVO ------------")
    linhas.append("Resumo por jogo (ordenado pela melhor media de acertos):")
    linhas.append("")
    linhas.append(_df_to_pretty(df_ag))
    linhas.append("")
    linhas.append("------------ BACKTEST — MODO CONSERVADOR ------------")
    linhas.append("Resumo por jogo (ordenado pela melhor media de acertos):")
    linhas.append("")
    linhas.append(_df_to_pretty(df_cons))
    linhas.append("")
    linhas.append("Legenda:")
    linhas.append(" - media_acertos : media de acertos do jogo nos concursos analisados")
    linhas.append(" - max_acertos   : maior numero de acertos que o jogo ja fez")
    linhas.append(" - min_acertos   : menor numero de acertos que o jogo ja fez")
    linhas.append(" - colunas 11.0, 12.0, 13.0 ... : quantas vezes o jogo fez 11, 12, 13 pontos etc")
    linhas.append("")

    out.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✅ Relatorio mastigado gerado: {out}")


if __name__ == "__main__":
    main()