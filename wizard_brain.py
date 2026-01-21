# wizard_brain.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import math
import numpy as np
import pandas as pd


# ============================================================
#   SAÍDAS / TIPOS
# ============================================================

@dataclass(frozen=True)
class Estatisticas:
    freq: Dict[int, float]        # frequência (0..1) por dezena (1..25)
    quentes: Set[int]             # top quentes
    frias: Set[int]               # top frias
    freq_media: float             # média global das frequências


@dataclass(frozen=True)
class DiversidadeConfig:
    # Punições por repetição com jogos já escolhidos
    peso_overlap: float = 1.2          # penaliza qtd de dezenas repetidas
    peso_jaccard: float = 6.0          # penaliza similaridade (overlap / união)

    # Bônus por cobertura (novas dezenas no conjunto)
    peso_cobertura: float = 0.8        # bônus por dezena nova no conjunto

    # Mantém agressivo e conservador diferentes
    # agressivo tende a aceitar "hot" (freq recente alta),
    # conservador tende a puxar para o miolo (freq próxima da média).
    peso_separacao_modo: float = 0.15

    # Controle de limite (evita punição exagerada)
    overlap_alvo_max: int = 11         # se dois jogos repetem >= isso, pune mais
    reforco_overlap_extra: float = 1.8 # multiplicador extra quando passa do alvo


# Melhor para apostar 1 jogo (pune pouco a diversidade)
PRESET_SOLO = DiversidadeConfig(
    peso_overlap=0.6,
    peso_jaccard=3.0,
    peso_cobertura=0.25,
    peso_separacao_modo=0.12,
    overlap_alvo_max=12,
    reforco_overlap_extra=1.4,
)

# Melhor para apostar 2+ jogos (pune overlap e força cobertura)
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
    # Espera colunas D1..D15
    cols = [f"D{i}" for i in range(1, 16)]
    arr = df[cols].to_numpy(dtype=int, copy=True)
    return arr


def _binvec_25(dezenas15: Sequence[int]) -> np.ndarray:
    v = np.zeros(25, dtype=np.int8)
    for d in dezenas15:
        if 1 <= int(d) <= 25:
            v[int(d) - 1] = 1
    return v


# ============================================================
#   QUENTES/FRIAS (base)
# ============================================================

def detectar_quentes_frias(
    base_df: pd.DataFrame,
    ultimos: int = 200,
    top_quentes: int = 7,
    top_frias: int = 7,
) -> Estatisticas:
    """
    Calcula frequências nas últimas 'ultimos' linhas da base.
    Retorna:
      - freq: proporção (0..1) de aparição da dezena nos concursos analisados
      - quentes: maiores frequências
      - frias: menores frequências
      - freq_media: média das frequências
    """
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
#   CLUSTERIZAÇÃO (opcional) — modelo leve
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
    """
    Cria clusters simples dos concursos (vetor binário 25).
    Se sklearn não existir no ambiente, devolve modelo "vazio" (não quebra).
    """
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


def _cluster_bonus(
    dezenas: Sequence[int],
    modelo_cluster: ClusterModel,
    ultimos_df: pd.DataFrame,
) -> float:
    """
    Pequeno bônus se o candidato cair em cluster "menos comum" nos últimos concursos.
    (Serve só como tie-break, não como motor principal.)
    """
    if modelo_cluster is None or modelo_cluster.kmeans is None or modelo_cluster.n_clusters <= 0:
        return 0.0

    try:
        km = modelo_cluster.kmeans
        v = _binvec_25(dezenas).reshape(1, -1)
        c = int(km.predict(v)[0])

        arr = _extrair_dezenas_df(ultimos_df)
        X = np.stack([_binvec_25(row) for row in arr], axis=0)
        labels = km.predict(X)

        counts = np.bincount(labels, minlength=modelo_cluster.n_clusters)
        total = counts.sum() if counts.sum() > 0 else 1
        frac = counts[c] / total

        # cluster raro -> bônus maior
        return float(0.8 * (1.0 - frac))
    except Exception:
        return 0.0


# ============================================================
#   SCORE INTELIGENTE (COM PATCH)
#   Assinatura compatível com seu wizard_cli.py
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
    """
    Score final = score_base + (patch diversidade/cobertura/separação modo)

    Espera 'config' com:
      - modo: "agressivo"/"conservador"
      - jogos_finais (ou config.jogos_finais)
    """
    jogo = sorted(int(x) for x in dezenas)
    jogo_set = set(jogo)
    modo = str(getattr(config, "modo", "conservador")).lower()

    # -------------------------
    # (A) SCORE BASE (o seu motor)
    # -------------------------

    # A1) Cobertura local (prefere dezenas menos usadas nos escolhidos)
    cobertura_score = 0.0
    for d in jogo:
        freq_local = float(cobertura_contagem.get(d, 0))
        cobertura_score += 1.0 / (1.0 + freq_local)

    # A2) Penalidade por "colar" demais nos últimos concursos
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(jogo_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    # agressivo tolera um pouco mais repetição
    if modo.startswith("agre"):
        penal_recent = max(0, max_overlap - 11) * 1.0
    else:
        penal_recent = max(0, max_overlap - 9) * 1.4

    # A3) Quentes/Frias (leve, pra não viciar)
    qtd_quentes = len(jogo_set & quentes)
    qtd_frias = len(jogo_set & frias)

    # alvo “natural”: uns 4~6 quentes, 2~4 frias (bem leve)
    bonus_quentes = 0.35 * _normalizar_0_1(qtd_quentes, 2, 7)
    penal_frias = 0.20 * _normalizar_0_1(qtd_frias, 4, 8)

    # A4) Balanceamento por faixa (1–9 / 10–18 / 19–25) evita extremos
    f1 = sum(1 for d in jogo if 1 <= d <= 9)
    f2 = sum(1 for d in jogo if 10 <= d <= 18)
    f3 = sum(1 for d in jogo if 19 <= d <= 25)

    # ideal ~ 5/5/5 ou próximo
    bal = (abs(f1 - 5) + abs(f2 - 5) + abs(f3 - 5))
    penal_balance = 0.18 * bal

    # A5) Cluster tie-break
    # (precisa ultimos_df no caller; aqui fazemos sem — então deixamos neutro)
    cluster_bonus = 0.0

    score_base = (cobertura_score + bonus_quentes - penal_frias) - (penal_recent + penal_balance) + cluster_bonus

    # -------------------------
    # (B) PATCH: diversidade + cobertura conjunto + separação de modos
    # -------------------------

    finais = int(getattr(config, "jogos_finais", getattr(config, "jogos_finais", 2)) or 2)
    cfg = PRESET_SOLO if finais <= 1 else PRESET_COBERTURA

    score = float(score_base)

    # B1) Cobertura do CONJUNTO (união dos escolhidos)
    uniao = set()
    for g in escolhidos:
        uniao |= set(g)

    novas = len(jogo_set - uniao)
    score += cfg.peso_cobertura * novas

    # B2) Penaliza “clone” (overlap e jaccard) com os já escolhidos
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

    # B3) Separação real de modo usando frequência recente
    # agressivo: puxa acima da média ("hot")
    # conservador: puxa para perto da média (menos extremo)
    freq_vals = [float(freq.get(int(d), 0.0)) for d in jogo]
    mean_freq_jogo = _mean(freq_vals)
    mean_freq_global = _mean(list(freq.values())) if freq else 0.0

    if modo.startswith("agre"):
        score += cfg.peso_separacao_modo * (mean_freq_jogo - mean_freq_global)
    else:
        score -= cfg.peso_separacao_modo * abs(mean_freq_jogo - mean_freq_global)

    return float(score)


# ============================================================
#   SELEÇÃO FINAL (GREEDY) — use no wizard_cli (opcional)
#   (Você pode manter seu loop atual que chama calcular_score_inteligente;
#    este método é útil se você quiser pontuar candidatos e escolher depois.)
# ============================================================

def selecionar_jogos_finais_diversos(
    candidatos: List[Tuple[Sequence[int], float]],
    modo: str,
    finais: int,
    cfg: DiversidadeConfig,
    freq: Dict[int, float],
    escolhidos_seed: Optional[List[Sequence[int]]] = None,
) -> List[Sequence[int]]:
    """
    candidatos: lista de (dezenas, score_base)
    retorna: lista com 'finais' jogos, evitando clones.
    OBS: Aqui é genérico; seu wizard_cli hoje faz seleção “em fluxo”.
    """
    escolhidos: List[Sequence[int]] = list(escolhidos_seed or [])
    uniao: Set[int] = set()
    for g in escolhidos:
        uniao |= _to_set(g)

    # freq média global para separação de modo
    mean_freq_global = _mean(list(freq.values())) if freq else 0.0

    def score_diverso(dezenas: Sequence[int], score_base: float) -> float:
        jogo = _to_set(dezenas)
        score = float(score_base)

        # cobertura
        novas = len(jogo - uniao)
        score += cfg.peso_cobertura * novas

        # diversidade
        if escolhidos:
            overlaps = [len(jogo & _to_set(g)) for g in escolhidos]
            max_ov = max(overlaps) if overlaps else 0

            jaccs = [_jaccard(jogo, _to_set(g)) for g in escolhidos]
            max_j = max(jaccs) if jaccs else 0.0

            penalty_overlap = cfg.peso_overlap * max_ov
            penalty_jacc = cfg.peso_jaccard * max_j

            if max_ov >= cfg.overlap_alvo_max:
                extra = (max_ov - cfg.overlap_alvo_max + 1)
                penalty_overlap *= (cfg.reforco_overlap_extra ** extra)

            score -= (penalty_overlap + penalty_jacc)

        # separação de modo
        freqs = [float(freq.get(int(d), 0.0)) for d in jogo]
        mean_freq_jogo = _mean(freqs)
        if str(modo).lower().startswith("agre"):
            score += cfg.peso_separacao_modo * (mean_freq_jogo - mean_freq_global)
        else:
            score -= cfg.peso_separacao_modo * abs(mean_freq_jogo - mean_freq_global)

        return score

    pool = list(candidatos)
    finais = int(finais)

    for _ in range(finais):
        if not pool:
            break

        melhor_idx = -1
        melhor_score = -1e18

        for idx, (dezenas, base_sc) in enumerate(pool):
            sc = score_diverso(dezenas, float(base_sc))
            if sc > melhor_score:
                melhor_score = sc
                melhor_idx = idx

        if melhor_idx < 0:
            break

        melhor_dezenas, _ = pool.pop(melhor_idx)
        escolhidos.append(list(melhor_dezenas))
        uniao |= _to_set(melhor_dezenas)

    return escolhidos