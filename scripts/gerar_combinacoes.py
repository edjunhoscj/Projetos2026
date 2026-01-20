from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import pandas as pd


def _load_base(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    df = df[cols].copy().sort_values("Concurso").reset_index(drop=True)
    return df


def _freq(df: pd.DataFrame) -> Dict[int, int]:
    cols = [f"D{i}" for i in range(1, 16)]
    arr = df[cols].to_numpy(dtype=int).flatten()
    f = {d: 0 for d in range(1, 26)}
    for x in arr:
        f[int(x)] += 1
    return f


def _recent_freq(df: pd.DataFrame, ultimos: int = 200) -> Dict[int, int]:
    return _freq(df.tail(int(ultimos)))


def _respeita_consecutivos(nums: List[int], max_run: int = 4) -> bool:
    nums = sorted(nums)
    run = 1
    for i in range(1, len(nums)):
        if nums[i] == nums[i-1] + 1:
            run += 1
            if run > max_run:
                return False
        else:
            run = 1
    return True


def _validar_padroes(nums: List[int]) -> bool:
    nums = sorted(nums)
    pares = sum(1 for x in nums if x % 2 == 0)
    soma = sum(nums)
    qtd_20_25 = sum(1 for x in nums if 20 <= x <= 25)

    # filtros suaves (não travam demais)
    if not (6 <= pares <= 9):
        return False
    if not (165 <= soma <= 240):
        return False
    if not (2 <= qtd_20_25 <= 7):
        return False
    if not _respeita_consecutivos(nums, max_run=4):
        return False
    return True


def _sample_weighted(weights: Dict[int, float], k: int = 15) -> List[int]:
    nums = list(weights.keys())
    w = np.array([weights[n] for n in nums], dtype=float)
    w = w / w.sum()
    # sem reposição
    chosen = np.random.choice(nums, size=k, replace=False, p=w)
    return sorted([int(x) for x in chosen])


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera combinacoes inteligentes para o Wizard (rápido, diversificado).")
    ap.add_argument("--base", default="base/base_limpa.xlsx")
    ap.add_argument("--out", default="combinacoes/combinacoes_inteligentes.csv")
    ap.add_argument("--qtd", type=int, default=80000, help="Quantidade de combinações alvo (default: 80000)")
    ap.add_argument("--ultimos", type=int, default=200, help="Janela recente para tendência (default: 200)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(int(args.seed))
    np.random.seed(int(args.seed))

    base_path = Path(args.base)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = _load_base(base_path)

    f_all = _freq(df)
    f_recent = _recent_freq(df, ultimos=int(args.ultimos))

    # pesos: mistura (histórico + recente), com compressão log
    weights: Dict[int, float] = {}
    for d in range(1, 26):
        a = float(f_all[d])
        r = float(f_recent[d])
        # peso base + tendência recente
        w = (np.log1p(a) * 0.65) + (np.log1p(r) * 0.35)
        # pequeno incentivo para 20..25 (observação do usuário)
        if 20 <= d <= 25:
            w *= 1.08
        weights[d] = float(w)

    # evita repetir concursos recentes idênticos
    ultimos_tuplas: Set[Tuple[int, ...]] = set()
    last_rows = df.tail(200)
    for _, row in last_rows.iterrows():
        nums = [int(row[f"D{i}"]) for i in range(1, 16)]
        ultimos_tuplas.add(tuple(sorted(nums)))

    alvo = int(args.qtd)
    vistos: Set[Tuple[int, ...]] = set()
    out: List[str] = []

    tentativas = 0
    max_tentativas = max(300000, alvo * 5)

    while len(out) < alvo and tentativas < max_tentativas:
        tentativas += 1
        nums = _sample_weighted(weights, 15)
        t = tuple(nums)

        if t in vistos:
            continue
        if t in ultimos_tuplas:
            continue
        if not _validar_padroes(nums):
            continue

        vistos.add(t)
        out.append(" ".join(f"{x:02d}" for x in nums))

    # salva
    with out_path.open("w", encoding="utf-8") as f:
        for line in out:
            f.write(line + "\n")

    print(f"✅ combinações inteligentes geradas: {len(out)}")
    print(f"📁 arquivo: {out_path}")
    if len(out) < alvo:
        print(f"⚠️ Não atingiu o alvo {alvo}. Tente aumentar max_tentativas ou relaxar filtros.")


if __name__ == "__main__":
    main()