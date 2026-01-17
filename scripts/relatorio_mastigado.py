from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_csv(path)


def _tabela(df: pd.DataFrame, top: int = 20) -> str:
    # garante colunas principais no começo
    cols_fixas = ["Jogo", "media_acertos", "mediana_acertos", "max_acertos", "min_acertos"]
    cols_fixas = [c for c in cols_fixas if c in df.columns]
    cols_rest = [c for c in df.columns if c not in cols_fixas]
    df2 = df[cols_fixas + cols_rest].copy()

    return df2.head(top).to_string(index=False)


def main() -> None:
    p = argparse.ArgumentParser(description="Gera relatório mastigado (TXT) a partir dos CSVs do backtest.")
    p.add_argument("--agressivo", required=True, help="CSV do backtest agressivo")
    p.add_argument("--conservador", required=True, help="CSV do backtest conservador")
    p.add_argument("--out", required=True, help="Saída TXT (ex.: outputs/relatorio_mastigado.txt)")
    p.add_argument("--data", default="", help="Data opcional para cabeçalho (ex.: 15-01-2026)")

    args = p.parse_args()

    ag = Path(args.agressivo)
    co = Path(args.conservador)
    out = Path(args.out)

    df_ag = _read_csv(ag)
    df_co = _read_csv(co)

    out.parent.mkdir(parents=True, exist_ok=True)

    data = args.data.strip()
    cab_data = f"DATA: {data}\n" if data else ""

    texto = []
    texto.append("==============================================")
    texto.append("   RELATÓRIO MASTIGADO DO BACKTEST (TXT)")
    if cab_data:
        texto.append(cab_data.rstrip())
    texto.append("==============================================\n")

    texto.append("------------ BACKTEST — MODO AGRESSIVO ------------")
    texto.append("Resumo por jogo (ordenado pela melhor média):\n")
    texto.append(_tabela(df_ag))
    texto.append("\n")

    texto.append("------------ BACKTEST — MODO CONSERVADOR ------------")
    texto.append("Resumo por jogo (ordenado pela melhor média):\n")
    texto.append(_tabela(df_co))
    texto.append("\n")

    # Melhor do dia (por média)
    best_ag = df_ag.iloc[0]
    best_co = df_co.iloc[0]

    texto.append("============ INTERPRETAÇÃO RÁPIDA ============")
    texto.append(f"Melhor do agressivo: Jogo {int(best_ag['Jogo'])} | média {best_ag['media_acertos']:.2f} | max {int(best_ag['max_acertos'])} | min {int(best_ag['min_acertos'])}")
    texto.append(f"Melhor do conservador: Jogo {int(best_co['Jogo'])} | média {best_co['media_acertos']:.2f} | max {int(best_co['max_acertos'])} | min {int(best_co['min_acertos'])}")
    texto.append("\nRecomendação prática:")
    texto.append("✔ Se for jogar 1 só: pegue o melhor do agressivo (maior média / maior teto)")
    texto.append("✔ Se for jogar 2: melhor agressivo + melhor conservador")
    texto.append("✔ Se for jogar 3: melhor agressivo + melhor conservador + 2º melhor conservador (ou o mais estável)")
    texto.append("==============================================\n")

    out.write_text("\n".join(texto), encoding="utf-8")
    print(f"OK: gerado {out}")


if __name__ == "__main__":
    main()