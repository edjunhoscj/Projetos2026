from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Tuple, Dict

import pandas as pd


# =========================
# Utilitários
# =========================

def load_base_last_n(base_path: Path, n: int) -> List[Set[int]]:
    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    df = pd.read_excel(base_path)
    if df.empty:
        raise ValueError("Base vazia.")

    # tenta detectar 15 colunas de dezenas
    # preferindo D1..D15 se existirem
    prefer = [c for c in df.columns if str(c).strip().lower() in {f"d{i}" for i in range(1, 16)}]
    if len(prefer) >= 15:
        cols = prefer[:15]
    else:
        # fallback: pega as 15 primeiras colunas numéricas 1..25
        numeric_cols = []
        for c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().mean() < 0.6:
                continue
            vmin = s.min(skipna=True)
            vmax = s.max(skipna=True)
            if pd.notna(vmin) and pd.notna(vmax) and 1 <= vmin <= 25 and 1 <= vmax <= 25:
                numeric_cols.append(c)
        if len(numeric_cols) < 15:
            raise ValueError("Não consegui detectar 15 colunas de dezenas na base.")
        cols = numeric_cols[:15]

    df_tail = df.tail(int(n)).copy()

    sorteios: List[Set[int]] = []
    for _, row in df_tail.iterrows():
        nums: List[int] = []
        for c in cols:
            v = row.get(c)
            try:
                nn = int(v)
            except Exception:
                continue
            if 1 <= nn <= 25:
                nums.append(nn)
        if len(nums) >= 15:
            sorteios.append(set(nums[:15]))

    if not sorteios:
        raise ValueError("Não consegui extrair sorteios (15 dezenas) da base.")
    return sorteios


def freq_from_draws(draws: List[Set[int]]) -> Dict[int, int]:
    freq = {i: 0 for i in range(1, 26)}
    for s in draws:
        for d in s:
            if 1 <= d <= 25:
                freq[d] += 1
    return freq


def odd_count(game: Set[int]) -> int:
    return sum(1 for x in game if x % 2 == 1)


def sum_game(game: Set[int]) -> int:
    return sum(game)


def max_consecutive_run(nums_sorted: List[int]) -> int:
    best = 1
    cur = 1
    for i in range(1, len(nums_sorted)):
        if nums_sorted[i] == nums_sorted[i-1] + 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def bucket_counts(game: Set[int]) -> Tuple[int, int, int]:
    # 1-8, 9-17, 18-25
    a = sum(1 for x in game if 1 <= x <= 8)
    b = sum(1 for x in game if 9 <= x <= 17)
    c = sum(1 for x in game if 18 <= x <= 25)
    return a, b, c


@dataclass
class Constraints:
    odd_min: int
    odd_max: int
    sum_min: int
    sum_max: int
    max_seq: int
    bucket_min: int
    bucket_max: int


def passes_constraints(game: Set[int], cons: Constraints) -> bool:
    if len(game) != 15:
        return False

    o = odd_count(game)
    if not (cons.odd_min <= o <= cons.odd_max):
        return False

    s = sum_game(game)
    if not (cons.sum_min <= s <= cons.sum_max):
        return False

    ns = sorted(game)
    if max_consecutive_run(ns) > cons.max_seq:
        return False

    a, b, c = bucket_counts(game)
    if not (cons.bucket_min <= a <= cons.bucket_max):
        return False
    if not (cons.bucket_min <= b <= cons.bucket_max):
        return False
    if not (cons.bucket_min <= c <= cons.bucket_max):
        return False

    return True


def score_game(game: Set[int], freq: Dict[int, int], modo: str) -> float:
    """
    Score simples:
      - agressivo: favorece dezenas quentes (frequência alta)
      - conservador: favorece equilíbrio (penaliza extremos)
    """
    fsum = sum(freq[d] for d in game)

    if modo == "agressivo":
        # quanto mais "quente", melhor
        return float(fsum)

    # conservador:
    # penaliza concentração em dezenas muito quentes e muito frias
    freqs = sorted(freq[d] for d in game)
    # spread (variação)
    spread = freqs[-1] - freqs[0]
    # penaliza spread grande e prioriza um fsum decente
    return float(fsum) - 0.6 * float(spread)


def jaccard(a: Set[int], b: Set[int]) -> float:
    return len(a & b) / len(a | b)


def diversify(top: List[Tuple[float, Set[int]]], finais: int, max_sim: float) -> List[Set[int]]:
    chosen: List[Set[int]] = []
    for _, g in top:
        if len(chosen) >= finais:
            break
        ok = True
        for c in chosen:
            if jaccard(g, c) >= max_sim:
                ok = False
                break
        if ok:
            chosen.append(g)
    return chosen


# =========================
# CLI
# =========================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["agressivo", "conservador"], required=True)
    ap.add_argument("--ultimos", type=int, default=300)
    ap.add_argument("--finais", type=int, default=5)
    ap.add_argument("--base", default="base/base_limpa.xlsx")
    ap.add_argument("--candidatos", type=int, default=80000, help="Qtde de jogos candidatos (amostragem)")
    ap.add_argument("--seed", type=int, default=0, help="Seed (0 = aleatória)")
    ap.add_argument("--max-sim", type=float, default=0.75, help="Similaridade máxima (diversidade)")
    args = ap.parse_args()

    base_path = Path(args.base)

    if args.seed and args.seed != 0:
        random.seed(args.seed)

    draws = load_base_last_n(base_path, args.ultimos)
    freq = freq_from_draws(draws)

    # constraints por modo
    if args.modo == "agressivo":
        cons = Constraints(
            odd_min=6, odd_max=10,
            sum_min=150, sum_max=235,
            max_seq=5,
            bucket_min=3, bucket_max=7,
        )
    else:
        cons = Constraints(
            odd_min=7, odd_max=9,
            sum_min=165, sum_max=220,
            max_seq=4,
            bucket_min=4, bucket_max=6,
        )

    print("=" * 46)
    print("WIZARD LOTOFÁCIL - CLI")
    print("=" * 46)
    print(f"Base histórica: {base_path}")
    print(f"Modo: {args.modo}")
    print(f"Últimos: {args.ultimos} concursos")
    print(f"Jogos finais desejados: {args.finais}")
    print(f"Candidatos (amostragem): {args.candidatos}")
    print("=" * 46)
    print("")

    # gera candidatos
    cand: List[Tuple[float, Set[int]]] = []
    tries = 0
    max_tries = max(args.candidatos * 5, 200000)

    while len(cand) < args.candidatos and tries < max_tries:
        tries += 1
        g = set(random.sample(range(1, 26), 15))
        if not passes_constraints(g, cons):
            continue
        sc = score_game(g, freq, args.modo)
        cand.append((sc, g))

    if not cand:
        print("⚠️ Atenção: não consegui gerar candidatos com as restrições atuais.")
        print("Jogos finais: 0")
        return

    cand.sort(key=lambda x: x[0], reverse=True)

    # pega um top maior e depois diversifica
    top_pool = cand[: max(args.finais * 80, 400)]
    chosen = diversify(top_pool, args.finais, args.max_sim)

    if len(chosen) < args.finais:
        # fallback: completa sem diversidade (não falha)
        for _, g in top_pool:
            if len(chosen) >= args.finais:
                break
            if g not in chosen:
                chosen.append(g)

    print("=" * 46)
    print("JOGOS GERADOS PELO WIZARD")
    print("=" * 46)
    print(f"Modo: {args.modo}")
    print(f"Jogos finais: {len(chosen)}")
    print("")

    for i, g in enumerate(chosen, start=1):
        nums = " ".join(f"{x:02d}" for x in sorted(g))
        print(f"Jogo {i:02d}: {nums}")

    print("")
    print("Boa sorte! 🍀")


if __name__ == "__main__":
    main()