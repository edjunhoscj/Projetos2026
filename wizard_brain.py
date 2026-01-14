from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Iterable

import numpy as np
import pandas as pd


DEZENAS_POSSIVEIS = list(range(1, 26))
COL_DEZENAS = [f"D{i}" for i in range(1, 16)]


# =====================================================
#  MODELO DE ESTATÍSTICAS USADO PELO WIZARD
# =====================================================

@dataclass
class EstatisticasWizard:
    """
    Objeto-resumo com tudo que o Wizard precisa saber da base.
    """
    # frequência absoluta de cada dezena na janela analisada
    freq: Dict[int, int]

    # dezenas mais quentes (acima do percentil 75)
    quentes: List[int]

    # dezenas mais frias (abaixo do percentil 25)
    frias: List[int]

    # probabilidade P(número | posição 1..15)
    prob_posicao: Dict[int, Dict[int, float]]


# =====================================================
#  CÁLCULOS DE ESTATÍSTICA BÁSICA
# =====================================================

def _contar_frequencias(df: pd.DataFrame) -> Dict[int, int]:
    """Conta quantas vezes cada dezena aparece nas colunas D1..D15."""
    freq = {d: 0 for d in DEZENAS_POSSIVEIS}
    for col in COL_DEZENAS:
        contagem = df[col].value_counts()
        for dezena, qtde in contagem.items():
            d = int(dezena)
            if d in freq:
                freq[d] += int(qtde)
    return freq


def _calcular_quentes_frias(freq: Dict[int, int]) -> Tuple[List[int], List[int]]:
    """
    Define dezenas quentes e frias usando quartis (Q1 e Q3).
    """
    valores = np.array(list(freq.values()), dtype=float)

    q1 = np.percentile(valores, 25)
    q3 = np.percentile(valores, 75)

    quentes = [d for d, f in freq.items() if f >= q3]
    frias = [d for d, f in freq.items() if f <= q1]

    # Só por segurança: ordena
    quentes.sort()
    frias.sort()

    return quentes, frias


def _probabilidade_por_posicao(df: pd.DataFrame) -> Dict[int, Dict[int, float]]:
    """
    Para cada posição (coluna D1..D15) calcula a probabilidade de
    cada dezena aparecer naquela posição.
    """
    prob_posicao: Dict[int, Dict[int, float]] = {}

    for idx, col in enumerate(COL_DEZENAS, start=1):
        contagem = df[col].value_counts()
        total = contagem.sum()
        if total == 0:
            prob_posicao[idx] = {d: 0.0 for d in DEZENAS_POSSIVEIS}
            continue

        probs_col = {}
        for d in DEZENAS_POSSIVEIS:
            probs_col[d] = float(contagem.get(d, 0)) / float(total)
        prob_posicao[idx] = probs_col

    return prob_posicao


def detectar_quentes_frias(
    base_df: pd.DataFrame,
    janela: int | None = None,
) -> EstatisticasWizard:
    """
    Recebe a base limpa completa e devolve um EstatisticasWizard.

    - janela: se informado, usa apenas os últimos N concursos;
      se None, usa a base inteira.
    """
    if janela is not None and janela > 0 and len(base_df) > janela:
        df = base_df.tail(janela).reset_index(drop=True)
    else:
        df = base_df.copy()

    # garante que só trabalhamos com as colunas D1..D15
    for col in COL_DEZENAS:
        if col not in df.columns:
            raise ValueError(f"Coluna '{col}' não encontrada na base limpa.")

    freq = _contar_frequencias(df)
    quentes, frias = _calcular_quentes_frias(freq)
    prob_posicao = _probabilidade_por_posicao(df)

    return EstatisticasWizard(
        freq=freq,
        quentes=quentes,
        frias=frias,
        prob_posicao=prob_posicao,
    )


# =====================================================
#  (OPCIONAL) CLUSTERIZAÇÃO – VERSÃO LEVE
# =====================================================

def clusterizar_concursos(base_df: pd.DataFrame) -> None:
    """
    Placeholder de clusterização. Para não criar dependência de scikit-learn
    no GitHub Actions, por enquanto não usamos cluster real.

    Mantive a função para não quebrar imports no wizard_cli.py.
    Quando quiser, dá pra trocar essa função por um KMeans de verdade.
    """
    return None


# =====================================================
#  SCORE INTELIGENTE DOS JOGOS
# =====================================================

def calcular_score_inteligente(
    dezenas: Iterable[int],
    ultimos_tuplas: set[tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    quentes: List[int],
    frias: List[int],
    freq: Dict[int, int],   # alinhado com o wizard_cli
    modelo_cluster,         # não usado por enquanto (placeholder)
    config,                 # WizardConfig (tem modo, etc.)
    escolhidos,   # <<< mantenha esse nome
) -> float:
    """
    Versão "inteligente" do score, combinando:
      - Cobertura (como antes)
      - Bônus por dezenas quentes
      - Pequeno bônus por usar algumas frias
      - Penalização por parecer demais com concursos recentes
      - Penalização por parecer demais com jogos já escolhidos
    """

    dezenas = sorted(int(d) for d in dezenas)
    dezenas_set = set(dezenas)

    # 1) Cobertura (igual ideia antiga)
    cobertura_score = 0.0
    for d in dezenas:
        freq_usada = cobertura_contagem.get(d, 0)
        cobertura_score += 1.0 / (1.0 + freq_usada)

    # 2) Bônus por dezenas quentes
    qtde_quentes = sum(1 for d in dezenas if d in quentes)
    bonus_quentes = qtde_quentes / 15.0  # entre 0 e 1

    # 3) Pequeno bônus se usar algumas frias (diversificação)
    qtde_frias = sum(1 for d in dezenas if d in frias)
    bonus_frias = (qtde_frias / 15.0) * 0.3  # peso menor

    # 4) Penalização por semelhança com concursos recentes
    max_overlap_ultimos = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(ult))
        if inter > max_overlap_ultimos:
            max_overlap_ultimos = inter

    if config.modo == "conservador":
        penal_ultimos = max(0, max_overlap_ultimos - 10) * 0.8
    else:
        # agressivo tolera mais repetição
        penal_ultimos = max(0, max_overlap_ultimos - 12) * 0.5

    # 5) Penalização por ficar muito parecido com jogos já escolhidos
    max_overlap_escolhidos = 0
    for jogo in escolhidos:
        inter = len(dezenas_set.intersection(jogo))
        if inter > max_overlap_escolhidos:
            max_overlap_escolhidos = inter
    penal_escolhidos = max(0, max_overlap_escolhidos - 10) * 0.7

    score = (
        cobertura_score
        + bonus_quentes
        + bonus_frias
        - penal_ultimos
        - penal_escolhidos
    )

    return float(score)