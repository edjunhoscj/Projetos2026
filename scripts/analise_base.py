from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class Resumo:
    freq: Dict[int, int]


def _extrair(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    return df[cols].to_numpy(dtype=int, copy=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Analisa padrões na base Lotofácil.")
    ap.add_argument("--base", required=True, help="Arquivo base_limpa.xlsx")
    ap.add_argument("--ultimos", type=int, default=200, help="Janela recência (default: 200)")
    args = ap.parse_args()

    base_path = Path(args.base)
    if not base_path.exists():
        raise FileNotFoundError(base_path)

    df = pd.read_excel(base_path)
    cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    df = df[cols].copy().sort_values("Concurso").reset_index(drop=True)

    ult = int(args.ultimos)
    df_last = df.tail(ult).copy()

    arr_all = _extrair(df).flatten()
    arr_last = _extrair(df_last).flatten()

    freq_all = {d: 0 for d in range(1, 26)}
    freq_last = {d: 0 for d in range(1, 26)}
    for x in arr_all:
        freq_all[int(x)] += 1
    for x in arr_last:
        freq_last[int(x)] += 1

    top_all = sorted(freq_all.items(), key=lambda x: x[1], reverse=True)[:10]
    top_last = sorted(freq_last.items(), key=lambda x: x[1], reverse=True)[:10]
    bot_last = sorted(freq_last.items(), key=lambda x: x[1])[:10]

    # paridade/soma/20-25
    def estat_janela(dfx: pd.DataFrame) -> Dict[str, float]:
        A = _extrair(dfx)
        pares = np.sum(A % 2 == 0, axis=1)
        soma = np.sum(A, axis=1)
        qtd_20_25 = np.sum((A >= 20) & (A <= 25), axis=1)
        return {
            "pares_med": float(np.mean(pares)),
            "pares_min": float(np.min(pares)),
            "pares_max": float(np.max(pares)),
            "soma_med": float(np.mean(soma)),
            "soma_min": float(np.min(soma)),
            "soma_max": float(np.max(soma)),
            "q20_25_med": float(np.mean(qtd_20_25)),
            "q20_25_min": float(np.min(qtd_20_25)),
            "q20_25_max": float(np.max(qtd_20_25)),
        }

    e_all = estat_janela(df)
    e_last = estat_janela(df_last)

    print("==============================================")
    print("ANÁLISE DA BASE — LOTOFÁCIL")
    print("==============================================")
    print(f"Concursos na base: {len(df)} | Último concurso: {int(df['Concurso'].max())}")
    print(f"Janela recente: últimos {ult} concursos")
    print()

    print("---- TOP 10 frequência (base inteira) ----")
    for d, f in top_all:
        print(f"{d:02d}: {f}")

    print("\n---- TOP 10 frequência (janela recente) ----")
    for d, f in top_last:
        print(f"{d:02d}: {f}")

    print("\n---- BOTTOM 10 (menos saíram na janela recente) ----")
    for d, f in bot_last:
        print(f"{d:02d}: {f}")

    print("\n---- Estatísticas gerais (base inteira) ----")
    for k, v in e_all.items():
        print(f"{k:12s}: {v:.2f}")

    print("\n---- Estatísticas (janela recente) ----")
    for k, v in e_last.items():
        print(f"{k:12s}: {v:.2f}")

    print("\nInterpretação rápida:")
    print("- q20_25_med: média de quantas dezenas entre 20 e 25 aparecem por concurso.")
    print("- pares_med: média de pares por concurso (normalmente perto de 7-8).")
    print("- soma_med: soma média das 15 dezenas (serve para manter jogos “plausíveis”).")


if __name__ == "__main__":
    main()