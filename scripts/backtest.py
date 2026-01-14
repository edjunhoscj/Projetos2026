from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

import pandas as pd

BASE_LIMPA_PATH = Path("base/base_limpa.xlsx")


# =========================
# Carregar base limpa
# =========================
def carregar_base_limpa(path: Path = BASE_LIMPA_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Base limpa não encontrada em: {path}")

    df = pd.read_excel(path)

    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base limpa: {faltando}")

    df = df.sort_values("Concurso").reset_index(drop=True)
    return df


# =========================
# Ler jogos do TXT
# =========================
def parse_jogos_arquivo(path: Path) -> List[Tuple[int, ...]]:
    """
    Lê um arquivo TXT gerado pelo wizard (outputs/...) e extrai os jogos.

    Exemplo de linha:
      'Jogo 01: 01 03 04 05 08 09 11 12 14 15 17 20 21 23 25'
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de jogos não encontrado: {path}")

    jogos: List[Tuple[int, ...]] = []

    padrao = re.compile(r"Jogo\s+\d+:\s+(.+)$")

    with path.open("r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            m = padrao.search(linha)
            if not m:
                continue

            numeros_str = m.group(1).split()
            try:
                dezenas = tuple(int(x) for x in numeros_str)
            except ValueError:
                continue

            if len(dezenas) == 15:
                jogos.append(dezenas)

    if not jogos:
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo. "
            "Confirme se é um TXT gerado pelo wizard."
        )

    return jogos


def contar_acertos(jogo: Tuple[int, ...], dezenas_sorteadas: Tuple[int, ...]) -> int:
    return len(set(jogo).intersection(dezenas_sorteadas))


# =========================
# Backtest
# =========================
def backtest_jogos(
    df_base: pd.DataFrame,
    jogos: List[Tuple[int, ...]],
    ultimos: int,
) -> pd.DataFrame:
    """
    Para cada concurso nos últimos N, calcula quantos acertos cada jogo teve.
    Retorna um DataFrame com estatísticas agregadas.
    """
    if ultimos <= 0:
        raise ValueError("--ultimos deve ser > 0")

    df = df_base.tail(ultimos).copy()

    resultados = []
    for _, linha in df.iterrows():
        concurso = int(linha["Concurso"])
        dezenas_concurso = tuple(int(linha[f"D{i}"]) for i in range(1, 16))

        for idx, jogo in enumerate(jogos, start=1):
            acertos = contar_acertos(jogo, dezenas_concurso)
            resultados.append(
                {
                    "Concurso": concurso,
                    "Jogo": idx,
                    "Acertos": acertos,
                }
            )

    res_df = pd.DataFrame(resultados)

    # Estatísticas por jogo
    resumo_jogo = (
        res_df.groupby("Jogo")["Acertos"]
        .agg(
            media_acertos="mean",
            max_acertos="max",
            min_acertos="min",
        )
        .reset_index()
    )

    # Distribuição de faixas (11 a 15)
    dist_faixas = (
        res_df.assign(
            faixa=lambda d: d["Acertos"].apply(
                lambda x: x if 11 <= x <= 15 else None
            )
        )
        .dropna(subset=["faixa"])
        .groupby(["Jogo", "faixa"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
        .rename_axis(None, axis=1)
    )

    resumo_final = pd.merge(resumo_jogo, dist_faixas, on="Jogo", how="left").fillna(0)

    # ordena por melhor desempenho médio
    resumo_final = resumo_final.sort_values("media_acertos", ascending=False).reset_index(
        drop=True
    )

    return resumo_final


def imprimir_resumo(resumo: pd.DataFrame, ultimos: int) -> None:
    print("\n========================================")
    print(f"        BACKTEST - ÚLTIMOS {ultimos} CONCURSOS")
    print("========================================\n")

    for _, row in resumo.iterrows():
        jogo_idx = int(row["Jogo"])
        media = row["media_acertos"]
        max_a = int(row["max_acertos"])
        min_a = int(row["min_acertos"])

        dist_desc = []
        for faixa in [11, 12, 13, 14, 15]:
            if faixa in resumo.columns:
                qtd = int(row.get(faixa, 0))
                if qtd > 0:
                    dist_desc.append(f"{faixa} pts: {qtd}x")

        dist_str = " | ".join(dist_desc) if dist_desc else "Nenhum jogo fez 11+ pontos."

        print(f"Jogo {jogo_idx:02d}:")
        print(f"  Média de acertos: {media:.2f}")
        print(f"  Máx / Mín: {max_a} / {min_a}")
        print(f"  Distribuição (11 a 15): {dist_str}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backtest dos jogos gerados pelo Wizard Lotofácil.\n\n"
            "Exemplo de uso:\n"
            "  python scripts/backtest.py "
            "--jogos-file outputs/jogos_agressivo_2026-01-14_16-02-08.txt "
            "--ultimos 100"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--jogos-file",
        type=str,
        required=True,
        help="Caminho para o TXT gerado pelo wizard (outputs/...).",
    )
    parser.add_argument(
        "--ultimos",
        type=int,
        default=100,
        help="Quantidade de concursos para simular (default: 100).",
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default=None,
        help="(Opcional) Caminho para salvar o resumo em CSV.",
    )

    args = parser.parse_args()

    base_df = carregar_base_limpa(BASE_LIMPA_PATH)
    jogos = parse_jogos_arquivo(Path(args.jogos_file))
    resumo = backtest_jogos(base_df, jogos, args.ultimos)

    # imprime no console
    imprimir_resumo(resumo, args.ultimos)

    # salva CSV se pedido
    if args.csv_out:
        out_path = Path(args.csv_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resumo.to_csv(out_path, index=False, float_format="%.4f")
        print(f"\n📁 Resumo salvo em: {out_path}")


if __name__ == "__main__":
    main()