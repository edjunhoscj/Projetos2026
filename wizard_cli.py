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
    # min_score base (ajustado mais abaixo por modo)
    min_score_base: float = 6.0


# =========================================
#   FUNÇÕES AUXILIARES
# =========================================

def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base histórica não encontrada em: {base_path}")

    df = pd.read_excel(base_path)

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


def jogo_muito_parecido(
    dezenas: List[int],
    escolhidos: List[Tuple[int, ...]],
    max_intersec: int = 10,
) -> bool:
    """
    Evita jogos quase idênticos entre si.
    Se compartilhar >= max_intersec dezenas com algum já escolhido, rejeita.
    """
    set_jogo = set(dezenas)
    for j in escolhidos:
        if len(set_jogo.intersection(j)) >= max_intersec:
            return True
    return False


def bonus_equilibrio(dezenas: List[int]) -> float:
    """
    Bônus por equilíbrio entre baixas, médias e altas,
    e por diversidade geral.
    Faixa sugerida para dezenas:
      - Baixas:  1..7
      - Médias:  8..18
      - Altas:  19..25
    """

    dezenas_set = set(dezenas)
    diversidade = len(dezenas_set) / 15.0  # normalmente 1.0, mas mantém a ideia

    baixas = sum(1 for d in dezenas if 1 <= d <= 7)
    medias = sum(1 for d in dezenas if 8 <= d <= 18)
    altas  = sum(1 for d in dezenas if 19 <= d <= 25)

    # Normaliza por tamanho da faixa
    bonus_baixas = baixas / 7.0
    bonus_medias = medias / 11.0
    bonus_altas  = altas / 7.0

    # Peso maior nas médias (onde historicamente sai mais)
    return (
        0.5 * diversidade +
        0.7 * bonus_medias +
        0.4 * bonus_baixas +
        0.4 * bonus_altas
    )


# =========================================
#   ESCOLHA DE JOGOS A PARTIR DE COMBINAÇÕES
# =========================================

def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    config: WizardConfig,
    freq: Dict[int, int],
    quentes: Set[int],
    frias: Set[int],
    modelo_cluster,
) -> List[Tuple[int, ...]]:
    """
    Lê combinacoes_inteligentes.csv em chunks e escolhe jogos
    conforme o modo (agressivo/conservador), priorizando:

    - evitar repetir demais os últimos concursos
    - boa cobertura de dezenas
    - equilíbrio entre baixas/médias/altas
    - diversidade entre os próprios jogos escolhidos
    """

    modo = config.modo
    jogos_finais = config.jogos_finais
    max_seq_run = config.max_seq_run

    # min_score mais exigente para modo conservador
    min_score = (
        config.min_score_base
        if modo == "agressivo"
        else config.min_score_base + 2.0
    )

    print(f"🔍 Lendo combinações de: {comb_path}")
    print(f"Modo: {modo} | Jogos finais desejados: {jogos_finais}")
    print(f"Score mínimo base: {min_score:.2f}")

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

    # Como o arquivo inteligente geralmente é pequeno (~20k),
    # 20_000 por chunk é suficiente.
    chunk_size = 20_000
    reader = pd.read_csv(comb_path, header=None, chunksize=chunk_size)

    for chunk_idx, chunk in enumerate(reader, start=1):
        print(f"  -> Processando chunk {chunk_idx} ({len(chunk)} linhas)")

        for _, row in chunk.iterrows():
            jogo_str = str(row.iloc[0]).strip()
            if not jogo_str:
                continue

            try:
                dezenas = [int(x) for x in jogo_str.split()]
            except ValueError:
                continue

            if len(dezenas) != 15:
                continue

            dezenas = sorted(dezenas)
            jogo_tupla = tuple(dezenas)

            # 1) Não repetir exatamente jogos recentes
            if jogo_tupla in ultimos_tuplas:
                continue

            # 2) Checar sequência máxima de números consecutivos
            if not respeita_sequencia_maxima(dezenas, max_seq_run):
                continue

            # 3) Evitar jogos muito parecidos entre si
            if jogo_muito_parecido(dezenas, escolhidos, max_intersec=11):
                continue

            # 4) Score "inteligente" (wizard_brain) + bônus de equilíbrio
            score_brain = calcular_score_inteligente(
                dezenas=dezenas,
                ultimos_tuplas=ultimos_tuplas,
                cobertura_contagem=cobertura_contagem,
                quentes=quentes,
                frias=frias,
                freq=freq,
                modelo_cluster=modelo_cluster,
                modo=modo,
            )

            score_total = score_brain + bonus_equilibrio(dezenas)

            if score_total < min_score:
                continue

            # 5) Atualiza cobertura
            for d in dezenas:
                cobertura_contagem[d] += 1

            escolhidos.append(jogo_tupla)

            if len(escolhidos) >= jogos_finais:
                print("✅ Quantidade de jogos finais atingida.")
                print(f"Score mínimo efetivo aceito neste chunk: {score_total:.2f}")
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
    # usamos sempre a versão inteligente de combinações
    comb_path = Path("combinacoes/combinacoes_inteligentes.csv")

    config = WizardConfig(
        modo=args.modo,
        ultimos=args.ultimos,
        jogos_finais=args.finais,
        max_seq_run=4,
        min_score_base=6.0,
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

    # 2) Estatísticas gerais para alimentar o cérebro
    freq, quentes, frias = detectar_quentes_frias(base_df)
    modelo_cluster = clusterizar_concursos(base_df)

    # 3) Escolhe jogos
    jogos = escolher_jogos(
        comb_path=comb_path,
        ultimos_df=ultimos_df,
        config=config,
        freq=freq,
        quentes=quentes,
        frias=frias,
        modelo_cluster=modelo_cluster,
    )

    # 4) Imprime resumo
    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()