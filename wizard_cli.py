from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# Importa o "cérebro" adicional
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
    modo: str                # "agressivo" ou "conservador"
    ultimos: int             # quantos concursos recentes comparar
    jogos_finais: int        # quantos jogos o wizard deve entregar
    max_seq_run: int = 4     # máx. de dezenas consecutivas (ex.: 4 -> 01 02 03 04)
    min_score: float = 0.0   # score mínimo para aceitar um jogo

    # Diversidade entre jogos finais
    max_overlap_entre_jogos: int = 12  # máx. de dezenas em comum entre jogos finais

    # Preferência pela “cauda” (20–25)
    tail_min: int = 2        # mínimo desejado de dezenas na faixa 20–25
    tail_max: int = 5        # máximo desejado (acima disso começa a “pesar”)


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


def contar_dezenas_faixa(dezenas: Iterable[int], inicio: int, fim: int) -> int:
    """
    Conta quantas dezenas de `dezenas` estão no intervalo [inicio, fim].
    Ex.: faixa 20–25 para olhar a “cauda alta”.
    """
    return sum(1 for d in dezenas if inicio <= d <= fim)


def jogos_suficientemente_diferentes(
    candidato: tuple[int, ...],
    escolhidos: list[tuple[int, ...]],
    max_overlap: int,
) -> bool:
    """
    Garante diversidade entre jogos finais:
    - rejeita se o candidato tiver mais do que `max_overlap` dezenas em comum
      com qualquer jogo já escolhido.
    """
    cand_set = set(candidato)
    for jogo in escolhidos:
        inter = len(cand_set.intersection(jogo))
        if inter > max_overlap:
            return False
    return True


# =========================================
#   ESCOLHA DE JOGOS A PARTIR DE COMBINAÇÕES
# =========================================

def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    config: WizardConfig,
    quentes: set[int],
    frias: set[int],
    freq: dict[int, int],
    modelo_cluster,
) -> list[tuple[int, ...]]:
    """
    Lê combinacoes/combinacoes.csv em chunks e escolhe jogos
    conforme o modo (agressivo/conservador), priorizando:

    - evitar repetir demais os últimos concursos
    - boa cobertura de dezenas
    - respeitar limite de sequência de números consecutivos
    - dar preferência a dezenas da cauda (20–25) dentro de uma faixa
    - garantir diversidade entre os jogos finais
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

    chunk_size = 50_000
    reader = pd.read_csv(comb_path, header=None, chunksize=chunk_size)

    rng = np.random.default_rng()  # para embaralhar linhas dentro do chunk

    for chunk_idx, chunk in enumerate(reader, start=1):
        print(f"  -> Processando chunk {chunk_idx} ({len(chunk)} linhas)")

        # Embaralha o chunk para não ficar preso no início do CSV
        # (quebra o "vício" de sempre pegar as primeiras combinações boas)
        chunk = chunk.sample(frac=1.0, random_state=rng.integers(0, 1_000_000))

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

            # 3) Score “inteligente” vindo do wizard_brain
            score_base = calcular_score_inteligente(
                dezenas=dezenas,
                ultimos_tuplas=ultimos_tuplas,
                cobertura_contagem=cobertura_contagem,
                quentes=quentes,
                frias=frias,
                freq=freq,
                modelo_cluster=modelo_cluster,
                config=config,
                jogos_escolhidos=escolhidos,
            )

            score = float(score_base)

            # 4) Ajuste de cauda (20–25)
            qtd_tail = contar_dezenas_faixa(dezenas, 20, 25)

            # Se não tem nenhuma na cauda, penaliza forte
            if qtd_tail == 0:
                score -= 1.5
            else:
                # Faixa ideal: [tail_min, tail_max]
                if config.tail_min <= qtd_tail <= config.tail_max:
                    # bônus proporcional, mas limitado
                    score += 0.3 * qtd_tail
                elif qtd_tail > config.tail_max:
                    # muita cauda, dá um leve "peso"
                    score -= 0.2 * (qtd_tail - config.tail_max)

            # Se ainda assim o score ficar abaixo do mínimo, pula
            if score < min_score:
                continue

            # 5) Diversidade entre jogos finais
            if not jogos_suficientemente_diferentes(
                jogo_tupla,
                escolhidos,
                max_overlap=config.max_overlap_entre_jogos,
            ):
                # Candidato muito parecido com algum já escolhido
                continue

            # 6) Atualiza cobertura
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
        max_overlap_entre_jogos=12,
        tail_min=2,
        tail_max=5,
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

    # 2) Calcula inteligência extra (quentes/frias, clusters) com base completa
    print("🧠 Calculando dezenas quentes/frias e clusters...")
    quentes, frias, freq = detectar_quentes_frias(
        base_df,
        janela=200,    # janela de concursos recentes para análise de calor
        top_n=8,       # top N quentes / frias
    )
    modelo_cluster = clusterizar_concursos(
        base_df,
        n_clusters=5,  # número de clusters pra agrupar padrões de sorteios
    )

    # 3) Escolhe jogos
    jogos = escolher_jogos(
        comb_path=comb_path,
        ultimos_df=ultimos_df,
        config=config,
        quentes=quentes,
        frias=frias,
        freq=freq,
        modelo_cluster=modelo_cluster,
    )

    # 4) Imprime resumo
    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()