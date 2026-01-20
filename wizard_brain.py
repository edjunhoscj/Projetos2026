# =========================
# PATCH: Diversidade + Cobertura + Separação de modos
# Arquivo: wizard_brain.py (na raiz)
# =========================

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple
import math


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

# Melhor para apostar 2 jogos (pune overlap e força cobertura)
PRESET_COBERTURA = DiversidadeConfig(
    peso_overlap=1.3,
    peso_jaccard=7.0,
    peso_cobertura=1.0,
    peso_separacao_modo=0.18,
    overlap_alvo_max=10,
    reforco_overlap_extra=2.0,
)


def _to_set(dezenas: Iterable[int]) -> Set[int]:
    return set(int(x) for x in dezenas)


def _jaccard(a: Set[int], b: Set[int]) -> float:
    inter = len(a & b)
    uni = len(a | b)
    return (inter / uni) if uni else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# -------------------------------------------------------------------
# SUBSTITUA a sua função calcular_score_inteligente por esta versão.
# Ela assume que você já calcula um score base dentro do método.
# Se no seu código o score base já está em "score", preserve e use aqui.
# -------------------------------------------------------------------
def calcular_score_inteligente(
    self,
    dezenas: Sequence[int],
    modo: str,
    *,
    score_base: float,
    ja_escolhidos: Optional[List[Sequence[int]]] = None,
    uniao_escolhidos: Optional[Set[int]] = None,
    cfg: DiversidadeConfig = PRESET_COBERTURA,
) -> float:
    """
    Retorna score final = score_base + ajustes de diversidade/cobertura/modo.

    - ja_escolhidos: jogos já escolhidos no greedy
    - uniao_escolhidos: união de dezenas já cobertas
    - cfg: preset (PRESET_SOLO ou PRESET_COBERTURA)
    """
    jogo = _to_set(dezenas)
    escolhidos = ja_escolhidos or []
    uniao = uniao_escolhidos or set()

    score = float(score_base)

    # 1) Cobertura: recompensa dezenas novas no conjunto
    novas = len(jogo - uniao)
    score += cfg.peso_cobertura * novas

    # 2) Repetição: penaliza parecido com o que já foi escolhido
    if escolhidos:
        overlaps = [len(jogo & _to_set(g)) for g in escolhidos]
        max_overlap = max(overlaps) if overlaps else 0

        # penaliza overlap bruto
        penalty_overlap = cfg.peso_overlap * max_overlap

        # penaliza jaccard (similaridade estrutural)
        jaccs = [_jaccard(jogo, _to_set(g)) for g in escolhidos]
        penalty_jacc = cfg.peso_jaccard * (max(jaccs) if jaccs else 0.0)

        # reforço se overlap passou do alvo (pra impedir jogos clones)
        if max_overlap >= cfg.overlap_alvo_max:
            extra = (max_overlap - cfg.overlap_alvo_max + 1)
            penalty_overlap *= (cfg.reforco_overlap_extra ** extra)

        score -= (penalty_overlap + penalty_jacc)

    # 3) Separação de modos: agressivo vs conservador
    # Requer que o brain tenha um mapa de frequências recentes.
    # Se não existir, simplesmente ignora sem quebrar.
    try:
        freq_map = getattr(self, "freq_recente", None) or getattr(self, "freq", None)
        if freq_map:
            freqs = [float(freq_map.get(int(d), 0.0)) for d in jogo]
            mean_freq_jogo = _mean(freqs)
            mean_freq_global = float(getattr(self, "freq_media", _mean(list(freq_map.values()))))

            # agressivo: puxa acima da média (mais "hot")
            # conservador: puxa para perto da média (menos extremo)
            if str(modo).lower().startswith("agre"):
                score += cfg.peso_separacao_modo * (mean_freq_jogo - mean_freq_global)
            else:
                score -= cfg.peso_separacao_modo * abs(mean_freq_jogo - mean_freq_global)
    except Exception:
        pass

    return score


# -------------------------------------------------------------------
# NOVO: seleção gulosa com diversidade/cobertura
# Use isso no lugar de: "pegar os top-N por score_base"
# -------------------------------------------------------------------
def selecionar_jogos_finais_diversos(
    self,
    candidatos: List[Tuple[Sequence[int], float]],
    modo: str,
    finais: int,
    cfg: DiversidadeConfig,
) -> List[Sequence[int]]:
    """
    candidatos: lista de (dezenas, score_base)
    retorna: lista com 'finais' jogos, evitando clones.
    """
    escolhidos: List[Sequence[int]] = []
    uniao: Set[int] = set()

    # greedy: a cada passo, recalcula score com diversidade em relação ao que já foi escolhido
    for _ in range(int(finais)):
        melhor = None
        melhor_score = -1e18

        for dezenas, score_base in candidatos:
            sc = calcular_score_inteligente(
                self,
                dezenas,
                modo,
                score_base=float(score_base),
                ja_escolhidos=escolhidos,
                uniao_escolhidos=uniao,
                cfg=cfg,
            )
            if sc > melhor_score:
                melhor_score = sc
                melhor = dezenas

        if melhor is None:
            break

        escolhidos.append(list(melhor))
        uniao |= _to_set(melhor)

        # opcional: remove o escolhido do pool para não repetir
        candidatos = [(d, s) for (d, s) in candidatos if list(d) != list(melhor)]

    return escolhidos