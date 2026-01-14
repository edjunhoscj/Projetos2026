from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# =========================================
#   CONFIGURAÇÃO DO WIZARD
# =========================================

@dataclass
class WizardConfig:
    modo: str               # "agressivo" ou "conservador"
    ultimos: int            # quantos concursos recentes comparar
    jogos_finais: int       # quantos jogos o wizard deve entregar
    max_seq_run: int = 4    # máx. de dezenas consecutivas
    min_score: float = 0.0  # score mínimo para aceitar um jogo


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
    if "Concurso" in df.columns:
        df = df.sort_values("Concurso")
    return df.tail(n).reset_index(drop=True)


def respeita_sequencia_maxima(dezenas: list[int], max_seq_run: int) -> bool:
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


def calcular_score_jogo(
    dezenas: list[int],
    ultimos_tuplas: set[tuple[int, ...]],
    cobertura_contagem: dict[int, int],
    modo: str,
) -> float:
    """
    Score combinando:
    - Cobertura (preferir dezenas menos usadas nos jogos já escolhidos)
    - Penalizar jogos muito parecidos com concursos recentes
    """
    dezenas_set = set(dezenas)

    # 1) Cobertura
    cobertura_score = 0.0
    for d in dezenas:
        freq = cobertura_contagem.get(d, 0)
        cobertura_score += 1.0 / (1.0 + freq)

    # 2) Penalização por semelhança com últimos concursos
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    if modo == "conservador":
        penalidade = max(0, max_overlap - 9)   # mais rígido
    else:
        penalidade = max(0, max_overlap - 11)  # agressivo aceita mais repetição

    score = cobertura_score - penalidade
    return score


# =========================================
#   ESCOLHA DE JOGOS A PARTIR DE COMBINAÇÕES
# =========================================

def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    config: WizardConfig,
) -> list[tuple[int, ...]]:
    """
    Lê combinacoes/combinacoes.csv (já inteligente) e escolhe
    jogos finais aplicando mais filtros e cobertura.
    """

    modo = config.modo
    jogos_finais = config.jogos_finais
    max_seq_run = config.max_seq_run
    min_score = config.min_score

    print(f"🔍 Lendo combinações de: {comb_path}")
    print(f"Modo: {modo} | Jogos finais desejados: {jogos_finais}")

    if not comb_path.exists():
        raise FileNotFoundError(f"Arquivo de combinações não encontrado: {comb_path}")

    # Lê tudo em memória (arquivo reduzido: ~15k linhas)
    comb_df = pd.read_csv(comb_path)

    col_dezenas = [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in col_dezenas if c not in comb_df.columns]
    if faltando:
        raise ValueError(f"Colunas D1..D15 faltando em {comb_path}: {faltando}")

    # Embaralha para dar variedade
    comb_df = comb_df.sample(frac=1.0, random_state=None).reset_index(drop=True)

    escolhidos: list[tuple[int, ...]] = []

    # Set de tuplas dos últimos concursos
    ultimos_tuplas: set[tuple[int, ...]] = set()
    for _, linha in ultimos_df.iterrows():
        dezenas_ult = [int(linha[f"D{i}"]) for i in range(1, 16)]
        ultimos_tuplas.add(tuple(sorted(dezenas_ult)))

    # Cobertura: contagem de frequência das dezenas nos escolhidos até agora
    cobertura_contagem: dict[int, int] = {d: 0 for d in range(1, 26)}

    for _, row in comb_df.iterrows():
        dezenas = [int(row[c]) for c in col_dezenas]
        dezenas = sorted(dezenas)
        jogo_tupla = tuple(dezenas)

        # 1) Não repetir exatamente concursos recentes
        if jogo_tupla in ultimos_tuplas:
            continue

        # 2) Sequência máxima
        if not respeita_sequencia_maxima(dezenas, max_seq_run):
            continue

        # 3) Score de cobertura + semelhança
        score = calcular_score_jogo(
            dezenas,
            ultimos_tuplas,
            cobertura_contagem,
            modo=modo,
        )

        if score < min_score:
            continue

        # 4) Atualiza cobertura
        for d in dezenas:
            cobertura_contagem[d] += 1

        escolhidos.append(jogo_tupla)

        if len(escolhidos) >= jogos_finais:
            print("✅ Quantidade de jogos finais atingida.")
            return escolhidos

    print("⚠️ Atenção: fim das combinações, "
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
        description="Wizard Lotofácil - gera jogos filtrando combinações inteligentes."
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
    comb_path = Path("combinacoes/combinacoes.csv")

    config = WizardConfig(
        modo=args.modo,
        ultimos=args.ultimos,
        jogos_finais=args.finais,
        max_seq_run=4,
        min_score=0.0,
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

    base_df = carregar_base(base_path)
    ultimos_df = pegar_ultimos_concursos(base_df, config.ultimos)

    jogos = escolher_jogos(comb_path, ultimos_df, config)

    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()