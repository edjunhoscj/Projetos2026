from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

import pandas as pd


# =========================
# Leitura / parsing jogos
# =========================

def parse_jogos_arquivo(path: Path) -> List[List[int]]:
    """
    Lê um TXT do Wizard e extrai jogos.
    Robusto: pega qualquer sequência válida de 15 dezenas (1..25, sem repetição) por linha,
    mesmo que tenha textos como 'Jogo 01:' etc.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de jogos não encontrado: {path}")

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    jogos: List[List[int]] = []

    for line in lines:
        # todos os números 1-2 dígitos na linha
        nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", line)]
        if len(nums) < 15:
            continue

        # procura um bloco de 15 dezenas válido dentro da linha
        for i in range(0, len(nums) - 14):
            bloco = nums[i : i + 15]
            if all(1 <= n <= 25 for n in bloco) and len(set(bloco)) == 15:
                jogos.append(sorted(bloco))
                break  # um jogo por linha já basta

    if not jogos:
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo. Confirme se é um TXT gerado pelo wizard."
        )

    return jogos


# =========================
# Leitura base histórica
# =========================

def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base histórica não encontrada: {base_path}")

    df = pd.read_excel(base_path)

    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base: {faltando}")

    # garante ordenação
    df = df.sort_values("Concurso").reset_index(drop=True)
    return df


def ultimos_concursos(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.tail(n).reset_index(drop=True)


# =========================
# Backtest
# =========================

def acertos(jogo: List[int], concurso_row: pd.Series) -> int:
    dezenas_sorteadas = {int(concurso_row[f"D{i}"]) for i in range(1, 16)}
    return len(set(jogo) & dezenas_sorteadas)


@dataclass
class Stats:
    jogo_idx: int
    media: float
    mediana: float
    maximo: int
    minimo: int
    dist: Dict[int, int]  # quantas vezes fez X acertos


def backtest_jogos(jogos: List[List[int]], ultimos_df: pd.DataFrame) -> List[Stats]:
    resultados: List[Stats] = []

    for idx, jogo in enumerate(jogos, start=1):
        lista_acertos = [acertos(jogo, row) for _, row in ultimos_df.iterrows()]

        dist: Dict[int, int] = {}
        for a in lista_acertos:
            dist[a] = dist.get(a, 0) + 1

        s = Stats(
            jogo_idx=idx,
            media=float(pd.Series(lista_acertos).mean()),
            mediana=float(pd.Series(lista_acertos).median()),
            maximo=int(max(lista_acertos)),
            minimo=int(min(lista_acertos)),
            dist=dist,
        )
        resultados.append(s)

    return resultados


def stats_to_df(stats: List[Stats]) -> pd.DataFrame:
    # Descobre todas as chaves de dist presentes (ex.: 11,12,13...)
    all_keys = sorted({k for s in stats for k in s.dist.keys()})

    rows = []
    for s in stats:
        row = {
            "Jogo": s.jogo_idx,
            "media_acertos": round(s.media, 4),
            "mediana_acertos": round(s.mediana, 4),
            "max_acertos": s.maximo,
            "min_acertos": s.minimo,
        }
        for k in all_keys:
            # colunas como "11.0" para casar com o que você já viu
            row[f"{float(k):.1f}"] = int(s.dist.get(k, 0))
        rows.append(row)

    df = pd.DataFrame(rows)
    # Ordena por melhor média
    df = df.sort_values(["media_acertos", "max_acertos"], ascending=[False, False]).reset_index(drop=True)
    return df


# =========================
# CLI
# =========================

def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest dos jogos gerados pelo Wizard.")
    parser.add_argument("--jogos-file", required=True, help="TXT com jogos gerados pelo wizard")
    parser.add_argument("--base", default="base/base_limpa.xlsx", help="Base limpa (xlsx)")
    parser.add_argument("--ultimos", type=int, default=200, help="Quantos concursos usar no backtest")
    parser.add_argument("--csv-out", required=True, help="Saída CSV (ex.: outputs/backtest_agressivo_x.csv)")
    args = parser.parse_args()

    jogos_file = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)

    base_df = carregar_base(base_path)
    ult_df = ultimos_concursos(base_df, args.ultimos)

    jogos = parse_jogos_arquivo(jogos_file)
    stats = backtest_jogos(jogos, ult_df)
    out_df = stats_to_df(stats)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(csv_out, index=False, encoding="utf-8")

    print("\n========================================")
    print("        BACKTEST DOS JOGOS GERADOS      ")
    print("========================================")
    print(f"Arquivo jogos: {jogos_file}")
    print(f"Concursos usados: {args.ultimos}")
    print(f"Saída CSV: {csv_out}")
    print("\nTop 5 por média:")
    print(out_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()