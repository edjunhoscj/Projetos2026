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
    peso_separacao_modo: float = 0.15

    # Controle de limite (evita punição exagerada)
    overlap_alvo_max: int = 11
    reforco_overlap_extra: float = 1.8


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
#   BANDAS (NOVO) — “perfil típico” dos últimos N concursos
# ============================================================

@dataclass(frozen=True)
class BandasConfig:
    # Quantos desvios padrão definem a “faixa típica”
    k_std: float = 1.0

    # Pesos (penalidades) para o modo soft
    w_soma: float = 0.55
    w_pares: float = 0.35
    w_faixas: float = 0.25     # 1-5,6-10,11-15,16-20,21-25 (cada)
    w_run: float = 0.20        # max sequência consecutiva

    # Peso geral (multiplicador)
    peso_geral: float = 1.0


@dataclass(frozen=True)
class BandasModel:
    ultimos: int
    cfg: BandasConfig

    # soma das dezenas
    soma_mu: float
    soma_sd: float
    soma_lo: float
    soma_hi: float

    # qtd pares
    pares_mu: float
    pares_sd: float
    pares_lo: float
    pares_hi: float

    # faixas 1-5, 6-10, 11-15, 16-20, 21-25
    faixa_mu: Dict[str, float]
    faixa_sd: Dict[str, float]
    faixa_lo: Dict[str, float]
    faixa_hi: Dict[str, float]

    # max run consecutivos
    run_mu: float
    run_sd: float
    run_lo: float
    run_hi: float


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    m = _mean(values)
    v = _mean([(x - m) ** 2 for x in values])
    return float(math.sqrt(max(0.0, v)))


def _to_set(dezenas: Iterable[int]) -> Set[int]:
    return set(int(x) for x in dezenas)


def _jaccard(a: Set[int], b: Set[int]) -> float:
    inter = len(a & b)
    uni = len(a | b)
    return (inter / uni) if uni else 0.0


def _extrair_dezenas_df(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    return df[cols].to_numpy(dtype=int, copy=True)


def _max_run_consecutivos(dezenas15: Sequence[int]) -> int:
    d = sorted(int(x) for x in dezenas15)
    run = 1
    best = 1
    for i in range(1, len(d)):
        if d[i] == d[i - 1] + 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return int(best)


def _faixas_1a25(dezenas15: Sequence[int]) -> Dict[str, int]:
    # “quadrantes” práticos por faixa (5 blocos)
    # 1-5, 6-10, 11-15, 16-20, 21-25
    out = {"f1_5": 0, "f6_10": 0, "f11_15": 0, "f16_20": 0, "f21_25": 0}
    for d in dezenas15:
        d = int(d)
        if 1 <= d <= 5:
            out["f1_5"] += 1
        elif 6 <= d <= 10:
            out["f6_10"] += 1
        elif 11 <= d <= 15:
            out["f11_15"] += 1
        elif 16 <= d <= 20:
            out["f16_20"] += 1
        elif 21 <= d <= 25:
            out["f21_25"] += 1
    return out


def construir_bandas(
    base_df: pd.DataFrame,
    ultimos: int = 300,
    cfg: Optional[BandasConfig] = None,
) -> BandasModel:
    cfg = cfg or BandasConfig()

    if "Concurso" in base_df.columns:
        base_df = base_df.sort_values("Concurso")

    df = base_df.tail(int(ultimos)).reset_index(drop=True)
    arr = _extrair_dezenas_df(df)

    somas: List[float] = []
    pares: List[float] = []
    runs: List[float] = []
    faixas_series: Dict[str, List[float]] = {k: [] for k in ["f1_5", "f6_10", "f11_15", "f16_20", "f21_25"]}

    for row in arr:
        dezenas = [int(x) for x in row]
        somas.append(float(sum(dezenas)))
        pares.append(float(sum(1 for x in dezenas if int(x) % 2 == 0)))
        runs.append(float(_max_run_consecutivos(dezenas)))
        fx = _faixas_1a25(dezenas)
        for k, v in fx.items():
            faixas_series[k].append(float(v))

    soma_mu = _mean(somas)
    soma_sd = max(1e-6, _std(somas))
    soma_lo = soma_mu - cfg.k_std * soma_sd
    soma_hi = soma_mu + cfg.k_std * soma_sd

    pares_mu = _mean(pares)
    pares_sd = max(1e-6, _std(pares))
    pares_lo = pares_mu - cfg.k_std * pares_sd
    pares_hi = pares_mu + cfg.k_std * pares_sd

    faixa_mu = {k: _mean(v) for k, v in faixas_series.items()}
    faixa_sd = {k: max(1e-6, _std(v)) for k, v in faixas_series.items()}
    faixa_lo = {k: faixa_mu[k] - cfg.k_std * faixa_sd[k] for k in faixa_mu}
    faixa_hi = {k: faixa_mu[k] + cfg.k_std * faixa_sd[k] for k in faixa_mu}

    run_mu = _mean(runs)
    run_sd = max(1e-6, _std(runs))
    run_lo = run_mu - cfg.k_std * run_sd
    run_hi = run_mu + cfg.k_std * run_sd

    return BandasModel(
        ultimos=int(ultimos),
        cfg=cfg,
        soma_mu=soma_mu, soma_sd=soma_sd, soma_lo=soma_lo, soma_hi=soma_hi,
        pares_mu=pares_mu, pares_sd=pares_sd, pares_lo=pares_lo, pares_hi=pares_hi,
        faixa_mu=faixa_mu, faixa_sd=faixa_sd, faixa_lo=faixa_lo, faixa_hi=faixa_hi,
        run_mu=run_mu, run_sd=run_sd, run_lo=run_lo, run_hi=run_hi,
    )


def _penalidade_soft_bandas(dezenas15: Sequence[int], bandas: BandasModel) -> float:
    cfg = bandas.cfg
    dezenas = [int(x) for x in dezenas15]

    soma = float(sum(dezenas))
    pares = float(sum(1 for x in dezenas if x % 2 == 0))
    run = float(_max_run_consecutivos(dezenas))
    fx = {k: float(v) for k, v in _faixas_1a25(dezenas).items()}

    def dist_norm(x: float, lo: float, hi: float, sd: float) -> float:
        if lo <= x <= hi:
            return 0.0
        alvo = lo if x < lo else hi
        return abs(x - alvo) / max(1e-6, sd)

    p = 0.0
    p += cfg.w_soma * dist_norm(soma, bandas.soma_lo, bandas.soma_hi, bandas.soma_sd)
    p += cfg.w_pares * dist_norm(pares, bandas.pares_lo, bandas.pares_hi, bandas.pares_sd)

    for k in fx:
        p += cfg.w_faixas * dist_norm(fx[k], bandas.faixa_lo[k], bandas.faixa_hi[k], bandas.faixa_sd[k])

    p += cfg.w_run * dist_norm(run, bandas.run_lo, bandas.run_hi, bandas.run_sd)

    return float(cfg.peso_geral * p)


def _fora_bandas_hard(dezenas15: Sequence[int], bandas: BandasModel) -> bool:
    dezenas = [int(x) for x in dezenas15]
    soma = float(sum(dezenas))
    pares = float(sum(1 for x in dezenas if x % 2 == 0))
    run = float(_max_run_consecutivos(dezenas))
    fx = {k: float(v) for k, v in _faixas_1a25(dezenas).items()}

    if not (bandas.soma_lo <= soma <= bandas.soma_hi):
        return True
    if not (bandas.pares_lo <= pares <= bandas.pares_hi):
        return True
    if not (bandas.run_lo <= run <= bandas.run_hi):
        return True
    for k in fx:
        if not (bandas.faixa_lo[k] <= fx[k] <= bandas.faixa_hi[k]):
            return True
    return False


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

    total = max(1, len(df))
    freq = {d: cont[d] / total for d in range(1, 26)}
    freq_media = float(_mean(list(freq.values())))

    ordenado = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    quentes = set(d for d, _ in ordenado[:int(top_quentes)])

    ordenado_f = sorted(freq.items(), key=lambda kv: kv[1])
    frias = set(d for d, _ in ordenado_f[:int(top_frias)])

    return Estatisticas(freq=freq, quentes=quentes, frias=frias, freq_media=freq_media)


# ============================================================
#   CLUSTER (mantido leve)
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

    def binvec_25(row15: Sequence[int]) -> np.ndarray:
        v = np.zeros(25, dtype=np.int8)
        for d in row15:
            d = int(d)
            if 1 <= d <= 25:
                v[d - 1] = 1
        return v

    X = np.stack([binvec_25(row) for row in arr], axis=0)
    n_clusters = int(max(2, min(n_clusters, len(df) // 10 if len(df) >= 20 else 2)))

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    km.fit(X)

    return ClusterModel(kmeans=km, n_clusters=n_clusters)


# ============================================================
#   SCORE INTELIGENTE (com Bandas: off/soft/hard)
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
    bandas_model: Optional[BandasModel] = None,
) -> float:
    jogo = sorted(int(x) for x in dezenas)
    jogo_set = set(jogo)
    modo = str(getattr(config, "modo", "conservador")).lower()

    bandas_mode = str(getattr(config, "bandas", "soft") or "soft").lower()
    # bandas_mode: "off", "soft", "hard"
    if bandas_mode not in ("off", "soft", "hard"):
        bandas_mode = "soft"

    # HARD: descarta se foge do típico
    if bandas_mode == "hard" and bandas_model is not None:
        if _fora_bandas_hard(jogo, bandas_model):
            return -1e18

    # -------------------------
    # (A) SCORE BASE
    # -------------------------

    # A1) Cobertura local (prefere dezenas menos usadas nos escolhidos)
    cobertura_score = 0.0
    for d in jogo:
        freq_local = float(cobertura_contagem.get(d, 0))
        cobertura_score += 1.0 / (1.0 + freq_local)

    # A2) Penalidade por colar nos últimos concursos
    max_overlap_recent = 0
    for ult in ultimos_tuplas:
        inter = len(jogo_set.intersection(ult))
        if inter > max_overlap_recent:
            max_overlap_recent = inter

    if modo.startswith("agre"):
        penal_recent = max(0, max_overlap_recent - 11) * 1.0
    else:
        penal_recent = max(0, max_overlap_recent - 9) * 1.4

    # A3) Quentes/Frias (leve)
    qtd_quentes = len(jogo_set & quentes)
    qtd_frias = len(jogo_set & frias)

    def normalizar_0_1(x: float, lo: float, hi: float) -> float:
        if hi <= lo:
            return 0.0
        return max(0.0, min(1.0, (x - lo) / (hi - lo)))

    bonus_quentes = 0.35 * normalizar_0_1(qtd_quentes, 2, 7)
    penal_frias = 0.20 * normalizar_0_1(qtd_frias, 4, 8)

    # A4) Balanceamento por faixa 1–9 / 10–18 / 19–25
    f1 = sum(1 for d in jogo if 1 <= d <= 9)
    f2 = sum(1 for d in jogo if 10 <= d <= 18)
    f3 = sum(1 for d in jogo if 19 <= d <= 25)
    bal = (abs(f1 - 5) + abs(f2 - 5) + abs(f3 - 5))
    penal_balance = 0.18 * bal

    score_base = (cobertura_score + bonus_quentes - penal_frias) - (penal_recent + penal_balance)

    # -------------------------
    # (B) DIVERSIDADE + COBERTURA + SEPARAÇÃO DE MODOS
    # -------------------------

    finais = int(getattr(config, "jogos_finais", 2) or 2)

    # preset do diversity é decidido fora (via config.preset) no CLI; aqui só “auto”
    preset_div = str(getattr(config, "preset", "auto") or "auto").lower()
    if preset_div == "solo":
        cfg_div = PRESET_SOLO
    elif preset_div == "cobertura":
        cfg_div = PRESET_COBERTURA
    else:
        cfg_div = PRESET_SOLO if finais <= 1 else PRESET_COBERTURA

    score = float(score_base)

    # B1) Cobertura do CONJUNTO (união dos escolhidos)
    uniao = set()
    for g in escolhidos:
        uniao |= set(g)

    novas = len(jogo_set - uniao)
    score += cfg_div.peso_cobertura * novas

    # B2) Penaliza clone
    if escolhidos:
        overlaps = [len(jogo_set & set(g)) for g in escolhidos]
        max_ov = max(overlaps) if overlaps else 0

        jaccs = [_jaccard(jogo_set, set(g)) for g in escolhidos]
        max_j = max(jaccs) if jaccs else 0.0

        penalty_overlap = cfg_div.peso_overlap * max_ov
        penalty_jacc = cfg_div.peso_jaccard * max_j

        if max_ov >= cfg_div.overlap_alvo_max:
            extra = (max_ov - cfg_div.overlap_alvo_max + 1)
            penalty_overlap *= (cfg_div.reforco_overlap_extra ** extra)

        score -= (penalty_overlap + penalty_jacc)

    # B3) Separação de modo via freq recente
    freq_vals = [float(freq.get(int(d), 0.0)) for d in jogo]
    mean_freq_jogo = _mean(freq_vals)
    mean_freq_global = _mean(list(freq.values())) if freq else 0.0

    if modo.startswith("agre"):
        score += cfg_div.peso_separacao_modo * (mean_freq_jogo - mean_freq_global)
    else:
        score -= cfg_div.peso_separacao_modo * abs(mean_freq_jogo - mean_freq_global)

    # -------------------------
    # (C) BANDAS (NOVO) — modo SOFT
    # -------------------------
    if bandas_mode == "soft" and bandas_model is not None:
        # penaliza fora do “normal”
        score -= _penalidade_soft_bandas(jogo, bandas_model)

    return float(score)