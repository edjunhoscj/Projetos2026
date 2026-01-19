#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Dict

import pandas as pd


# =========================
# Helpers: parsing jogos TXT
# =========================

_NUM_RE = re.compile(r"\b(\d{1,2})\b")


def _line_to_game_numbers(line: str) -> Optional[List[int]]:
    """
    Extrai um jogo (15 dezenas) de uma linha, aceitando vários formatos:
      - "Jogo 01: 02 03 05 ... 23"
      - "02 03 05 06 07 ... 23"
      - qualquer linha que contenha pelo menos 15 números entre 1..25
    Retorna lista de 15 ints ordenados (1..25) ou None.
    """
    nums = []
    for m in _NUM_RE.finditer(line):
        try:
            n = int(m.group(1))
        except Exception:
            continue
        if 1 <= n <= 25:
            nums.append(n)

    # remove duplicados preservando ordem
    seen = set()
    nums2 = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            nums2.append(n)

    if len(nums2) >= 15:
        game = nums2[:15]
        # valida
        if len(game) == 15 and all(1 <= x <= 25 for x in game):
            return sorted(game)

    return None


def parse_jogos_arquivo(path: Path) -> List[List[int]]:
    """
    Lê um arquivo TXT gerado pelo wizard (ou similar) e tenta extrair jogos.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    jogos: List[List[int]] = []
    for line in text:
        g = _line_to_game_numbers(line)
        if g:
            jogos.append(g)

    # remove duplicados
    unique = []
    seen = set()
    for g in jogos:
        key = tuple(g)
        if key not in seen:
            seen.add(key)
            unique.append(g)

    if not unique:
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo. Confirme se é um TXT gerado pelo Wizard "
            "e se ele realmente contém linhas com 15 dezenas."
        )

    return unique


# =========================
# Helpers: reading base
# =========================

def _try_extract_15_from_row(row: Sequence) -> Optional[List[int]]:
    nums = []
    for v in row:
        try:
            if pd.isna(v):
                continue
        except Exception:
            pass
        s = str(v).strip()
        if not s:
            continue
        # se vier "01 02 03 ..." num único campo
        found = [int(x) for x in _NUM_RE.findall(s) if 1 <= int(x) <= 25]
        for n in found:
            nums.append(n)

    # remove duplicados
    seen = set()
    nums2 = []
    for n in nums:
        if 1 <= n <= 25 and n not in seen:
            seen.add(n)
            nums2.append(n)

    if len(nums2) >= 15:
        return sorted(nums2[:15])
    return None


def load_base_draws(base_path: Path) -> List[List[int]]:
    """
    Carrega a base histórica (Excel) e tenta identificar as 15 dezenas por concurso.

    Compatível com:
      - colunas separadas (D1..D15, bola1..bola15, etc.)
      - coluna única com string contendo as dezenas
    """
    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    df = pd.read_excel(base_path)

    # 1) tenta achar 15 colunas numéricas (1..25)
    # pega colunas com muitos valores numéricos válidos
    candidate_cols = []
    for c in df.columns:
        series = df[c]
        # tenta converter para num
        s_num = pd.to_numeric(series, errors="coerce")
        valid = s_num.between(1, 25).sum()
        if valid > max(10, int(len(df) * 0.2)):  # heurística
            candidate_cols.append(c)

    # se tiver >= 15 colunas candidatas, tenta montar por linha
    draws: List[List[int]] = []
    if len(candidate_cols) >= 15:
        # pega as 15 melhores colunas por "valid"
        scored = []
        for c in candidate_cols:
            s_num = pd.to_numeric(df[c], errors="coerce")
            scored.append((c, int(s_num.between(1, 25).sum())))
        scored.sort(key=lambda x: x[1], reverse=True)
        cols15 = [c for c, _ in scored[:15]]

        for _, r in df[cols15].iterrows():
            nums = _try_extract_15_from_row(list(r.values))
            if nums and len(nums) == 15:
                draws.append(nums)

    # 2) fallback: tenta extrair 15 dezenas de cada linha inteira
    if not draws:
        for _, r in df.iterrows():
            nums = _try_extract_15_from_row(list(r.values))
            if nums and len(nums) == 15:
                draws.append(nums)

    # remove inválidas
    draws2 = []
    for d in draws:
        if len(d) == 15 and all(1 <= x <= 25 for x in d):
            draws2.append(sorted(d))

    if not draws2:
        raise ValueError(
            "Não consegui extrair as 15 dezenas por concurso da base. "
            "Verifique se o Excel contém as dezenas (1..25) em colunas separadas ou em texto."
        )

    return draws2


# =========================
# Backtest core
# =========================

@dataclass
class GameStats:
    jogo_id: int
    media_acertos: float
    max_acertos: int
    min_acertos: int
    counts: Dict[int, int]


def acertos(game: Sequence[int], draw: Sequence[int]) -> int:
    s = set(game)
    return sum(1 for x in draw if x in s)


def evaluate_games(
    jogos: List[List[int]],
    draws: List[List[int]],
    ultimos: int,
    thresholds: Sequence[int] = (11, 12, 13, 14, 15),
) -> Tuple[pd.DataFrame, List[List[int]]]:
    # usa os últimos N concursos
    if ultimos <= 0:
        raise ValueError("--ultimos deve ser > 0")
    draws_used = draws[-ultimos:] if len(draws) >= ultimos else draws[:]

    rows = []
    for idx, game in enumerate(jogos, start=1):
        hits = [acertos(game, d) for d in draws_used]
        if not hits:
            continue
        counts = {t: sum(1 for h in hits if h == t) for t in thresholds}
        rows.append(
            {
                "jogo": idx,
                "media_acertos": round(sum(hits) / len(hits), 4),
                "max_acertos": int(max(hits)),
                "min_acertos": int(min(hits)),
                **{f"{t}.0": int(counts[t]) for t in thresholds},  # mantém padrão "11.0"
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Não consegui avaliar os jogos (df vazio). Verifique o TXT e a base.")

    df = df.sort_values(["media_acertos", "max_acertos", "min_acertos"], ascending=[False, False, False])
    return df, draws_used


def df_to_pretty_text(df: pd.DataFrame, titulo: str) -> str:
    # formatação simples em texto
    lines = []
    lines.append("=" * 46)
    lines.append(titulo)
    lines.append("=" * 46)
    lines.append("")
    lines.append(df.to_string(index=False))
    lines.append("")
    lines.append("Legenda:")
    lines.append(" - media_acertos : média de acertos nos concursos analisados")
    lines.append(" - max_acertos   : maior número de acertos que o jogo fez")
    lines.append(" - min_acertos   : menor número de acertos que o jogo fez")
    lines.append(" - colunas 11.0, 12.0, 13.0...: quantas vezes fez exatamente 11, 12, 13...")
    lines.append("")
    return "\n".join(lines)


# =========================
# CLI
# =========================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backtest de jogos (Wizard Lotofácil)")
    p.add_argument("--jogos-file", required=True, help="TXT com jogos gerados (wizard)")
    p.add_argument("--base", default="base/base_limpa.xlsx", help="Base histórica (xlsx)")
    p.add_argument("--ultimos", type=int, default=20, help="Quantos últimos concursos usar")
    p.add_argument("--csv-out", required=True, help="Saída CSV (obrigatório)")
    # TXT opcional (para compatibilidade com seu relatório completo)
    p.add_argument("--out", required=False, help="Saída TXT formatada (opcional)")
    p.add_argument("--titulo", default="BACKTEST", help="Título no TXT (se --out for usado)")
    return p


def main() -> None:
    args = build_parser().parse_args()

    jogos_path = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)
    txt_out = Path(args.out) if args.out else None

    jogos = parse_jogos_arquivo(jogos_path)
    draws = load_base_draws(base_path)

    df, _ = evaluate_games(jogos, draws, ultimos=args.ultimos)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False)

    if txt_out:
        txt_out.parent.mkdir(parents=True, exist_ok=True)
        txt = df_to_pretty_text(df, args.titulo)
        txt_out.write_text(txt, encoding="utf-8")

    print(f"OK: gerou CSV em {csv_out}")
    if txt_out:
        print(f"OK: gerou TXT em {txt_out}")


if __name__ == "__main__":
    main()