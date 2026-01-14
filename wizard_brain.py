from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd


# -----------------------------------------
# Config extra do Wizard (aproveitada pelo CLI)
# -----------------------------------------

@dataclass
class BrainConfig:
    """
    Parâmetros finos usados no cálculo do score.
    Você pode ajustar pesos aqui se quiser "afinar" o comportamento.
    """
    # pesos dos componentes
    peso_cobertura: float = 1.0
    peso_quentes: float = 0.8
    peso_frias: float = 0.3
    peso_bonus_20_25: float = 0.6

    # penalidades
    penalidade_base_conservador: float = 1.0
    penalidade_base_agressivo: float = 0.5

    # diversidade
    min_diferenca_entre_jogos: int = 3   # mínimo de dezenas diferentes entre dois jogos finais
    penalidade_diversidade: float = 0.7  # o quanto "pesa" ficar muito parecido com jogos já escolhidos


# -----------------------------------------
# 1) Detecção de dezenas quentes / frias
# -----------------------------------------

def detectar_quentes_frias(
    df: pd.DataFrame,
    janela: int = 200,
    top_n: int = 10,
    bottom_n: int = 10,
) -> tuple[Set[int], Set[int], Dict[int, int]]:
    """
    Olha apenas os últimos `janela` concursos e calcula:
      - quentes: dezenas mais frequentes
      - frias: dezenas menos frequentes
      - freq: dict {dezena -> frequência absoluta}

    Retorna (quentes, frias, freq).
    """
    if len(df) == 0:
        return set(), set(), {}

    ultimos_df = df.tail(janela)

    dezenas_cols = [c for c in ultimos_df.columns if c.startswith("D")]
    valores = ultimos_df[dezenas_cols].values.ravel()

    # garante inteiros 1..25
    valores = pd.Series(valores).astype(int)
    contagem = valores.value_counts().sort_values(ascending=False)

    freq = {int(k): int(v) for k, v in contagem.items()}

    quentes = set(contagem.head(top_n).index.astype(int))
    frias = set(contagem.tail(bottom_n).index.astype(int))

    return quentes, frias, freq


# -----------------------------------------
# 2) "Clusterização" simples dos concursos
# -----------------------------------------

def clusterizar_concursos(df: pd.DataFrame) -> Dict[Tuple[int, ...], int]:
    """
    Cria clusters bem simples com base na SOMA das dezenas de cada concurso.

    - soma baixa  -> cluster 0
    - soma média  -> cluster 1
    - soma alta   -> cluster 2

    Retorna um dicionário: {tupla_dezenas_ordenadas -> id_do_cluster}
    """
    if len(df) == 0:
        return {}

    dezenas_cols = [c for c in df.columns if c.startswith("D")]

    somas = df[dezenas_cols].sum(axis=1).values
    q1, q2 = np.quantile(somas, [0.33, 0.66])

    clusters: Dict[Tuple[int, ...], int] = {}

    for _, row in df.iterrows():
        dezenas = tuple(sorted(int(row[c]) for c in dezenas_cols))
        s = sum(dezenas)
        if s <= q1:
            c_id = 0
        elif s <= q2:
            c_id = 1
        else:
            c_id = 2
        clusters[dezenas] = c_id

    return clusters


# -----------------------------------------
# 3) Cálculo do score inteligente
# -----------------------------------------

def _cluster_de_um_jogo(
    dezenas: Sequence[int],
    clusters_existentes: Dict[Tuple[int, ...], int],
) -> int | None:
    """
    Tenta achar o cluster de um jogo com base na soma.
    Se não existir na base, aproxima pela soma vs quantis.
    (fallback simples para não quebrar o fluxo).
    """
    t = tuple(sorted(dezenas))
    if t in clusters_existentes:
        return clusters_existentes[t]

    # aproxima pelo mesmo critério da criação
    somas = np.array([sum(k) for k in clusters_existentes.keys()])
    if len(somas) == 0:
        return None
    q1, q2 = np.quantile(somas, [0.33, 0.66])
    s = sum(dezenas)
    if s <= q1:
        return 0
    elif s <= q2:
        return 1
    else:
        return 2


def calcular_score_inteligente(
    dezenas: list[int],
    ultimos_tuplas: Set[Tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    quentes: Set[int],
    frias: Set[int],
    freq: Dict[int, int],
    clusters: Dict[Tuple[int, ...], int],
    config_wizard,        # WizardConfig (do CLI)
    brain_cfg: BrainConfig,
    escolhidos: List[Tuple[int, ...]],
) -> float:
    """
    Calcula um score combinando:
      - cobertura de dezenas (preferir números ainda pouco usados nos jogos escolhidos)
      - proximidade dos últimos concursos (penaliza jogos muito parecidos)
      - bônus para dezenas quentes
      - leve bônus para dezenas frias (busca equilíbrio)
      - bônus específico para dezenas 20..25
      - diversidade entre jogos finais
      - distribuição de clusters (evitar todos os jogos no mesmo "tipo")
    """

    dezenas_set = set(dezenas)

    # 1) Cobertura: 1 / (1 + freq_escolhidos_ate_agora)
    cobertura_score = 0.0
    for d in dezenas:
        freq_escolhida = cobertura_contagem.get(d, 0)
        cobertura_score += 1.0 / (1.0 + freq_escolhida)

    # 2) Semelhança com últimos concursos
    max_overlap_ultimos = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(ult))
        if inter > max_overlap_ultimos:
            max_overlap_ultimos = inter

    if config_wizard.modo == "conservador":
        base_pen = brain_cfg.penalidade_base_conservador
        limite = 9  # acima disso começa a pesar forte
    else:
        base_pen = brain_cfg.penalidade_base_agressivo
        limite = 11

    penalidade_ultimos = base_pen * max(0, max_overlap_ultimos - limite)

    # 3) Bônus quentes / frias
    qtd_quentes = len([d for d in dezenas if d in quentes])
    qtd_frias = len([d for d in dezenas if d in frias])

    bonus_quentes = brain_cfg.peso_quentes * (qtd_quentes / len(dezenas))
    bonus_frias = brain_cfg.peso_frias * (qtd_frias / len(dezenas))

    # 4) Bônus para dezenas 20..25
    qtd_20_25 = len([d for d in dezenas if d >= 20])
    bonus_20_25 = brain_cfg.peso_bonus_20_25 * (qtd_20_25 / len(dezenas))

    # 5) Diversidade entre jogos finais já escolhidos
    penalidade_diversidade_total = 0.0
    for j in escolhidos:
        inter = len(dezenas_set.intersection(j))
        diferencas = len(dezenas) - inter
        if diferencas < brain_cfg.min_diferenca_entre_jogos:
            # jogo muito parecido → penaliza forte
            penalidade_diversidade_total += brain_cfg.penalidade_diversidade

    # 6) Cluster: evita todos no mesmo tipo
    cluster_atual = _cluster_de_um_jogo(dezenas, clusters)
    penalidade_cluster = 0.0
    if cluster_atual is not None and escolhidos:
        clusters_escolhidos = [
            _cluster_de_um_jogo(list(j), clusters) for j in escolhidos
        ]
        clusters_escolhidos = [c for c in clusters_escolhidos if c is not None]
        if clusters_escolhidos:
            proporcao_mesmo = sum(
                1 for c in clusters_escolhidos if c == cluster_atual
            ) / len(clusters_escolhidos)
            # se já tem muitos no mesmo cluster, desincentiva um pouco
            penalidade_cluster = 0.5 * proporcao_mesmo

    # Score final
    score = (
        brain_cfg.peso_cobertura * cobertura_score
        + bonus_quentes
        + bonus_frias
        + bonus_20_25
        - penalidade_ultimos
        - penalidade_diversidade_total
        - penalidade_cluster
    )

    return float(score)