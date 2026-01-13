import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "base" / "base_limpa.xlsx"

def backtest(jogos, janela=100):
    df = pd.read_excel(BASE)
    resultados = []

    for _, row in df.tail(janela).iterrows():
        sorteio = set(row[f"D{i}"] for i in range(1, 16))
        for jogo in jogos:
            acertos = len(sorteio & set(jogo))
            resultados.append(acertos)

    return resultados

if __name__ == "__main__":
    # exemplo rápido
    jogos = [
        {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15}
    ]
    r = backtest(jogos)
    print("Média de acertos:", sum(r)/len(r))
    print(">=11:", sum(1 for x in r if x >= 11))
