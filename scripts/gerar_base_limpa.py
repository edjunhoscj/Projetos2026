#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


COLS_DEZENAS = [f"D{i}" for i in range(1, 16)]
COLS_OBRIG = ["Concurso"] + COLS_DEZENAS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="base/base_dados_atualizada.xlsx", help="Base bruta (XLSX)")
    ap.add_argument("--out", default="base/base_limpa.xlsx", help="Base limpa (XLSX)")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not inp.exists():
        print(f"❌ Arquivo de entrada não existe: {inp.as_posix()}")
        return 1

    df = pd.read_excel(inp)

    # normaliza nomes de colunas (evita espaços)
    df.columns = [str(c).strip() for c in df.columns]

    faltando = [c for c in COLS_OBRIG if c not in df.columns]
    if faltando:
        print(f"❌ Colunas faltando na base atualizada: {faltando}")
        print("📌 Colunas encontradas:", df.columns.tolist())
        return 1

    # garante tipos numéricos
    df["Concurso"] = pd.to_numeric(df["Concurso"], errors="coerce")
    for c in COLS_DEZENAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["Concurso"] + COLS_DEZENAS).copy()

    # concurso inteiro
    df["Concurso"] = df["Concurso"].astype(int)

    # dezenas inteiras 1..25
    for c in COLS_DEZENAS:
        df[c] = df[c].astype(int)

    for c in COLS_DEZENAS:
        if not df[c].between(1, 25).all():
            ruins = df.loc[~df[c].between(1, 25), ["Concurso", c]].head(10)
            print(f"❌ Encontrei dezenas fora de 1..25 na coluna {c}. Exemplos:")
            print(ruins.to_string(index=False))
            return 1

    # ordena e remove duplicados
    df = df.sort_values("Concurso").drop_duplicates(subset=["Concurso"], keep="last").reset_index(drop=True)

    # salva
    df.to_excel(out, index=False)
    print(f"✅ Base limpa gerada: {out.as_posix()} | concursos: {len(df)} | último: {df['Concurso'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())