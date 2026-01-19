#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd


def _cols_dezenas() -> list[str]:
    return [f"D{i}" for i in range(1, 16)]


def _consecutivos(q: list[int]) -> int:
    r = sorted(q)
    return sum(1 for a, b in zip(r, r[1:]) if b == a + 1)


def _row_bins() -> list[set[int]]:
    return [
        set(range(1, 6)),
        set(range(6, 11)),
        set(range(11, 16)),
        set(range(16, 21)),
        set(range(21, 26)),
    ]


def _col_bins() -> list[set[int]]:
    return [
        {1, 6, 11, 16, 21},
        {2, 7, 12, 17, 22},
        {3, 8, 13, 18, 23},
        {4, 9, 14, 19, 24},
        {5, 10, 15, 20, 25},
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="base/base_limpa.xlsx", help="Caminho do base_limpa.xlsx")
    ap.add_argument("--ultimos", type=int, default=200, help="Quantos concursos finais analisar")
    args = ap.parse_args()

    base_path = Path(args.base)
    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    df = pd.read_excel(base_path).sort_values("Concurso")
    cols = _cols_dezenas()

    if not all(c in df.columns for c in cols):
        raise ValueError(f"Base não tem colunas D1..D15. Colunas: {list(df.columns)}")

    df_tail = df.tail(args.ultimos).copy()
    arr = df_tail[cols].to_numpy(dtype=int)

    sums = arr.sum(axis=1)
    odd_counts = (arr % 2 == 1).sum(axis=1)
    cons = np.array([_consecutivos(list(row)) for row in arr], dtype=int)

    # repetição com concurso anterior (dentro do recorte)
    reps = []
    for i in range(1, len(arr)):
        reps.append(len(set(arr[i - 1]) & set(arr[i])))
    reps = np.array(reps, dtype=int) if reps else np.array([], dtype=int)

    # linhas/colunas
    rb = _row_bins()
    cb = _col_bins()
    row_counts = []
    col_counts = []
    for row in arr:
        s = set(row)
        row_counts.append([len(s & b) for b in rb])
        col_counts.append([len(s & b) for b in cb])
    row_counts = np.array(row_counts, dtype=int)
    col_counts = np.array(col_counts, dtype=int)

    def pct(x, p):  # percentil
        return float(np.percentile(x, p)) if len(x) else float("nan")

    print("=" * 60)
    print(f"ANÁLISE BASE (últimos {args.ultimos} concursos do arquivo)")
    print(f"Arquivo: {base_path}")
    print(f"Concurso: {df_tail['Concurso'].min()} .. {df_tail['Concurso'].max()}")
    print("=" * 60)

    print("\nSOMA das dezenas:")
    print(f"  mediana: {np.median(sums):.0f} | p5: {pct(sums,5):.0f} | p95: {pct(sums,95):.0f}")

    print("\nÍMPARES por jogo:")
    print(f"  mediana: {np.median(odd_counts):.0f} | p5: {pct(odd_counts,5):.0f} | p95: {pct(odd_counts,95):.0f}")

    print("\nCONSECUTIVOS (pares adjacentes dentro do jogo):")
    print(f"  mediana: {np.median(cons):.0f} | p5: {pct(cons,5):.0f} | p95: {pct(cons,95):.0f}")

    if len(reps):
        c = Counter(reps)
        print("\nREPETIÇÃO com o concurso anterior:")
        print(f"  mediana: {np.median(reps):.0f} | p5: {pct(reps,5):.0f} | p95: {pct(reps,95):.0f}")
        print("  distribuição (qtde -> ocorrências):")
        for k in sorted(c):
            print(f"    {k:2d} -> {c[k]}")
    else:
        print("\nREPETIÇÃO: não calculado (poucos concursos no recorte).")

    print("\nDISTRIBUIÇÃO por LINHAS (1-5, 6-10, 11-15, 16-20, 21-25):")
    print(f"  médias: {row_counts.mean(axis=0).round(3).tolist()}")
    print(f"  p5: {np.percentile(row_counts,5,axis=0).tolist()} | p95: {np.percentile(row_counts,95,axis=0).tolist()}")

    print("\nDISTRIBUIÇÃO por COLUNAS (1/6/11/16/21 ...):")
    print(f"  médias: {col_counts.mean(axis=0).round(3).tolist()}")
    print(f"  p5: {np.percentile(col_counts,5,axis=0).tolist()} | p95: {np.percentile(col_counts,95,axis=0).tolist()}")

    print("\nSugestão de filtros/penalizações (com base nesses ranges):")
    print("  - ímpares: 6 a 9 (ideal 7–8)")
    print("  - soma: p5..p95")
    print("  - repetição com último concurso: p5..p95")
    print("  - consecutivos: p5..p95")
    print("  - linhas/colunas: evitar extremos (muito 0 ou muito 5)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())