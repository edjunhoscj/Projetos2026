from pathlib import Path

import pandas as pd

BASE_PATH = Path(__file__).resolve().parents[1] / "base"
ARQ_RAW = BASE_PATH / "base_raw.xlsx"
ARQ_LIMPO = BASE_PATH / "base_limpa.xlsx"


def gerar_base_limpa():
    if not ARQ_RAW.exists():
        raise FileNotFoundError(
            f"Arquivo RAW não encontrado: {ARQ_RAW}\n"
            "Rode antes: python scripts/atualizar_base.py"
        )

    print(f"🧹 Lendo base RAW: {ARQ_RAW}")
    df = pd.read_excel(ARQ_RAW)

    # Garante colunas esperadas
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base RAW: {faltando}")

    # Tipos corretos
    df["Concurso"] = df["Concurso"].astype(int)
    for i in range(1, 16):
        df[f"D{i}"] = df[f"D{i}"].astype(int)

    # Ordenar por concurso
    df = df.sort_values("Concurso").reset_index(drop=True)

    # Calcular Ciclo simples: reseta quando fecha 25 dezenas
    ciclo_atual = 1
    usadas = set()
    ciclos = []

    for _, row in df.iterrows():
        dezenas = {int(row[f"D{i}"]) for i in range(1, 16)}
        usadas |= dezenas
        ciclos.append(ciclo_atual)

        if len(usadas) == 25:
            usadas.clear()
            ciclo_atual += 1

    df["Ciclo"] = ciclos

    df.to_excel(ARQ_LIMPO, index=False)

    print("✅ Base limpa criada com sucesso:")
    print(f"📁 {ARQ_LIMPO}")
    print(f"Total de linhas: {len(df)}")
    print(f"Colunas: {list(df.columns)}")
    print()
    print(df.head(3))


if __name__ == "__main__":
    gerar_base_limpa()
