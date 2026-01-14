from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


BASE_LIMPA = Path("base") / "base_limpa.xlsx"
OUT_DIR = Path("combinacoes")
OUT_FILE = OUT_DIR / "combinacoes.csv"


def carregar_base() -> pd.DataFrame:
    if not BASE_LIMPA.exists():
        raise FileNotFoundError(f"Base limpa não encontrada em: {BASE_LIMPA}")

    df = pd.read_excel(BASE_LIMPA)

    col_dezenas = [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in col_dezenas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas de dezenas faltando na base limpa: {faltando}")

    return df


def _freq_dezenas(df: pd.DataFrame) -> dict[int, int]:
    """Conta frequência de 1..25 em todas as colunas D1..D15."""
    col_dezenas = [f"D{i}" for i in range(1, 16)]
    vals = df[col_dezenas].values.ravel()
    vals = vals[~pd.isna(vals)].astype(int)

    freq = {d: 0 for d in range(1, 26)}
    for v in vals:
        freq[int(v)] += 1
    return freq


def _normalizar(arr: np.ndarray) -> np.ndarray:
    a_min = float(arr.min())
    a_max = float(arr.max())
    if a_max == a_min:
        return np.ones_like(arr, dtype=float)
    return (arr - a_min) / (a_max - a_min)


def calcular_pesos_dezenas(df: pd.DataFrame) -> dict[int, float]:
    """
    Calcula um peso para cada dezena combinando:
    - frequência global
    - frequência recente (últimos 200)
    - tendência (freq. recente - freq. média últimos 500)
    """
    ultimos_recent = 200
    ultimos_media = 500

    todos = df
    recent = df.tail(ultimos_recent)
    media = df.tail(ultimos_media)

    freq_global = _freq_dezenas(todos)
    freq_recent = _freq_dezenas(recent)
    freq_media = _freq_dezenas(media)

    dezenas = np.arange(1, 26, dtype=int)

    arr_fg = np.array([freq_global[d] for d in dezenas], dtype=float)
    arr_fr = np.array([freq_recent[d] for d in dezenas], dtype=float)
    arr_fm = np.array([freq_media[d] for d in dezenas], dtype=float)

    arr_trend = arr_fr - arr_fm  # positivo = esquentando

    n_fg = _normalizar(arr_fg)
    n_fr = _normalizar(arr_fr)
    n_tr = _normalizar(arr_trend)

    # Combinação dos componentes
    # - 50%: frequência recente
    # - 30%: frequência global
    # - 20%: tendência
    pesos = {}
    for i, d in enumerate(dezenas):
        score = 0.5 * n_fr[i] + 0.3 * n_fg[i] + 0.2 * n_tr[i]
        # Nunca deixar peso zero
        pesos[int(d)] = float(max(score, 0.01))

    return pesos


def respeita_regras_basicas(jogo: list[int]) -> bool:
    """
    Regras simples para deixar o jogo mais "natural":
    - 6 a 9 pares
    - 7 a 10 dezenas entre 1 e 15 (baixas)
    - no máximo 4 dezenas consecutivas
    """
    jogo = sorted(jogo)

    pares = sum(1 for d in jogo if d % 2 == 0)
    if not (6 <= pares <= 9):
        return False

    baixas = sum(1 for d in jogo if d <= 15)
    if not (7 <= baixas <= 10):
        return False

    run = 1
    for i in range(1, len(jogo)):
        if jogo[i] == jogo[i - 1] + 1:
            run += 1
            if run > 4:
                return False
        else:
            run = 1

    return True


def preparar_ultimos(df: pd.DataFrame, n: int = 30) -> list[tuple[int, ...]]:
    """Lista de tuplas com os últimos n concursos para penalizar repetição."""
    col_dezenas = [f"D{i}" for i in range(1, 16)]
    ult = df.tail(n)

    tuplas: list[tuple[int, ...]] = []
    for _, row in ult.iterrows():
        dezenas = [int(row[c]) for c in col_dezenas]
        tuplas.append(tuple(sorted(dezenas)))
    return tuplas


def score_jogo(jogo: list[int],
               pesos: dict[int, float],
               ultimos_tuplas: list[tuple[int, ...]]) -> float:
    """
    Score do jogo:
    - soma dos pesos das dezenas
    - penalização por ser muito parecido com concursos recentes
    """
    base = sum(pesos[d] for d in jogo)

    jogo_set = set(jogo)
    max_overlap = 0
    for ult in ultimos_tuplas:
        inter = len(jogo_set.intersection(ult))
        if inter > max_overlap:
            max_overlap = inter

    # Se estiver muito parecido com um concurso recente, penaliza forte
    penalidade = max(0, max_overlap - 9)  # a partir de 10 repetidos
    score = base - 2.0 * penalidade

    return score


def gerar_combinacoes_inteligentes() -> None:
    df = carregar_base()
    print(f"Base limpa carregada com {len(df)} concursos.")

    pesos = calcular_pesos_dezenas(df)
    ultimos_tuplas = preparar_ultimos(df, n=30)

    OUT_DIR.mkdir(exist_ok=True)
    if OUT_FILE.exists():
        OUT_FILE.unlink()

    # Parâmetros da "Monte Carlo inteligente"
    total_candidatos = 80_000   # quantos jogos sortear no total
    manter_top = 15_000         # quantos jogos manter no CSV final

    dezenas_array = np.arange(1, 26, dtype=int)
    probs = np.array([pesos[int(d)] for d in dezenas_array], dtype=float)
    probs = probs / probs.sum()

    jogos_scored: list[tuple[float, list[int]]] = []

    print("Gerando jogos candidatos (Monte Carlo)...")
    gerados = 0
    while gerados < total_candidatos:
        # sorteia 15 dezenas sem reposição com probabilidade ponderada
        amostra = np.random.choice(dezenas_array, size=15, replace=False, p=probs)
        jogo = sorted(int(x) for x in amostra)

        if not respeita_regras_basicas(jogo):
            continue

        s = score_jogo(jogo, pesos, ultimos_tuplas)
        jogos_scored.append((s, jogo))
        gerados += 1

        if gerados % 10_000 == 0:
            print(f"  {gerados} jogos válidos gerados...")

    print("Ordenando por score e selecionando o top...")
    # ordena por score decrescente
    jogos_scored.sort(key=lambda x: x[0], reverse=True)
    jogos_top = jogos_scored[:manter_top]

    # monta DataFrame com colunas D1..D15
    dados = {f"D{i}": [] for i in range(1, 16)}
    for _, jogo in jogos_top:
        for i, d in enumerate(jogo, start=1):
            dados[f"D{i}"].append(d)

    df_out = pd.DataFrame(dados)
    df_out.to_csv(OUT_FILE, index=False)

    print(f"✅ Geradas {len(df_out)} combinações inteligentes em: {OUT_FILE}")


if __name__ == "__main__":
    gerar_combinacoes_inteligentes()