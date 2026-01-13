from __future__ import annotations

import pandas as pd


def _normalizar_jogo(jogo) -> str:
    """
    Converte um jogo (lista/tupla/str) para string normalizada:
    '01 02 03 ... 15' (sempre ordenado e com zfill(2)).
    """
    if jogo is None:
        return ""

    # Se já for string
    if isinstance(jogo, str):
        parts = [p for p in jogo.replace(",", " ").split() if p.strip()]
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except Exception:
                pass
        nums = sorted(set(nums))
        return " ".join(str(n).zfill(2) for n in nums)

    # Se for lista/tupla/iterável
    try:
        nums = sorted(int(x) for x in jogo)
        return " ".join(str(n).zfill(2) for n in nums)
    except Exception:
        return ""


def remover_resultado_concursos(possibilidades, resultado_concursos):
    """
    Remove da lista/Series de possibilidades os jogos que já saíram nos concursos.

    - possibilidades: pode ser list, Series ou DataFrame (com uma coluna de jogos)
    - resultado_concursos: lista/Series/DataFrame com jogos sorteados

    Retorna: possibilidades sem os jogos já sorteados (mesmo tipo básico: Series).
    """

    # 1) Converte possibilidades para Series (cada linha = 1 jogo)
    if isinstance(possibilidades, pd.DataFrame):
        # pega a primeira coluna como jogos
        s_poss = possibilidades.iloc[:, 0].astype(str)
    elif isinstance(possibilidades, pd.Series):
        s_poss = possibilidades.astype(str)
    else:
        s_poss = pd.Series(possibilidades)

    # Normaliza possibilidades (string padrão)
    s_poss_norm = s_poss.apply(_normalizar_jogo)

    # 2) Converte resultados para lista normalizada
    if isinstance(resultado_concursos, pd.DataFrame):
        # tenta pegar D1..D15 se existir, senão primeira coluna
        cols_d = [c for c in resultado_concursos.columns if str(c).startswith("D")]
        if len(cols_d) >= 15:
            jogos_res = resultado_concursos[cols_d].values.tolist()
        else:
            jogos_res = resultado_concursos.iloc[:, 0].tolist()
    elif isinstance(resultado_concursos, pd.Series):
        jogos_res = resultado_concursos.tolist()
    else:
        jogos_res = list(resultado_concursos)

    jogos_res_norm = set(_normalizar_jogo(j) for j in jogos_res if j is not None)

    # remove strings vazias (segurança)
    jogos_res_norm.discard("")

    # 3) Remove: filtra ao invés de drop por índice (mais robusto)
    mask = ~s_poss_norm.isin(jogos_res_norm)
    removidos = s_poss[mask].reset_index(drop=True)

    return removidos
