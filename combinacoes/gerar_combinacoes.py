from __future__ import annotations

import math
from pathlib import Path
from typing import List, Tuple, Set

import numpy as np
import pandas as pd


BASE_LIMPA_PATH = Path("base/base_limpa.xlsx")
SAIDA_INTELIGENTE = Path("combinacoes/combinacoes_inteligentes.csv")


def carregar_base() -> pd.DataFrame:
    if not BASE_LIMPA_PATH.exists():
        raise FileNotFoundError(f"Base limpa não encontrada em: {BASE_LIMPA_PATH}")
    df = pd.read_excel(BASE_LIMPA_PATH)
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base limpa: {faltando}")
    if "Concurso" in df.columns:
        df = df.sort_values("Concurso")
    return df.reset_index(drop=True)


def calcular_frequencias(df: pd.DataFrame, ultimos_n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """
    Retorna (freq_total, freq_recent) para dezenas 1..25.
    """
    cols_dezenas = [f"D{i}" for i in range(1, 16)]
    todos = df[cols_dezenas].to_numpy(dtype=int)

    freq_total = np.zeros(26, dtype=int)
    for linha in todos:
        for d in linha:
            freq_total[d] += 1

    recent = df.tail(ultimos_n)[cols_dezenas].to_numpy(dtype=int)
    freq_recent = np.zeros(26, dtype=int)
    for linha in recent:
        for d in linha:
            freq_recent[d] += 1

    return freq_total, freq_recent


def montar_probabilidades(freq_total: np.ndarray, freq_recent: np.ndarray) -> np.ndarray:
    dezenas = np.arange(1, 26)

    ft = freq_total[dezenas].astype(float)
    fr = freq_recent[dezenas].astype(float)

    # suavização para evitar zero
    ft = ft + 1.0
    fr = fr + 1.0

    # mistura: dá mais peso para os últimos concursos, mas não ignora o histórico
    alpha = 0.7
    beta = 0.3

    mix = alpha * fr / fr.sum() + beta * ft / ft.sum()

    # leve empurrão para dezenas altas (20–25)
    bonus_altos = np.array([0.0 if d < 20 else 0.05 for d in dezenas])
    mix = mix + bonus_altos

    mix = mix / mix.sum()
    return mix


def respeita_sequencia_maxima(dezenas: List[int], max_seq_run: int = 4) -> bool:
    dezenas = sorted(dezenas)
    run = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i - 1] + 1:
            run += 1
            if run > max_seq_run:
                return False
        else:
            run = 1
    return True


def gerar_combinacoes_inteligentes(
    n_jogos: int,
    prob: np.ndarray,
    max_seq_run: int = 4,
) -> List[Tuple[int, ...]]:
    dezenas = np.arange(1, 26)
    jogos: List[Tuple[int, ...]] = []
    seen: Set[Tuple[int, ...]] = set()

    tentativas = 0
    max_tentativas = n_jogos * 50  # folga razoável

    while len(jogos) < n_jogos and tentativas < max_tentativas:
        tentativas += 1

        escolha = np.random.choice(
            dezenas,
            size=15,
            replace=False,
            p=prob,
        )
        escolha_lista = sorted(int(x) for x in escolha)
        jogo = tuple(escolha_lista)

        if jogo in seen:
            continue
        if not respeita_sequencia_maxima(escolha_lista, max_seq_run=max_seq_run):
            continue

        # regra simples de equilíbrio: não deixar MUITOS números muito baixos
        qtd_baixos = sum(1 for d in escolha_lista if d <= 10)
        if qtd_baixos > 9:
            continue

        seen.add(jogo)
        jogos.append(jogo)

    return jogos


def salvar_jogos(jogos: List[Tuple[int, ...]], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        for jogo in jogos:
            linha = " ".join(f"{d:02d}" for d in jogo)
            f.write(linha + "\n")


def main() -> None:
    print("📊 Carregando base limpa...")
    df = carregar_base()

    print("📈 Calculando frequências...")
    freq_total, freq_recent = calcular_frequencias(df, ultimos_n=200)
    prob = montar_probabilidades(freq_total, freq_recent)

    # tamanho do arquivo "inteligente"
    n_jogos = 20000  # ~1 MB de texto

    print(f"🎲 Gerando {n_jogos} combinações inteligentes...")
    jogos = gerar_combinacoes_inteligentes(n_jogos=n_jogos, prob=prob, max_seq_run=4)

    print(f"💾 Salvando em {SAIDA_INTELIGENTE} (total: {len(jogos)} jogos)...")
    salvar_jogos(jogos, SAIDA_INTELIGENTE)

    print("✅ Combinações inteligentes geradas com sucesso.")


if __name__ == "__main__":
    main()