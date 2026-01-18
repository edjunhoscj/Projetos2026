from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import pandas as pd


# =========================
# Parser robusto de jogos
# =========================

_RE_15_NUMS = re.compile(r"(?<!\d)(\d{1,2})(?!\d)")

def _extrair_15_dezenas_da_linha(line: str) -> List[int] | None:
    """
    Extrai dezenas de uma linha com qualquer formato, por ex:
      - "Jogo 01: 02 03 05 ... 23"
      - "02 03 05 06 ... 23"
      - "Jogo 3 — 01 02 ... 15"
    Retorna lista com 15 ints (1..25) ou None.
    """
    nums = [int(x) for x in _RE_15_NUMS.findall(line)]
    if len(nums) < 15:
        return None

    # Estratégia: tenta janelas de 15 números válidos (1..25) e sem repetição
    for i in range(0, len(nums) - 14):
        chunk = nums[i : i + 15]
        if all(1 <= n <= 25 for n in chunk) and len(set(chunk)) == 15:
            return sorted(chunk)

    return None


def parse_jogos_arquivo(path: Path) -> List[Tuple[int, ...]]:
    """
    Lê um TXT gerado pelo wizard e retorna lista de jogos (tuplas ordenadas).
    É tolerante a logs, cabeçalhos e texto no meio.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    jogos: List[Tuple[int, ...]] = []

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        dezenas = _extrair_15_dezenas_da_linha(line)
        if dezenas:
            jogos.append(tuple(dezenas))

    # remove duplicados preservando ordem
    jogos_unicos: List[Tuple[int, ...]] = []
    seen = set()
    for j in jogos:
        if j not in seen:
            seen.add(j)
            jogos_unicos.append(j)

    if not jogos_unicos:
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo. "
            "Confirme se é um TXT gerado pelo wizard (com 15 dezenas por jogo)."
        )

    return jogos_unicos


# =========================
# Backtest
# =========================

def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base histórica não encontrada em: {base_path}")

    df = pd.read_excel(base_path)
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base: {faltando}")

    df = df.sort_values("Concurso").reset_index(drop=True)
    return df


def acertos(jogo: Tuple[int, ...], linha_concurso: pd.Series) -> int:
    dezenas_sorteadas = {int(linha_concurso[f"D{i}"]) for i in range(1, 16)}
    return len(set(jogo) & dezenas_sorteadas)


@dataclass
class BacktestResultado:
    jogo_idx: int
    media_acertos: float
    max_acertos: int
    min_acertos: int
    freq_por_acerto: dict[int, int]


def backtest_jogos(jogos: List[Tuple[int, ...]], base_df: pd.DataFrame, ultimos: int) -> pd.DataFrame:
    ultimos_df = base_df.tail(ultimos).reset_index(drop=True)

    resultados: List[BacktestResultado] = []

    for idx, jogo in enumerate(jogos, start=1):
        lista_acertos: List[int] = []
        for _, row in ultimos_df.iterrows():
            lista_acertos.append(acertos(jogo, row))

        media = float(pd.Series(lista_acertos).mean())
        mx = int(max(lista_acertos))
        mn = int(min(lista_acertos))

        freq = pd.Series(lista_acertos).value_counts().to_dict()
        resultados.append(
            BacktestResultado(
                jogo_idx=idx,
                media_acertos=media,
                max_acertos=mx,
                min_acertos=mn,
                freq_por_acerto={int(k): int(v) for k, v in freq.items()},
            )
        )

    # monta dataframe
    rows = []
    for r in resultados:
        row = {
            "Jogo": r.jogo_idx,
            "media_acertos": round(r.media_acertos, 4),
            "max_acertos": r.max_acertos,
            "min_acertos": r.min_acertos,
        }
        # colunas 0..15 se existirem
        for k, v in r.freq_por_acerto.items():
            row[float(k)] = v  # mantém compatível com seu CSV "11.0, 12.0..."
        rows.append(row)

    df = pd.DataFrame(rows)

    # garante colunas 11..15 (se não existirem, coloca 0)
    for k in [11.0, 12.0, 13.0, 14.0, 15.0]:
        if k not in df.columns:
            df[k] = 0

    # ordena colunas
    base_cols = ["Jogo", "media_acertos", "max_acertos", "min_acertos"]
    acerto_cols = sorted([c for c in df.columns if isinstance(c, float)])
    df = df[base_cols + acerto_cols]

    # ordena pelo melhor desempenho médio
    df = df.sort_values(["media_acertos", "max_acertos"], ascending=[False, False]).reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest dos jogos gerados (TXT do wizard -> CSV).")
    parser.add_argument("--jogos-file", required=True, help="TXT com jogos gerados pelo wizard")
    parser.add_argument("--base", default="base/base_limpa.xlsx", help="Base histórica limpa (xlsx)")
    parser.add_argument("--ultimos", type=int, default=200, help="Quantos concursos recentes avaliar")
    parser.add_argument("--csv-out", required=True, help="Arquivo CSV de saída (outputs/...)")
    args = parser.parse_args()

    jogos_file = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)

    jogos = parse_jogos_arquivo(jogos_file)
    base_df = carregar_base(base_path)

    df = backtest_jogos(jogos, base_df, args.ultimos)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False, encoding="utf-8")

    print(f"✅ Backtest gerado: {csv_out} ({len(df)} jogos)")


if __name__ == "__main__":
    main()