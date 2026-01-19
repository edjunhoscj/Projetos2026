# wizard_brain.py  (na raiz)
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _contar_altas_20_25(dezenas: list[int]) -> int:
    return sum(1 for d in dezenas if 20 <= d <= 25)


def _jaccard(a: set[int], b: set[int]) -> float:
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0


def _perfil_modo(config) -> dict:
    """
    Define "personalidade" do modo pra evitar agressivo == conservador.
    Ajuste fino aqui se quiser.
    """
    if config.modo == "agressivo":
        return {
            "w_freq": 1.00,          # peso de frequência
            "w_quentes": 0.90,       # favorece quentes
            "w_frias": 0.25,         # aceita algumas frias
            "w_recencia": 0.60,      # penaliza repetição com últimos (mais leve)
            "w_div": 2.20,           # diversidade entre jogos (alto!)
            "w_cov": 2.10,           # cobertura do conjunto (alto!)
            "max_jaccard": 0.62,     # limite de similaridade (mais tolerante)
            "target_20_25": (4, 6),  # quer 4-6 dezenas 20..25 (tendência)
        }
    else:
        return {
            "w_freq": 0.85,
            "w_quentes": 0.55,
            "w_frias": 0.45,         # conservador aceita mais equilíbrio
            "w_recencia": 0.95,      # penaliza repetição com últimos (mais forte)
            "w_div": 2.60,           # diversidade ainda maior
            "w_cov": 2.30,
            "max_jaccard": 0.56,     # mais exigente (menos jogos parecidos)
            "target_20_25": (3, 5),
        }


def calcular_score_inteligente(
    dezenas: list[int],
    ultimos_tuplas: set[tuple[int, ...]],
    cobertura_contagem: dict[int, int],
    quentes: set[int],
    frias: set[int],
    freq: dict[int, int],
    modelo_cluster,
    config,
    escolhidos: list[tuple[int, ...]],
) -> float:
    """
    Score "de verdade" para evitar jogos viciados:
      1) Frequência (histórica) + quentes/frias (com pesos por modo)
      2) Penalização de repetição com concursos recentes (recência)
      3) Diversidade ENTRE os jogos escolhidos (punir Jaccard alto e overlap alto)
      4) Cobertura do CONJUNTO (recompensa trazer dezenas novas ao pool)
      5) Tendência 20..25 como "soft target" (sem engessar)
    """
    p = _perfil_modo(config)

    dezenas = sorted(dezenas)
    s = set(dezenas)

    # -----------------------------
    # 1) Frequência + quentes/frias
    # -----------------------------
    # normaliza freq pela maior frequência observada (evita explodir score)
    maxf = max(freq.values()) if freq else 1
    freq_score = sum((freq.get(d, 0) / maxf) for d in dezenas) / 15.0

    # quentes/frias
    qtd_quentes = sum(1 for d in dezenas if d in quentes)
    qtd_frias = sum(1 for d in dezenas if d in frias)
    quentes_score = qtd_quentes / 15.0
    frias_score = qtd_frias / 15.0

    score_base = (
        p["w_freq"] * freq_score
        + p["w_quentes"] * quentes_score
        + p["w_frias"] * frias_score
    )

    # -----------------------------
    # 2) Penalização por recência
    # -----------------------------
    # quanto mais parecido com algum dos últimos concursos, pior (dependendo do modo)
    max_overlap_ultimos = 0
    for ult in ultimos_tuplas:
        inter = len(s.intersection(ult))
        if inter > max_overlap_ultimos:
            max_overlap_ultimos = inter

    # penaliza acima de um “limiar razoável”
    # agressivo tolera mais repetição com últimos; conservador tolera menos
    limiar = 11 if config.modo == "agressivo" else 10
    recencia_pen = max(0, max_overlap_ultimos - limiar) * p["w_recencia"]

    # -----------------------------
    # 3) Diversidade entre jogos escolhidos
    # -----------------------------
    # ideia: se você já escolheu um jogo muito parecido, esse candidato cai muito no score
    div_pen = 0.0
    if escolhidos:
        # união do que já foi escolhido
        for j in escolhidos:
            sj = set(j)
            jac = _jaccard(s, sj)

            # penalidade suave + "muro" se passar do limite de Jaccard
            if jac > p["max_jaccard"]:
                div_pen += (jac - p["max_jaccard"]) * 10.0  # cai forte

            # também punir overlap absoluto (ex.: 12/15 iguais)
            overlap = len(s & sj)
            if overlap >= (10 if config.modo == "agressivo" else 9):
                div_pen += (overlap - 9) * 0.8

        div_pen *= p["w_div"]

    # -----------------------------
    # 4) Cobertura do conjunto (recompensa “trazer dezenas novas”)
    # -----------------------------
    cov_bonus = 0.0
    if escolhidos:
        ja = set()
        for j in escolhidos:
            ja |= set(j)

        novas = len(s - ja)  # quantas dezenas novas esse jogo adiciona ao pool
        # bônus cresce rápido no começo, depois suaviza
        cov_bonus = (novas / 15.0) * p["w_cov"]

        # extra: se o pool total está pequeno, incentiva ainda mais
        # (evita 5 jogos quase iguais)
        pool_atual = len(ja)
        if pool_atual < (18 if config.modo == "agressivo" else 20):
            cov_bonus += 0.35

    else:
        # primeiro jogo: cobertura não existe ainda, então não mexe
        cov_bonus = 0.0

    # -----------------------------
    # 5) Tendência 20..25 (soft target)
    # -----------------------------
    # Não força, mas melhora se ficar dentro do intervalo desejado
    c2025 = _contar_altas_20_25(dezenas)
    lo, hi = p["target_20_25"]
    if c2025 < lo:
        bonus_2025 = -0.30 * (lo - c2025)
    elif c2025 > hi:
        bonus_2025 = -0.20 * (c2025 - hi)
    else:
        bonus_2025 = +0.25

    # -----------------------------
    # Cobertura de repetição interna (já existe no teu fluxo via cobertura_contagem)
    # -----------------------------
    # Isso ajuda a evitar “sempre as mesmas dezenas” dentro do conjunto
    # (mantém, mas com peso menor para não dominar)
    cov_interna = 0.0
    for d in dezenas:
        f = cobertura_contagem.get(d, 0)
        cov_interna += 1.0 / (1.0 + f)
    cov_interna = (cov_interna / 15.0) * 0.65

    # -----------------------------
    # Score final
    # -----------------------------
    score = score_base + cov_interna + cov_bonus + bonus_2025 - recencia_pen - div_pen

    return float(score)