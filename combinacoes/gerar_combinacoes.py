import itertools
import pandas as pd
import os

def gerar_combinacoes():
    os.makedirs("combinacoes", exist_ok=True)

    print("Gerando combinações 15 dezenas entre 25... isso vai gerar 3.268.760 linhas!")

    comb = itertools.combinations(range(1, 26), 15)

    # Gravar em segmentos para economizar memória
    chunk_size = 50000
    buffer = []
    total = 0
    part = 1

    for c in comb:
        buffer.append(c)
        total += 1

        if len(buffer) >= chunk_size:
            df = pd.DataFrame(buffer)
            df.to_csv(f"combinacoes/combinacoes.csv", mode="a", header=not os.path.exists("combinacoes/combinacoes.csv"), index=False)
            buffer = []
            print(f"{total:,} combinações gravadas...")

    if buffer:
        df = pd.DataFrame(buffer)
        df.to_csv(f"combinacoes/combinacoes.csv", mode="a", header=not os.path.exists("combinacoes/combinacoes.csv"), index=False)

    print("Finalizado!")

if __name__ == "__main__":
    gerar_combinacoes()