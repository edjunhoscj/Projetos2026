from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from wizard_brain import (
    detectar_quentes_frias,
    clusterizar_concursos,
    calcular_score_inteligente,
)

print("\n========================================")
print("        BACKTEST DOS JOGOS GERADOS      ")
print("========================================")

for i, jogo in enumerate(jogos, start=1):
    acertos = backtest_jogos(jogo, df)
    print(f"Jogo {i:02d} — melhor resultado: {acertos} acertos")

# =========================================
#   CONFIGURAÇÃO DO WIZARD
# =========================================

@dataclass
class WizardConfig:
    modo: str               # "agressivo" ou "conservador"
    ultimos: int            # quantos concursos recentes comparar
    jogos_finais: int       # quantos jogos o wizard deve entregar
    max_seq_run: int = 4    # máx. de dezenas consecutivas (ex.: 4 -> 01 02 03 04)
    min_score: float = 0.0  # score mínimo para aceitar um jogo


# =========================================
#   FUNÇÕES AUXILIARES
# =========================================

def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base histórica não encontrada em: {base_path}")

    df = pd.read_excel(base_path)

    # Garantir colunas principais
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base: {faltando}")

    return df


def pegar_ultimos_concursos(df: pd.DataFrame, n: int) -> pd.DataFrame:
    # Ordena por Concurso se existir, senão usa ordem natural
    if "Concurso" in df.columns:
        df = df.sort_values("Concurso")
    return df.tail(n).reset_index(drop=True)


def respeita_sequencia_maxima(dezenas: list[int], max_seq_run: int) -> bool:
    """
    Verifica se não há mais do que `max_seq_run` dezenas consecutivas.
    Ex.: [1,2,3,4,7,...] com max_seq_run=4 OK; se tivesse 1..5 -> quebra.
    """
    dezenas = sorted(dezenas)
    run = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i - 1] + 1:
            run += 1
            if run > max_seq_run:
                return False
        else:
            run = 1
    return True


# =========================================
#   ESCOLHA DE JOGOS A PARTIR DE COMBINAÇÕES
# =========================================

def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    config: WizardConfig,
    freq: dict[int, int],
    quentes: set[int],
    frias: set[int],
    modelo_cluster,
) -> list[tuple[int, ...]]:
    """
    Lê combinacoes/combinacoes_inteligentes.csv em chunks e escolhe jogos
    conforme o modo (agressivo/conservador), priorizando:

    - evitar repetir demais os últimos concursos
    - boa cobertura de dezenas
    - respeitar limite de sequência de números consecutivos
    - usar estatísticas de quentes/frias e clusterização
    """

    modo = config.modo
    jogos_finais = config.jogos_finais
    max_seq_run = config.max_seq_run
    min_score = config.min_score

    print(f"🔍 Lendo combinações de: {comb_path}")
    print(f"Modo: {modo} | Jogos finais desejados: {jogos_finais}")

    if not comb_path.exists():
        raise FileNotFoundError(f"Arquivo de combinações não encontrado: {comb_path}")

    escolhidos: list[tuple[int, ...]] = []

    # Set com tuplas dos últimos concursos para evitar repetição exata
    ultimos_tuplas: set[tuple[int, ...]] = set()
    for _, linha in ultimos_df.iterrows():
        dezenas_ult = [int(linha[f"D{i}"]) for i in range(1, 16)]
        ultimos_tuplas.add(tuple(sorted(dezenas_ult)))

    # Cobertura: contagem de frequência das dezenas nos escolhidos até agora
    cobertura_contagem: dict[int, int] = {d: 0 for d in range(1, 26)}

    chunk_size = 20_000
    reader = pd.read_csv(comb_path, header=None, chunksize=chunk_size)

    for chunk_idx, chunk in enumerate(reader, start=1):
        print(f"  -> Processando chunk {chunk_idx} ({len(chunk)} linhas)")

        for _, row in chunk.iterrows():
            # Cada row tem UMA coluna: a string "01 02 03 ... 15"
            jogo_str = str(row.iloc[0]).strip()

            if not jogo_str:
                continue

            try:
                dezenas = [int(x) for x in jogo_str.split()]
            except ValueError:
                # Linha malformada, pula
                continue

            if len(dezenas) != 15:
                # Também não é um jogo válido
                continue

            dezenas = sorted(dezenas)
            jogo_tupla = tuple(dezenas)

            # 1) Não repetir exatamente jogos recentes
            if jogo_tupla in ultimos_tuplas:
                continue

            # 2) Checar sequência máxima de números consecutivos
            if not respeita_sequencia_maxima(dezenas, max_seq_run):
                continue

            # 3) Score inteligente (cobertura + quentes/frias + cluster etc.)
            score = calcular_score_inteligente(
                dezenas=dezenas,
                ultimos_tuplas=ultimos_tuplas,
                cobertura_contagem=cobertura_contagem,
                quentes=quentes,
                frias=frias,
                freq=freq,
                modelo_cluster=modelo_cluster,
                config=config,
                escolhidos=escolhidos,
            )

            if score < min_score:
                continue

            # 4) Atualiza cobertura
            for d in dezenas:
                cobertura_contagem[d] += 1

            escolhidos.append(jogo_tupla)

            # Critério de parada: atingimos os jogos finais desejados
            if len(escolhidos) >= jogos_finais:
                print("✅ Quantidade de jogos finais atingida.")
                return escolhidos

    print("⚠️ Atenção: fim do arquivo de combinações, "
          f"mas só conseguimos {len(escolhidos)} jogos.")
    return escolhidos


# =========================================
#   IMPRESSÃO / RESUMO FINAL
# =========================================

def imprimir_resumo(jogos: list[tuple[int, ...]], config: WizardConfig) -> None:
    print("\n========================================")
    print("        JOGOS GERADOS PELO WIZARD       ")
    print("========================================")
    print(f"Modo: {config.modo}")
    print(f"Jogos finais: {len(jogos)}\n")

    for idx, jogo in enumerate(jogos, start=1):
        seq = " ".join(f"{d:02d}" for d in jogo)
        print(f"Jogo {idx:02d}: {seq}")

    print("\nBoa sorte! 🍀")


# =========================================
#   FUNÇÃO PRINCIPAL (CLI)
# =========================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wizard Lotofácil - gera jogos filtrando combinações."
    )
    parser.add_argument(
        "--modo",
        choices=["agressivo", "conservador"],
        default="conservador",
        help="Modo de jogo (default: conservador)",
    )
    parser.add_argument(
        "--ultimos",
        type=int,
        default=20,
        help="Quantidade de concursos recentes para comparação (default: 20)",
    )
    parser.add_argument(
        "--finais",
        type=int,
        default=5,
        help="Quantidade de jogos finais desejados (default: 5)",
    )

    args = parser.parse_args()

    base_path = Path("base/base_limpa.xlsx")
    # usa as combinações inteligentes
    comb_path = Path("combinacoes/combinacoes_inteligentes.csv")

    config = WizardConfig(
        modo=args.modo,
        ultimos=args.ultimos,
        jogos_finais=args.finais,
        max_seq_run=4,
        min_score=0.0,   # se quiser filtrar mais forte, aumentar esse valor
    )

    print("========================================")
    print("     WIZARD LOTOFÁCIL - CLI")
    print("========================================")
    print(f"Base histórica: {base_path}")
    print(f"Combinações:    {comb_path}")
    print(f"Modo:           {config.modo}")
    print(f"Últimos:        {config.ultimos} concursos")
    print(f"Jogos finais:   {config.jogos_finais}")
    print("========================================\n")

    # 1) Carrega base e pega últimos concursos
    base_df = carregar_base(base_path)
    ultimos_df = pegar_ultimos_concursos(base_df, config.ultimos)

    # 2) Estatísticas quentes/frias + modelo de clusters
    estat = detectar_quentes_frias(base_df)
    freq = estat.freq
    quentes = estat.quentes
    frias = estat.frias

    modelo_cluster = clusterizar_concursos(base_df)

    # 3) Escolhe jogos
    jogos = escolher_jogos(
        comb_path,
        ultimos_df,
        config,
        freq,
        quentes,
        frias,
        modelo_cluster,
    )

    # 4) Imprime resumo
    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()