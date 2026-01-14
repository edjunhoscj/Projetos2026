from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple, Set, Dict, List, Optional

import numpy as np
import pandas as pd


# =========================================
#  TIPOS E CONFIGURAÇÃO
# =========================================

@dataclass
class EstatisticasWizard:
    freq_global: pd.Series          # frequência absoluta ao longo de toda a base (1..25)
    freq_recent: pd.Series          # frequência em janela recente
    quentes: Set[int]               # dezenas mais quentes na janela recente
    frias: Set[int]                 # dezenas mais frias na janela recente


# =========================================
#  FUNÇÕES DE ESTATÍSTICA
# =========================================

def _serie_dezenas(df: pd.DataFrame) -> pd.Series:
    """
    Converte colunas D1..D15 em uma Series de dezenas (1..25) empilhadas.
    """
    col_dezenas = [c for c in df.columns if c.startswith("D")]
    dados = df[col_dezenas].values.ravel()
    return pd.Series(dados, dtype="int64")


def detectar_quentes_frias(
    df: pd.DataFrame,
    ultimos: int = 200,
    qtd_quentes: int = 8,
    qtd_frias: int = 8,
) -> EstatisticasWizard:
    """
    Calcula:
    - frequência global das dezenas (toda a base)
    - frequência recente (janela dos últimos N concursos)
    - conjuntos de dezenas quentes e frias com base na janela recente
    """
    if "Concurso" in df.columns:
        df_ordenado = df.sort_values("Concurso")
    else:
        df_ordenado = df.copy()

    # ----- Frequência global -----
    s_global = _serie_dezenas(df_ordenado)
    freq_global = s_global.value_counts().sort_index()

    # Garante índice 1..25
    freq_global = freq_global.reindex(range(1, 26), fill_value=0)

    # ----- Frequência recente -----
    if ultimos > len(df_ordenado):
        ultimos = len(df_ordenado)

    df_recent = df_ordenado.tail(ultimos)
    s_recent = _serie_dezenas(df_recent)
    freq_recent = s_recent.value_counts().sort_index()
    freq_recent = freq_recent.reindex(range(1, 26), fill_value=0)

    # ----- Quentes e frias (pela janela recente) -----
    # Ordena por frequência recente (maior -> menor)
    ordenadas = freq_recent.sort_values(ascending=False)

    quentes = set(ordenadas.head(qtd_quentes).index.tolist())
    frias = set(ordenadas.tail(qtd_frias).index.tolist())

    return EstatisticasWizard(
        freq_global=freq_global,
        freq_recent=freq_recent,
        quentes=quentes,
        frias=frias,
    )


def clusterizar_concursos(df: pd.DataFrame) -> Optional[np.ndarray]:
    """
    Placeholder simples para futura lógica de clusterização.
    Por enquanto, apenas retorna None para não depender de bibliotecas pesadas
    (sklearn, etc.) no GitHub Actions.

    Se no futuro quiser usar clusters de padrão de jogo, essa função pode
    ser expandida.
    """
    return None


# =========================================
#  SCORE INTELIGENTE DOS JOGOS
# =========================================

def calcular_score_inteligente(
    dezenas: List[int],
    ultimos_tuplas: Set[Tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    estat: EstatisticasWizard,
    config,          # WizardConfig (definido no wizard_cli)
    escolhidos: List[Tuple[int, ...]],
) -> float:
    """
    Calcula um score para o jogo combinando:

    - Cobertura: prioriza dezenas pouco usadas entre os jogos já escolhidos.
    - Frequência histórica: favorece dezenas levemente mais frequentes.
    - Quentes / Frias: bônus para quentes, penalidade para frias.
    - Similaridade com concursos recentes: penaliza jogos muito parecidos.
    - Diversidade entre os próprios jogos escolhidos: evita clones.
    """
    dezenas_set = set(dezenas)

    # ---------------------------------
    # 1) Cobertura: quero "espalhar" as dezenas
    # ---------------------------------
    cobertura_score = 0.0
    for d in dezenas:
        freq_uso = cobertura_contagem.get(d, 0)
        cobertura_score += 1.0 / (1.0 + freq_uso)

    # ---------------------------------
    # 2) Frequência histórica (freq_global normalizada)
    #    - favorece dezenas levemente acima da média
    # ---------------------------------
    freq_global = estat.freq_global
    media = freq_global.mean()
    desvio = freq_global.std(ddof=0) or 1.0

    freq_score = 0.0
    for d in dezenas:
        z = (freq_global[d] - media) / desvio
        # limito para não explodir
        z = max(min(z, 2.0), -2.0)
        freq_score += z
    freq_score *= 0.15  # peso moderado

    # ---------------------------------
    # 3) Quentes e Frias
    # ---------------------------------
    quentes = estat.quentes
    frias = estat.frias

    qtd_quentes = sum(1 for d in dezenas if d in quentes)
    qtd_frias = sum(1 for d in dezenas if d in frias)

    # ideia: queremos algumas quentes, mas não todas; e quase nada de frias
    hot_score = 0.25 * qtd_quentes - 0.20 * qtd_frias

    # ---------------------------------
    # 4) Similaridade com concursos recentes
    # ---------------------------------
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    if config.modo == "conservador":
        # conservador penaliza mais repetição
        repet_penalty = max(0, max_overlap - 9) * 1.2
    else:
        # agressivo tolera um pouco mais
        repet_penalty = max(0, max_overlap - 11) * 0.8

    # ---------------------------------
    # 5) Diversidade entre jogos escolhidos
    # ---------------------------------
    diversidade_penalty = 0.0
    for jogo in escolhidos:
        inter = len(dezenas_set.intersection(jogo))
        # acima de 12 números em comum já considero "clone"
        if inter > 12:
            diversidade_penalty += (inter - 12) * 0.5

    # ---------------------------------
    # SCORE FINAL
    # ---------------------------------
    score = (
        cobertura_score
        + freq_score
        + hot_score
        - repet_penalty
        - diversidade_penalty
    )
    return float(score)