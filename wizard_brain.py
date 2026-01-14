from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple, Any

import numpy as np
import pandas as pd


# =========================================
#   MODELO SIMPLES DE "CLUSTERS"
# =========================================

@dataclass
class ClusterModel:
    """
    Modelo bem leve só para dar contexto estatístico aos jogos.

    - media_global: frequência média (0..1) de cada dezena (1..25) em toda a base
    - media_recentes: frequência média nas últimas N dezenas
    """
    media_global: np.ndarray  # shape (25,)
    media_recentes: np.ndarray  # shape (25,)


# =========================================
#   HELPERS
# =========================================

def _df_para_matriz_binaria(df: pd.DataFrame) -> np.ndarray:
    """
    Converte a base em uma matriz binária (n_concursos x 25),
    onde cada linha é um concurso e cada coluna indica se a dezena 1..25 saiu (1) ou não (0).
    """
    n = len(df)
    mat = np.zeros((n, 25), dtype=np.float32)

    cols_dezenas = [f"D{i}" for i in range(1, 16)]

    for idx, row in df[cols_dezenas].iterrows():
        for d in row.values:
            if 1 <= int(d) <= 25:
                mat[idx, int(d) - 1] = 1.0

    return mat


# =========================================
#   QUENTES / FRIAS
# =========================================

def detectar_quentes_frias(
    df: pd.DataFrame,
    n_ultimos: int = 200,
    top_k: int = 8,
) -> Tuple[Set[int], Set[int], Dict[int, int]]:
    """
    Analisa os últimos N concursos e devolve:
      - quentes: dezenas mais frequentes
      - frias: dezenas menos frequentes
      - freq: dict com contagem absoluta em N concursos
    """

    if len(df) == 0:
        return set(), set(), {d: 0 for d in range(1, 26)}

    # Garante que n_ultimos não passe do tamanho da base
    fatia = df.tail(min(n_ultimos, len(df)))

    contagem = {d: 0 for d in range(1, 26)}
    cols_dezenas = [f"D{i}" for i in range(1, 16)]

    for _, row in fatia[cols_dezenas].iterrows():
        for d in row.values:
            d_int = int(d)
            if 1 <= d_int <= 25:
                contagem[d_int] += 1

    # Ordena por frequência
    ordenado = sorted(contagem.items(), key=lambda x: x[1], reverse=True)
    # top_k mais quentes
    quentes = {d for d, _ in ordenado[:top_k]}
    # top_k mais frias (do fim)
    frias = {d for d, _ in ordenado[-top_k:]}

    return quentes, frias, contagem


# =========================================
#   "CLUSTERIZAÇÃO" (RESUMO ESTATÍSTICO)
# =========================================

def clusterizar_concursos(
    df: pd.DataFrame,
    n_ultimos: int = 200,
) -> ClusterModel:
    """
    NÃO usa sklearn (para ficar leve no GitHub Actions).
    Apenas calcula vetores médios (global e recentes) em espaço 25D,
    representando o "estilo" médio dos concursos.
    """

    if len(df) == 0:
        media_zero = np.zeros(25, dtype=np.float32)
        return ClusterModel(media_global=media_zero, media_recentes=media_zero)

    mat = _df_para_matriz_binaria(df)
    media_global = mat.mean(axis=0)

    # Últimos N concursos
    mat_recent = mat[-min(n_ultimos, len(df)) :, :]
    media_recentes = mat_recent.mean(axis=0)

    return ClusterModel(
        media_global=media_global.astype(np.float32),
        media_recentes=media_recentes.astype(np.float32),
    )


# =========================================
#   SCORE INTELIGENTE
# =========================================

def _cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def calcular_score_inteligente(
    dezenas: Sequence[int],
    ultimos_tuplas: Set[Tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    quentes: Set[int],
    frias: Set[int],
    freq: Dict[int, int],
    modelo_cluster: ClusterModel,
    config: Any,  # WizardConfig (evita import circular)
    escolhidos: List[Tuple[int, ...]],
) -> float:
    """
    Heurística de score:

    1) Cobertura: prioriza dezenas pouco usadas nos jogos já escolhidos
    2) Quentes/Frias:
       - agressivo: puxa mais quentes, evita frias
       - conservador: busca equilíbrio entre quentes/frias
    3) Distância dos últimos concursos (não ser cópia)
    4) Similaridade com "estilo" médio recente (cluster)
    5) Diversidade entre os próprios jogos escolhidos
    """

    dezenas = sorted(int(d) for d in dezenas)
    dezenas_set = set(dezenas)

    # -------------------------
    # 1) Cobertura
    # -------------------------
    cobertura_score = 0.0
    for d in dezenas:
        freq_d = cobertura_contagem.get(d, 0)
        # quanto menos apareceu nos jogos ESCOLHIDOS até agora, maior o ganho
        cobertura_score += 1.0 / (1.0 + freq_d)

    # -------------------------
    # 2) Quentes / Frias
    # -------------------------
    qtd_quentes = len(dezenas_set & quentes)
    qtd_frias = len(dezenas_set & frias)

    if getattr(config, "modo", "conservador") == "agressivo":
        # agressivo: quer puxar mais as dezenas quentes
        bonus_quentes = 0.40 * qtd_quentes
        penal_frias = 0.25 * qtd_frias
        hf_score = bonus_quentes - penal_frias
    else:
        # conservador: busca equilíbrio (nem poucas, nem muitas quentes)
        # alvo: entre 5 e 9 quentes
        alvo_min, alvo_max = 5, 9
        if qtd_quentes < alvo_min:
            desvio = alvo_min - qtd_quentes
        elif qtd_quentes > alvo_max:
            desvio = qtd_quentes - alvo_max
        else:
            desvio = 0
        hf_score = 2.0 - 0.4 * desvio - 0.1 * qtd_frias  # começa de 2 e vai caindo

    # -------------------------
    # 3) Sobreposição com últimos concursos
    # -------------------------
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    if getattr(config, "modo", "conservador") == "conservador":
        # conservador: penaliza se sobrepõe demais (>= 11 repetidas)
        penal_ultimos = max(0, max_overlap - 10) * 0.8
    else:
        # agressivo: aceita mais sobreposição, só pesa se ficar muito alto
        penal_ultimos = max(0, max_overlap - 12) * 0.5

    # -------------------------
    # 4) Similaridade com estilo médio (clusters)
    # -------------------------
    jogo_vec = np.zeros(25, dtype=np.float32)
    for d in dezenas:
        if 1 <= d <= 25:
            jogo_vec[d - 1] = 1.0

    cos_recent = _cos_sim(jogo_vec, modelo_cluster.media_recentes)
    # Em geral cos_recent fica entre ~0.35 e ~0.85

    if getattr(config, "modo", "conservador") == "conservador":
        # conservador quer um jogo parecido, mas não idêntico
        # alvo de similaridade ~0.7
        cluster_score = 1.5 - abs(cos_recent - 0.7) * 3.0
    else:
        # agressivo quer surfar forte a tendência recente
        cluster_score = cos_recent * 2.5  # [0..2.5 aprox]

    # -------------------------
    # 5) Diversidade entre os jogos escolhidos
    # -------------------------
    penal_diversidade = 0.0
    for j in escolhidos:
        inter = len(dezenas_set.intersection(set(j)))
        if inter >= 13:
            penal_diversidade += (inter - 12) * 0.7
        elif inter >= 11:
            penal_diversidade += (inter - 10) * 0.3

    # -------------------------
    # Score final
    # -------------------------
    score_final = (
        cobertura_score      # cobertura
        + hf_score           # quentes/frias
        + cluster_score      # estilo médio
        - penal_ultimos      # muito colado nos últimos sorteios
        - penal_diversidade  # muito parecido com outros jogos do próprio wizard
    )

    return float(score_final)