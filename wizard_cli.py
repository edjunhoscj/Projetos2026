import argparse
import random
import pandas as pd
from pathlib import Path
from itertools import combinations

BASE_ARQ = Path(__file__).parent / "base" / "base_limpa.xlsx"

def carregar_base():
    if not BASE_ARQ.exists():
        raise FileNotFoundError("Base não encontrada. Rode atualizar_base.py")
    return pd.read_excel(BASE_ARQ)

def ultimos_concursos(df, n):
    return df.tail(n)

def score_jogo(jogo, freq):
    return sum(freq.get(n, 0) for n in jogo)

def gerar_candidatos(freq, qtd=5000):
    dezenas = list(range(1, 26))
    candidatos = set()
    while len(candidatos) < qtd:
        jogo = tuple(sorted(random.sample(dezenas, 15)))
        candidatos.add(jogo)
    return list(candidatos)

def filtrar_modo(jogos, modo):
    if modo == "conservador":
        return [j for j in jogos if max_seq(j) <= 4]
    return jogos

def max_seq(jogo):
    m = c = 1
    for i in range(1, len(jogo)):
        if jogo[i] == jogo[i-1] + 1:
            c += 1
            m = max(m, c)
        else:
            c = 1
    return m

def cobertura(jogos):
    return len(set(n for j in jogos for n in j))

def selecionar_finais(jogos, freq, n=5):
    jogos = sorted(jogos, key=lambda j: score_jogo(j, freq), reverse=True)
    finais = []
    while jogos and len(finais) < n:
        j = jogos.pop(0)
        finais.append(j)
        jogos = [x for x in jogos if len(set(x) & set(j)) < 10]
    return finais

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ultimos", type=int, default=10)
    parser.add_argument("--modo", choices=["conservador", "agressivo"], default="conservador")
    parser.add_argument("--finais", type=int, default=5)
    args = parser.parse_args()

    df = carregar_base()
    ult = ultimos_concursos(df, args.ultimos)

    freq = {}
    for i in range(1, 16):
        for n in ult[f"D{i}"]:
            freq[n] = freq.get(n, 0) + 1

    candidatos = gerar_candidatos(freq)
    candidatos = filtrar_modo(candidatos, args.modo)
    finais = selecionar_finais(candidatos, freq, args.finais)

    print("\n🎯 JOGOS FINAIS\n")
    for i, j in enumerate(finais, 1):
        print(f"{i}: {j}")

    print("\n📊 Cobertura total:", cobertura(finais), "dezenas")

if __name__ == "__main__":
    main()
