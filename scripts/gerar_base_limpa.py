from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera base limpa padronizada (Concurso + D1..D15).")
    ap.add_argument("--in", dest="inp", default="base/base_dados_atualizada.xlsx")
    ap.add_argument("--out", default="base/base_limpa.xlsx")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not inp.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {inp}")

    df = pd.read_excel(inp)

    cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in cols if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base atualizada: {faltando}")

    df = df[cols].copy()

    # tipos
    df["Concurso"] = df["Concurso"].astype(int)
    for i in range(1, 16):
        df[f"D{i}"] = df[f"D{i}"].astype(int)

    # remove duplicados por concurso, mantendo o mais recente
    df = df.sort_values("Concurso").drop_duplicates(subset=["Concurso"], keep="last")
    df = df.sort_values("Concurso").reset_index(drop=True)

    out_tmp = out.with_suffix(".tmp.xlsx")
    df.to_excel(out_tmp, index=False)
    out_tmp.replace(out)

    print(f"✅ Base limpa criada com sucesso: {out}")
    print(f"Total de linhas: {len(df)}")
    print(f"Último concurso: {int(df['Concurso'].max())}")


if __name__ == "__main__":
    main()