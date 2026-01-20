from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import math
import numpy as np
import pandas as pd


# =========================
#  Estruturas
# =========================

@dataclass
class Estatisticas:
    freq: Dict[int, int]
    quentes: Set[int]
    frias: Set[int]
    ultimos_n: int


# =========================
#  Helpers
# =========================

def _extrair_dezenas_df(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    arr = df[cols].to_numpy(dtype=int, copy=True)
    return arr


def detectar_quentes_frias(base_df: pd.DataFrame, ultimos_n: int = 200, top_k: int = 8) -> Estatisticas:
    """
    Calcula frequência das dezenas considerando a base inteira e
    identifica quentes/frias olhando os últimos `ultimos_n` concursos.
    """
    arr_all = _extrair_dezenas_df(base_df)
    flat_all = arr_all.flatten()

    freq: Dict[int, int] = {d: 0 for d in range(1, 26)}
    for d in flat_all:
        if 1 <= int(d) <= 25:
            freq[int(d)] += 1

    # quentes/frias por recência
    df_last = base_df.tail(int(ultimos_n)).copy()
    arr_last = _extrair_dezenas_df(df_last)
    flat_last = arr_last.flatten()

    freq_last: Dict[int, int] = {d: 0 for d in range(1, 26)}
    for d in flat_last:
        if 1 <= int(d) <= 25:
            freq_last[int(d)] += 1

    ordenado = sorted(freq_last.items(), key=lambda x: x[1], reverse=True)
    quentes = {d for d, _ in ordenado[:top_k]}
    frias = {d for d, _ in sorted(freq_last.items(), key=lambda x: x[1])[:top_k]}

    return Estatisticas(freq=freq, quentes=quentes, frias=frias, ultimos_n=int(ultimos_n))


def clusterizar_concursos(base_df: pd.DataFrame, k: int = 6):
    """
    Cluster leve: tenta usar sklearn se existir, mas não depende dele.
    Retorna um objeto com método predict(X) ou None.
    """
    try:
        from sklearn.cluster import KMeans  # type: ignore
    except Exception:
        return None

    X = _extrair_dezenas_df(base_df).astype(float)

    # Features simples: contagem por faixa + soma + pares/ímpares
    def feats(row: np.ndarray) -> List[float]:
        row = np.sort(row)
        f1 = np.sum((1 <= row) & (row <= 5))
        f2 = np.sum((6 <= row) & (row <= 10))
        f3 = np.sum((11 <= row) & (row <= 15))
        f4 = np.sum((16 <= row) & (row <= 20))
        f5 = np.sum((21 <= row) & (row <= 25))
        soma = float(np.sum(row))
        pares = float(np.sum(row % 2 == 0))
        return [f1, f2, f3, f4, f5, soma, pares]

    F = np.array([feats(r) for r in X], dtype=float)

    km = KMeans(n_clusters=int(k), random_state=42, n_init="auto")
    km.fit(F)
    return km


def _overlap(a: List[int], b: List[int]) -> int:
    sa = set(a)
    sb = set(b)
    return len(sa.intersection(sb))


def _max_consecutivos(dezenas: List[int]) -> int:
    dezenas = sorted(dezenas)
    run = 1
    best = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i - 1] + 1:
            run += 1
        else:
            best = max(best, run)
            run = 1
    best = max(best, run)
    return best


def calcular_score_inteligente(
    dezenas: List[int],
    ultimos_tuplas: Set[Tuple[int, ...]],
    cobertura_contagem: Dict[int, int],
    quentes: Set[int],
    frias: Set[int],
    freq: Dict[int, int],
    modelo_cluster,
    config,
    escolhidos: List[Tuple[int, ...]],
) -> float:
    """
    Score inteligente:
    - Diversidade entre jogos escolhidos (penaliza repetição entre eles)
    - Cobertura (força espalhar dezenas)
    - Quentes/Frias (com pesos diferentes por modo)
    - Padrões plausíveis (pares/ímpares, soma, consecutivos, 20-25)
    - Diferença real entre agressivo e conservador
    """

    modo = getattr(config, "modo", "conservador")
    dezenas = sorted([int(x) for x in dezenas])
    dezenas_set = set(dezenas)

    # ---------- 1) Cobertura (força espalhar)
    # Quanto menos usada a dezena nos escolhidos, maior o bônus.
    cobertura = 0.0
    for d in dezenas:
        cobertura += 1.0 / (1.0 + float(cobertura_contagem.get(d, 0)))

    # ---------- 2) Frequência histórica (suave) + log para não “viciar”
    # Normaliza por [min,max] e aplica compressão log.
    vals = np.array([freq.get(d, 0) for d in range(1, 26)], dtype=float)
    vmin, vmax = float(vals.min()), float(vals.max())
    def norm(v: float) -> float:
        if vmax == vmin:
            return 0.5
        return (v - vmin) / (vmax - vmin)

    freq_score = 0.0
    for d in dezenas:
        x = norm(float(freq.get(d, 0)))
        freq_score += math.log(1.0 + 9.0 * x)  # 0..~2.3

    # ---------- 3) Quentes/Frias (pesos por modo)
    qtd_quentes = sum(1 for d in dezenas if d in quentes)
    qtd_frias = sum(1 for d in dezenas if d in frias)

    # agressivo: gosta de quentes; tolera frias pouco
    # conservador: quer mix (nem “só quente”, nem “só frio”)
    if modo == "agressivo":
        hot_bonus = 0.35 * qtd_quentes
        cold_pen = 0.12 * qtd_frias
    else:
        # ideal ~ 4 a 6 quentes (ajuste fino)
        hot_bonus = 0.20 * max(0, 6 - abs(qtd_quentes - 5))
        cold_pen = 0.08 * max(0, qtd_frias - 4)

    # ---------- 4) Penalidade por semelhança com concursos recentes
    # conservador penaliza mais overlap; agressivo penaliza menos
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(dezenas_set.intersection(set(ult)))
        max_overlap = max(max_overlap, inter)

    if modo == "conservador":
        penal_ult = max(0, max_overlap - 9) * 0.65
    else:
        penal_ult = max(0, max_overlap - 11) * 0.35

    # ---------- 5) Penalidade por repetir demais entre os escolhidos
    # Isso é o que “desvicia” e faz agressivo/conservador realmente diferentes.
    if escolhidos:
        overlaps = []
        for j in escolhidos:
            overlaps.append(_overlap(dezenas, list(j)))
        avg_ov = float(np.mean(overlaps))
    else:
        avg_ov = 0.0

    # penaliza se estiver muito parecido com os anteriores
    penal_repeticao = max(0.0, avg_ov - (9.5 if modo == "agressivo" else 8.0)) * 0.75

    # ---------- 6) Regras estatísticas leves (sem travar)
    pares = sum(1 for d in dezenas if d % 2 == 0)
    impares = 15 - pares
    # alvo típico 7/8
    paridade_bonus = 0.0
    if 6 <= pares <= 9:
        paridade_bonus = 0.35
    else:
        paridade_bonus = -0.25 * abs(pares - 7.5)

    soma = sum(dezenas)
    # soma “plausível” (range típico) – ajuste leve
    soma_bonus = 0.0
    if 170 <= soma <= 230:
        soma_bonus = 0.35
    else:
        soma_bonus = -0.02 * min(abs(soma - 200), 60)

    # consecutivos
    maxseq = _max_consecutivos(dezenas)
    cons_bonus = 0.0
    if maxseq <= getattr(config, "max_seq_run", 4):
        cons_bonus = 0.25
    else:
        cons_bonus = -0.60 * (maxseq - getattr(config, "max_seq_run", 4))

    # ---------- 7) Forçar presença 20–25 (observação prática do usuário)
    # Sem “obrigar demais”: dá bônus se tiver 3 a 6 dezenas em 20..25
    qtd_20_25 = sum(1 for d in dezenas if 20 <= d <= 25)
    if modo == "agressivo":
        bonus_20_25 = 0.25 * max(0, 4 - abs(qtd_20_25 - 4))
    else:
        bonus_20_25 = 0.18 * max(0, 4 - abs(qtd_20_25 - 4))

    # ---------- 8) Cluster (opcional)
    cluster_bonus = 0.0
    if modelo_cluster is not None:
        try:
            # monta feature igual ao treino
            row = np.array(dezenas, dtype=float)
            f1 = np.sum((1 <= row) & (row <= 5))
            f2 = np.sum((6 <= row) & (row <= 10))
            f3 = np.sum((11 <= row) & (row <= 15))
            f4 = np.sum((16 <= row) & (row <= 20))
            f5 = np.sum((21 <= row) & (row <= 25))
            soma = float(np.sum(row))
            pares = float(np.sum(row % 2 == 0))
            F = np.array([[f1, f2, f3, f4, f5, soma, pares]], dtype=float)
            _ = modelo_cluster.predict(F)
            cluster_bonus = 0.10
        except Exception:
            cluster_bonus = 0.0

    # ---------- 9) Pesos finais por modo
    if modo == "agressivo":
        score = (
            1.05 * cobertura +
            0.55 * freq_score +
            hot_bonus - cold_pen -
            penal_ult -
            penal_repeticao +
            paridade_bonus +
            soma_bonus +
            cons_bonus +
            bonus_20_25 +
            cluster_bonus
        )
    else:
        score = (
            1.20 * cobertura +
            0.45 * freq_score +
            hot_bonus - cold_pen -
            penal_ult -
            1.15 * penal_repeticao +
            1.05 * paridade_bonus +
            1.05 * soma_bonus +
            cons_bonus +
            0.85 * bonus_20_25 +
            cluster_bonus
        )

    return float(score)