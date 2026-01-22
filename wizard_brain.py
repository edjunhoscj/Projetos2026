# wizard_brain.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd


# ============================================================
#   SAÍDAS / TIPOS
# ============================================================

@dataclass(frozen=True)
class Estatisticas:
    freq: Dict[int, float]
    quentes: Set[int]
    frias: Set[int]
    freq_media: float


@dataclass(frozen=True)
class DiversidadeConfig:
    peso_overlap: float = 1.2
    peso_jaccard: float = 6.0
    peso_cobertura: float = 0.8
    peso_separacao_modo: float = 0.15
    overlap_alvo_max: int = 11
    reforco_overlap_extra: float = 1.8


PRESET_SOLO = DiversidadeConfig(
    peso_overlap=0.6,
    peso_jaccard=3.0,
    peso_cobertura=0.25,
    peso_separacao_modo=0.12,
    overlap_alvo_max=12,
    reforco_overlap_extra=1.4,
)

PRESET_COBERTURA = DiversidadeConfig(
    peso_overlap=1.3,
    peso_jaccard=7.0,
    peso_cobertura=1.0,
    peso_separacao_modo=0.18,
    overlap_alvo_max=10,
    reforco_overlap_extra=2.0,
)


# ============================================================
#   HELPERS
# ============================================================

def _to_set(dezenas: Iterable[int]) -> Set[int]:
    return set(int(x) for x in dezenas)


def _jaccard(a: Set[int], b: Set[int]) -> float:
    inter = len(a & b)
    uni = len(a | b)
    return (inter / uni) if uni else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _normalizar_0_1(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _extrair_dezenas_df(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    return df[cols].to_numpy(dtype=int, copy=True)


def _binvec_25(dezenas15: Sequence[int]) -> np.ndarray:
    v = np.zeros(25, dtype=np.int8)
    for d in dezenas15:
        d = int(d)
        if 1 <= d <= 25:
            v[d - 1] = 1
    return v


# ============================================================
#   QUENTES/FRIAS
# ============================================================

def detectar_quentes_frias(
    base_df: pd.DataFrame,
    ultimos: int = 200,
    top_quentes: int = 7,
    top_frias: int = 7,
) -> Estatisticas:
    if "Concurso" in base_df.columns:
        base_df = base_df.sort_values("Concurso")

    df = base_df.tail(int(ultimos)).reset_index(drop=True)
    arr = _extrair_dezenas_df(df)

    cont = {d: 0 for d in range(1, 26)}
    for row in arr:
        for d in row:
            d = int(d)
            if 1 <= d <= 25:
                cont[d] += 1

    total_concursos = max(1, len(df))
    freq = {d: cont[d] / total_concursos for d in range(1, 26)}
    freq_media = float(_mean(list(freq.values())))

    ordenado = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    quentes = set(d for d, _ in ordenado[:int(top_quentes)])

    ordenado_f = sorted(freq.items(), key=lambda kv: kv[1])
    frias = set(d for d, _ in ordenado_f[:int(top_frias)])

    return Estatisticas(freq=freq, quentes=quentes, frias=frias, freq_media=freq_media)


# ============================================================
#   CLUSTER (opcional)
# ============================================================

@dataclass
class ClusterModel:
    kmeans: Optional[object] = None
    n_clusters: int = 0


def clusterizar_concursos(
    base_df: pd.DataFrame,
    n_clusters: int = 8,
    ultimos: int = 600,
    random_state: int = 42,
) -> ClusterModel:
    try:
        from sklearn.cluster import KMeans  # type: ignore
    except Exception:
        return ClusterModel(kmeans=None, n_clusters=0)

    if "Concurso" in base_df.columns:
        base_df = base_df.sort_values("Concurso")

    df = base_df.tail(int(ultimos)).reset_index(drop=True)
    arr = _extrair_dezenas_df(df)
    X = np.stack([_binvec_25(row) for row in arr], axis=0)

    n_clusters = int(max(2, min(n_clusters, len(df) // 10 if len(df) >= 20 else 2)))

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    km.fit(X)

    return ClusterModel(kmeans=km, n_clusters=n_clusters)


# ============================================================
#   SCORE INTELIGENTE (compatível com seu CLI)
# ============================================================

def calcular_score_inteligente(
    dezenas: Sequence[int],
    ultimos_tuplas: Set[Tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    quentes: Set[int],
    frias: Set[int],
    freq: Dict[int, float],
    modelo_cluster: ClusterModel,
    config,
    escolhidos: List[Tuple[int, ...]],
) -> float:
    jogo = sorted(int(x) for x in dezenas)
    jogo_set = set(jogo)
    modo = str(getattr(config, "modo", "conservador")).lower()

    # -------------------------
    # SCORE BASE
    # -------------------------
    cobertura_score = 0.0
    for d in jogo:
        freq_local = float(cobertura_contagem.get(d, 0))
        cobertura_score += 1.0 / (1.0 + freq_local)

    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(jogo_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    if modo.startswith("agre"):
        penal_recent = max(0, max_overlap - 11) * 1.0
    else:
        penal_recent = max(0, max_overlap - 9) * 1.4

    qtd_quentes = len(jogo_set & quentes)
    qtd_frias = len(jogo_set & frias)

    bonus_quentes = 0.35 * _normalizar_0_1(qtd_quentes, 2, 7)
    penal_frias = 0.20 * _normalizar_0_1(qtd_frias, 4, 8)

    f1 = sum(1 for d in jogo if 1 <= d <= 9)
    f2 = sum(1 for d in jogo if 10 <= d <= 18)
    f3 = sum(1 for d in jogo if 19 <= d <= 25)

    bal = (abs(f1 - 5) + abs(f2 - 5) + abs(f3 - 5))
    penal_balance = 0.18 * bal

    score_base = (cobertura_score + bonus_quentes - penal_frias) - (penal_recent + penal_balance)

    # -------------------------
    # PATCH: diversidade/cobertura/separação
    # -------------------------
    finais = int(getattr(config, "jogos_finais", 2) or 2)
    preset_req = str(getattr(config, "preset", "auto")).lower()

    if preset_req == "solo":
        cfg = PRESET_SOLO
    elif preset_req == "cobertura":
        cfg = PRESET_COBERTURA
    else:
        cfg = PRESET_SOLO if finais <= 1 else PRESET_COBERTURA

    score = float(score_base)

    # união dos escolhidos
    uniao = set()
    for g in escolhidos:
        uniao |= set(g)

    novas = len(jogo_set - uniao)
    score += cfg.peso_cobertura * novas

    if escolhidos:
        overlaps = [len(jogo_set & set(g)) for g in escolhidos]
        max_ov = max(overlaps) if overlaps else 0

        jaccs = [_jaccard(jogo_set, set(g)) for g in escolhidos]
        max_j = max(jaccs) if jaccs else 0.0

        penalty_overlap = cfg.peso_overlap * max_ov
        penalty_jacc = cfg.peso_jaccard * max_j

        if max_ov >= cfg.overlap_alvo_max:
            extra = (max_ov - cfg.overlap_alvo_max + 1)
            penalty_overlap *= (cfg.reforco_overlap_extra ** extra)

        score -= (penalty_overlap + penalty_jacc)

    freq_vals = [float(freq.get(int(d), 0.0)) for d in jogo]
    mean_freq_jogo = _mean(freq_vals)
    mean_freq_global = _mean(list(freq.values())) if freq else 0.0

    if modo.startswith("agre"):
        score += cfg.peso_separacao_modo * (mean_freq_jogo - mean_freq_global)
    else:
        score -= cfg.peso_separacao_modo * abs(mean_freq_jogo - mean_freq_global)

    return float(score)