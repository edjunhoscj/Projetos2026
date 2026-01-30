# scripts/analise_padroes.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def carregar_base_xlsx(base_path: Path) -> pd.DataFrame:
    df = pd.read_excel(base_path)
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Base inválida. Colunas faltando: {faltando}")
    return df.sort_values("Concurso").reset_index(drop=True)


def extrair_dezenas(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    return df[cols].to_numpy(dtype=int, copy=True)


def grid_pos(n: int) -> Tuple[int, int]:
    """Mapeia 1..25 em (row, col) 0..4 no grid 5x5."""
    n = int(n)
    r = (n - 1) // 5
    c = (n - 1) % 5
    return r, c


def quadrante(n: int) -> str:
    """
    Divide o 5x5 em 4 blocos (não fica igualzinho, mas é útil):
      - TL: rows 0..2, cols 0..2 (9)
      - TR: rows 0..2, cols 3..4 (6)
      - BL: rows 3..4, cols 0..2 (6)
      - BR: rows 3..4, cols 3..4 (4)
    """
    r, c = grid_pos(n)
    if r <= 2 and c <= 2:
        return "TL"
    if r <= 2 and c >= 3:
        return "TR"
    if r >= 3 and c <= 2:
        return "BL"
    return "BR"


def count_runs(dezenas: List[int]) -> int:
    """Número de 'runs' consecutivos (ex: 1-2-3 conta como 1 run)."""
    d = sorted(dezenas)
    runs = 0
    i = 0
    while i < len(d):
        j = i
        while j + 1 < len(d) and d[j + 1] == d[j] + 1:
            j += 1
        if j > i:
            runs += 1
        i = j + 1
    return runs


def max_run_len(dezenas: List[int]) -> int:
    d = sorted(dezenas)
    best = 1
    cur = 1
    for i in range(1, len(d)):
        if d[i] == d[i-1] + 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def analisar(df: pd.DataFrame) -> Dict[str, object]:
    arr = extrair_dezenas(df)
    n = len(df)
    if n == 0:
        return {}

    # Distribuições
    pares = []
    soma = []
    runs = []
    runmax = []
    rep_prev = []

    rows_counts = np.zeros((n, 5), dtype=int)  # 5 linhas
    cols_counts = np.zeros((n, 5), dtype=int)  # 5 colunas
    quad_counts = np.zeros((n, 4), dtype=int)  # TL,TR,BL,BR

    quad_map = {"TL": 0, "TR": 1, "BL": 2, "BR": 3}

    for i in range(n):
        dezenas = list(map(int, arr[i]))
        s = set(dezenas)

        pares.append(sum(1 for x in dezenas if x % 2 == 0))
        soma.append(sum(dezenas))
        runs.append(count_runs(dezenas))
        runmax.append(max_run_len(dezenas))

        # repetição vs concurso anterior
        if i > 0:
            rep_prev.append(len(s & set(arr[i-1])))
        else:
            rep_prev.append(0)

        # linhas/colunas/quadrantes
        for d in dezenas:
            r, c = grid_pos(d)
            rows_counts[i, r] += 1
            cols_counts[i, c] += 1
            quad_counts[i, quad_map[quadrante(d)]] += 1

    pares = np.array(pares)
    soma = np.array(soma)
    runs = np.array(runs)
    runmax = np.array(runmax)
    rep_prev = np.array(rep_prev)

    # Gaps: há quantos concursos cada dezena não aparece (no recorte)
    last_seen = {d: None for d in range(1, 26)}
    for idx in range(n-1, -1, -1):
        dezenas = set(arr[idx])
        for d in dezenas:
            if last_seen[d] is None:
                last_seen[d] = (n - 1) - idx
        if all(v is not None for v in last_seen.values()):
            break

    # Frequência
    freq = {d: 0 for d in range(1, 26)}
    for row in arr:
        for d in row:
            freq[int(d)] += 1
    freq = {d: freq[d] / n for d in range(1, 26)}

    out = {
        "n": n,
        "freq": freq,
        "last_seen_gap": last_seen,  # 0 = saiu no último concurso do recorte
        "pares": pares,
        "soma": soma,
        "runs": runs,
        "runmax": runmax,
        "rep_prev": rep_prev,
        "rows_counts": rows_counts,
        "cols_counts": cols_counts,
        "quad_counts": quad_counts,
    }
    return out


def qband(x: np.ndarray, lo=0.10, hi=0.90) -> Tuple[float, float, float]:
    """retorna (p10, p50, p90) por padrão."""
    if len(x) == 0:
        return 0.0, 0.0, 0.0
    return (float(np.quantile(x, lo)), float(np.quantile(x, 0.50)), float(np.quantile(x, hi)))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="Base limpa XLSX")
    p.add_argument("--ultimos", type=int, default=300)
    p.add_argument("--out", required=True, help="Saída TXT")
    args = p.parse_args()

    base = carregar_base_xlsx(Path(args.base))
    df = base.tail(int(args.ultimos)).reset_index(drop=True)

    r = analisar(df)
    n = int(r["n"])

    pares_p10, pares_p50, pares_p90 = qband(r["pares"])
    soma_p10, soma_p50, soma_p90 = qband(r["soma"])
    runs_p10, runs_p50, runs_p90 = qband(r["runs"])
    runmax_p10, runmax_p50, runmax_p90 = qband(r["runmax"])
    rep_p10, rep_p50, rep_p90 = qband(r["rep_prev"])

    # linhas/colunas/quads: bandas por posição
    rows = r["rows_counts"]
    cols = r["cols_counts"]
    quads = r["quad_counts"]

    def band_mat(mat: np.ndarray) -> List[Tuple[float, float, float]]:
        bands = []
        for j in range(mat.shape[1]):
            bands.append(qband(mat[:, j]))
        return bands

    rows_b = band_mat(rows)
    cols_b = band_mat(cols)
    quads_b = band_mat(quads)

    # top freq / bottom freq
    freq = r["freq"]
    freq_sorted = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    top10 = freq_sorted[:10]
    bot10 = sorted(freq.items(), key=lambda kv: kv[1])[:10]

    gaps = r["last_seen_gap"]
    gaps_sorted = sorted(gaps.items(), key=lambda kv: (kv[1] if kv[1] is not None else 10**9), reverse=True)

    lines = []
    lines.append("==============================================")
    lines.append(f"ANÁLISE DE PADRÕES — ÚLTIMOS {n} CONCURSOS")
    lines.append("==============================================\n")

    lines.append("Bandas (p10 / p50 / p90):")
    lines.append(f"- Pares: {pares_p10:.1f} / {pares_p50:.1f} / {pares_p90:.1f}")
    lines.append(f"- Soma : {soma_p10:.1f} / {soma_p50:.1f} / {soma_p90:.1f}")
    lines.append(f"- Runs consecutivos (qtd): {runs_p10:.1f} / {runs_p50:.1f} / {runs_p90:.1f}")
    lines.append(f"- Tamanho máx run: {runmax_p10:.1f} / {runmax_p50:.1f} / {runmax_p90:.1f}")
    lines.append(f"- Repetição vs concurso anterior: {rep_p10:.1f} / {rep_p50:.1f} / {rep_p90:.1f}\n")

    lines.append("Linhas (1–5,6–10,11–15,16–20,21–25) bandas p10/p50/p90:")
    for i, (a, b, c) in enumerate(rows_b, start=1):
        lines.append(f"  Linha {i}: {a:.1f} / {b:.1f} / {c:.1f}")
    lines.append("")

    lines.append("Colunas (1/6/11/16/21 etc.) bandas p10/p50/p90:")
    for i, (a, b, c) in enumerate(cols_b, start=1):
        lines.append(f"  Col {i}: {a:.1f} / {b:.1f} / {c:.1f}")
    lines.append("")

    lines.append("Quadrantes (TL/TR/BL/BR) bandas p10/p50/p90:")
    qnames = ["TL", "TR", "BL", "BR"]
    for i, name in enumerate(qnames):
        a, b, c = quads_b[i]
        lines.append(f"  {name}: {a:.1f} / {b:.1f} / {c:.1f}")
    lines.append("")

    lines.append("Top 10 dezenas mais frequentes (freq):")
    lines.append("  " + ", ".join([f"{d:02d}({f:.3f})" for d, f in top10]))
    lines.append("")

    lines.append("Bottom 10 dezenas menos frequentes (freq):")
    lines.append("  " + ", ".join([f"{d:02d}({f:.3f})" for d, f in bot10]))
    lines.append("")

    lines.append("Dezenas mais 'atrasadas' no recorte (gap = concursos desde a última aparição):")
    lines.append("  " + ", ".join([f"{d:02d}(gap={g})" for d, g in gaps_sorted[:10]]))
    lines.append("")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()