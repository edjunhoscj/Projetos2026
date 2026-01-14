from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Set, Dict

import pandas as pd

from wizard_brain import (
    detectar_quentes_frias,
    clusterizar_concursos,
    calcular_score_inteligente,
    EstatisticasWizard,
)


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


def respeita_sequencia_maxima(dezenas: List[int], max_seq_run: int) -> bool:
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


def conta_blocos(dezenas: List[int]) -> Tuple[int, int, int]:
    """
    Conta quantas dezenas caem em cada bloco:
    - bloco1: 1..9
    - bloco2: 10..19
    - bloco3: 20..25
    """
    b1 = sum(1 for d in dezenas if 1 <= d <= 9)
    b2 = sum(1 for d in dezenas if 10 <= d <= 19)
    b3 = sum(1 for d in dezenas if 20 <= d <= 25)
    return b1, b2, b3


def conta_pares(dezenas: List[int]) -> int:
    return sum(1 for d in dezenas if d % 2 == 0)


# =========================================
#   ESCOLHA DE JOGOS A PARTIR DE COMBINAÇÕES
# =========================================

def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    config: WizardConfig,
    estat: EstatisticasWizard,
) -> List[Tuple[int, ...]]:
    """
    Lê combinacoes/combinacoes.csv em chunks e escolhe jogos
    conforme o modo (agressivo/conservador), priorizando:

    - evitar repetir demais os últimos concursos
    - boa cobertura de dezenas
    - respeitar limite de sequência de números consecutivos
    - respeitar blocos 1–9 / 10–19 / 20–25
    - respeitar faixa de pares/ímpares
    - incentivar dezenas quentes e evitar frias
    - manter diversidade entre os próprios jogos gerados
    """

    modo = config.modo
    jogos_finais = config.jogos_finais
    max_seq_run = config.max_seq_run
    min_score = config.min_score

    print(f"🔍 Lendo combinações de: {comb_path}")
    print(f"Modo: {modo} | Jogos finais desejados: {jogos_finais}")

    if not comb_path.exists():
        raise FileNotFoundError(f"Arquivo de combinações não encontrado: {comb_path}")

    escolhidos: List[Tuple[int, ...]] = []

    # Set com tuplas dos últimos concursos para evitar repetição exata
    ultimos_tuplas: Set[Tuple[int, ...]] = set()
    for _, linha in ultimos_df.iterrows():
        dezenas_ult = [int(linha[f"D{i}"]) for i in range(1, 16)]
        ultimos_tuplas.add(tuple(sorted(dezenas_ult)))

    # Cobertura: contagem de frequência das dezenas nos escolhidos até agora
    cobertura_contagem: Dict[int, int] = {d: 0 for d in range(1, 26)}

    chunk_size = 50_000
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

            # 3) Controle de blocos (1–9 / 10–19 / 20–25)
            b1, b2, b3 = conta_blocos(dezenas)
            # faixa típica observada na análise real
            if not (6 <= b1 <= 8):
                continue
            if not (4 <= b2 <= 6):
                continue
            if not (3 <= b3 <= 5):
                continue

            # 4) Controle de pares
            qtd_pares = conta_pares(dezenas)
            if not (6 <= qtd_pares <= 9):
                continue

            # 5) Similaridade dura com últimos concursos:
            #    não aceitar jogos com muita repetição
            dezenas_set = set(dezenas)
            max_overlap = 0
            for ult in ultimos_tuplas:
                inter = len(dezenas_set.intersection(ult))
                if inter > max_overlap:
                    max_overlap = inter
            # limite bruto (acima disso nem calcula score)
            if max_overlap > 13:
                continue

            # 6) Score inteligente combinando tudo
            score = calcular_score_inteligente(
                dezenas,
                ultimos_tuplas,
                cobertura_contagem,
                estat,
                config,
                escolhidos,
            )

            if score < min_score:
                continue

            # 7) Atualiza cobertura
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

def imprimir_resumo(jogos: List[Tuple[int, ...]], config: WizardConfig) -> None:
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
        default=10,
        help="Quantidade de concursos recentes para comparação (default: 10)",
    )
    parser.add_argument(
        "--finais",
        type=int,
        default=5,
        help="Quantidade de jogos finais desejados (default: 5)",
    )

    args = parser.parse_args()

    base_path = Path("base/base_limpa.xlsx")
    comb_path = Path("combinacoes/combinacoes.csv")

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

    # 2) Estatísticas (quentes/frias, frequências, etc.)
    estat = detectar_quentes_frias(base_df, ultimos=200)
    _ = clusterizar_concursos(base_df)  # por enquanto não usado, mas deixa pronto

    # 3) Escolhe jogos
    jogos = escolher_jogos(comb_path, ultimos_df, config, estat)

    # 4) Imprime resumo
    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()