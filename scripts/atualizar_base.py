from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests

# Pasta base/ e arquivo final
BASE_DIR = Path(__file__).resolve().parents[1] / "base"
BASE_DIR.mkdir(exist_ok=True)

ARQ_BASE = BASE_DIR / "base_limpa.xlsx"

# API agregada (já traz todos os concursos da Lotofácil)
URL_CAIXA = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"


def baixar_todos_concursos() -> list[dict]:
    """
    Baixa TODOS os concursos da API agregada em UMA chamada.
    Normalmente é bem rápido (alguns segundos).
    """
    print(f"📥 Baixando dados da API em {URL_CAIXA} ...")
    resp = requests.get(URL_CAIXA, timeout=60)
    resp.raise_for_status()
    dados = resp.json()
    print(f"✅ Recebidos {len(dados)} concursos da API.")
    return dados


def montar_dataframe(dados: list[dict]) -> pd.DataFrame:
    """
    Monta um DataFrame com colunas:
    Concurso, D1..D15, Ciclo (ciclo simples de 25 dezenas).
    """
    registros: list[dict] = []

    for d in dados:
        dezenas = sorted(d["dezenas"])
        registro = {
            "Concurso": d["concurso"],
            **{f"D{i+1}": dezenas[i] for i in range(15)},
        }
        registros.append(registro)

    df = (
        pd.DataFrame(registros)
        .sort_values("Concurso")
        .reset_index(drop=True)
    )

    # Cálculo de ciclo simples: reseta quando cobrir as 25 dezenas
    ciclo = 1
    usadas: set[int] = set()
    ciclos: list[int] = []

    cols_dezenas = [f"D{i}" for i in range(1, 16)]
    for _, row in df[cols_dezenas].iterrows():
        usadas |= {int(x) for x in row.values}
        if len(usadas) == 25:
            usadas.clear()
            ciclo += 1
        ciclos.append(ciclo)

    df["Ciclo"] = ciclos
    return df


def atualizar_base(ultimos: int | None = None) -> None:
    """
    Atualiza base_limpa.xlsx.

    - Baixa todos os concursos da API agregada.
    - Monta o DataFrame com colunas Concurso, D1..D15, Ciclo.
    - Se `ultimos` for informado, mantém APENAS os últimos N concursos.
    - Salva em base/base_limpa.xlsx.
    """
    print("========================================")
    print("      ATUALIZAR_BASE.PY (AGREGADA)      ")
    print("========================================")

    dados = baixar_todos_concursos()
    df = montar_dataframe(dados)

    total = len(df)
    print(f"📊 Total de concursos disponíveis: {total}")

    if ultimos is not None and ultimos > 0 and ultimos < total:
        df = df.tail(ultimos).reset_index(drop=True)
        print(f"✂ Mantendo apenas os últimos {ultimos} concursos.")
    else:
        print("ℹ Mantendo TODOS os concursos recebidos.")

    if ARQ_BASE.exists():
        df_antigo = pd.read_excel(ARQ_BASE)
        ultimo_antigo = int(df_antigo["Concurso"].max())
        print(f"📁 Base antiga ia até o concurso: {ultimo_antigo}")

    ultimo_novo = int(df["Concurso"].max())
    primeiro_novo = int(df["Concurso"].min())
    print(f"📁 Nova base: de {primeiro_novo} até {ultimo_novo}")

    df.to_excel(ARQ_BASE, index=False)

    print("========================================")
    print(f"💾 Base atualizada salva em: {ARQ_BASE}")
    print(f"   Total de linhas na base: {len(df)}")
    print("========================================")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Atualiza a base da Lotofácil a partir da API agregada.\n"
            "Use --ultimos N para manter apenas os últimos N concursos."
        )
    )
    parser.add_argument(
        "--ultimos",
        type=int,
        default=None,
        help="Se informado, mantém apenas os últimos N concursos na base.",
    )
    args = parser.parse_args()

    atualizar_base(args.ultimos)


if __name__ == "__main__":
    main()