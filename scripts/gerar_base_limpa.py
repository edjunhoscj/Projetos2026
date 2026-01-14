from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1] / "base"
ARQ_RAW = BASE_DIR / "base_raw.xlsx"      # base “crua” vinda da Caixa (se você passar a usar)
ARQ_LIMPA = BASE_DIR / "base_limpa.xlsx"  # base já preparada para o wizard


def gerar_base_limpa() -> None:
    print("========================================")
    print("      SCRIPT GERAR_BASE_LIMPA.PY")
    print("========================================")

    print(f"📂 Pasta base: {BASE_DIR}")

    # 1) Escolhe o arquivo de entrada
    if ARQ_RAW.exists():
        origem = ARQ_RAW
        print(f"🔎 Usando base RAW como entrada: {origem}")
    elif ARQ_LIMPA.exists():
        # fallback: usa a própria base_limpa como entrada (caso você ainda não tenha separado RAW/LIMPA)
        origem = ARQ_LIMPA
        print(f"🔎 Base RAW não encontrada. Usando base_limpa como entrada: {origem}")
    else:
        msg = (
            "❌ Nenhum arquivo de base encontrado.\n"
            f"Esperado: {ARQ_RAW} ou {ARQ_LIMPA}"
        )
        raise FileNotFoundError(msg)

    # 2) Lê o Excel
    print("📥 Lendo arquivo de entrada...")
    df = pd.read_excel(origem)

    print(f"✅ Base carregada com {len(df)} concursos.")
    print(f"Colunas disponíveis: {list(df.columns)}")

    # 3) Garante colunas de dezenas (D1..D15)
    dezenas_cols = [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in dezenas_cols if c not in df.columns]
    if faltando:
        raise ValueError(
            "❌ Colunas de dezenas faltando na base: "
            f"{faltando}. Verifique o formato do arquivo vindo da Caixa."
        )

    # 4) Calcula coluna Ciclo (se ainda não existir)
    if "Ciclo" not in df.columns:
        print("➕ Coluna 'Ciclo' não encontrada. Calculando ciclos...")
        ciclo = 1
        usadas: set[int] = set()
        ciclos: list[int] = []

        for _, row in df[dezenas_cols].iterrows():
            usadas |= set(int(x) for x in row.values)
            if len(usadas) == 25:
                usadas.clear()
                ciclo += 1
            ciclos.append(ciclo)

        df["Ciclo"] = ciclos
        print("✅ Coluna 'Ciclo' adicionada.")
    else:
        print("ℹ️ Coluna 'Ciclo' já existe. Mantendo valores atuais.")

    # 5) Salva base_limpa.xlsx (arquivo final que o wizard usa)
    BASE_DIR.mkdir(exist_ok=True)
    df.to_excel(ARQ_LIMPA, index=False)

    print("========================================")
    print(f"💾 Base limpa gerada com sucesso:")
    print(f"   Arquivo: {ARQ_LIMPA}")
    print(f"   Linhas:  {len(df)}")
    print("========================================")


if __name__ == "__main__":
    gerar_base_limpa()