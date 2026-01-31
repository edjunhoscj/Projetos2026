from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# ✅ garante que a RAIZ do repo entre no sys.path (para achar wizard_brain.py)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wizard_brain import detectar_quentes_frias, construir_bandas  # noqa: E402


def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    df = pd.read_excel(base_path)
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base: {faltando}")

    df = df.sort_values("Concurso").reset_index(drop=True)
    return df


def recorte(df: pd.DataFrame, ultimos: int) -> pd.DataFrame:
    n = int(ultimos)
    if n <= 0:
        return df.copy()
    return df.tail(n).reset_index(drop=True)


def flatten_dezenas(df: pd.DataFrame) -> np.ndarray:
    cols = [f"D{i}" for i in range(1, 16)]
    return df[cols].to_numpy(dtype=int).ravel()


def contagens_1a25(vals: np.ndarray) -> Dict[int, int]:
    cont = {d: 0 for d in range(1, 26)}
    for v in vals:
        v = int(v)
        if 1 <= v <= 25:
            cont[v] += 1
    return cont


def atrasos(df: pd.DataFrame) -> Dict[int, int]:
    cols = [f"D{i}" for i in range(1, 16)]
    ult_idx = len(df) - 1
    last_pos = {d: None for d in range(1, 26)}

    for i in range(len(df)):
        row = df.loc[i, cols].astype(int).tolist()
        for d in row:
            last_pos[int(d)] = i

    atraso = {}
    for d in range(1, 26):
        if last_pos[d] is None:
            atraso[d] = 10**9
        else:
            atraso[d] = ult_idx - int(last_pos[d])
    return atraso


def faixa_nome(d: int) -> str:
    if 1 <= d <= 9:
        return "01-09"
    if 10 <= d <= 18:
        return "10-18"
    return "19-25"


def linha_5x5(d: int) -> int:
    return (d - 1) // 5 + 1


def coluna_5x5(d: int) -> int:
    return (d - 1) % 5 + 1


def quadrante_5x5(d: int) -> str:
    r = linha_5x5(d)
    c = coluna_5x5(d)

    if r == 3 or c == 3:
        return "CENTRO"
    top = r <= 2
    left = c <= 2
    if top and left:
        return "Q1"
    if top and not left:
        return "Q2"
    if (not top) and left:
        return "Q3"
    return "Q4"


def main() -> None:
    parser = argparse.ArgumentParser(description="Análise de padrões (bandas) - Lotofácil")
    parser.add_argument("--base", required=True, help="Caminho da base base_limpa.xlsx")
    parser.add_argument("--ultimos", type=int, default=300, help="Quantidade de concursos para recorte")
    parser.add_argument("--out", required=True, help="Arquivo TXT de saída")
    args = parser.parse_args()

    base_path = Path(args.base)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = carregar_base(base_path)
    df_r = recorte(df, args.ultimos)

    n = len(df_r)
    vals = flatten_dezenas(df_r)
    cont = contagens_1a25(vals)

    # ✅ bandas do wizard_brain
    bandas = construir_bandas(df, ultimos=args.ultimos)

    # ✅ quentes/frias no recorte
    estat = detectar_quentes_frias(df, ultimos=args.ultimos, top_quentes=7, top_frias=7)

    atraso = atrasos(df_r)

    # agregações
    faixa_count = {"01-09": 0, "10-18": 0, "19-25": 0}
    pares = 0
    impares = 0
    linhas = {i: 0 for i in range(1, 6)}
    colunas = {i: 0 for i in range(1, 6)}
    quadrantes = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "CENTRO": 0}

    for d in range(1, 26):
        k = cont[d]
        faixa_count[faixa_nome(d)] += k
        if d % 2 == 0:
            pares += k
        else:
            impares += k
        linhas[linha_5x5(d)] += k
        colunas[coluna_5x5(d)] += k
        quadrantes[quadrante_5x5(d)] += k

    total_bolas = max(1, n * 15)

    def pct(x: int) -> float:
        return 100.0 * x / total_bolas

    freq_sorted = sorted(((d, cont[d], cont[d] / max(1, n)) for d in range(1, 26)),
                         key=lambda x: x[1], reverse=True)
    atraso_sorted = sorted(((d, atraso[d]) for d in range(1, 26)), key=lambda x: x[1], reverse=True)

    out: List[str] = []
    out.append("==============================================")
    out.append("ANÁLISE DE PADRÕES (BANDAS) - LOTOFÁCIL")
    out.append("==============================================")
    out.append(f"Base: {base_path}")
    out.append(f"Recorte: últimos {args.ultimos} concursos (N efetivo = {n})")
    out.append("")

    out.append("---- BANDAS (quantis 10%..90%) ----")
    out.append(f"Faixa 01-09:   {bandas.f1_1a9[0]}..{bandas.f1_1a9[1]} dezenas por concurso")
    out.append(f"Faixa 10-18:   {bandas.f2_10a18[0]}..{bandas.f2_10a18[1]} dezenas por concurso")
    out.append(f"Faixa 19-25:   {bandas.f3_19a25[0]}..{bandas.f3_19a25[1]} dezenas por concurso")
    out.append(f"Pares:         {bandas.pares[0]}..{bandas.pares[1]} por concurso")
    out.append(f"Ímpares:       {bandas.impares[0]}..{bandas.impares[1]} por concurso")
    out.append("")

    out.append("---- DISTRIBUIÇÃO GERAL (no recorte) ----")
    out.append(f"Total de dezenas observadas: {total_bolas}")
    out.append(f"01-09:  {faixa_count['01-09']} ({pct(faixa_count['01-09']):.1f}%)")
    out.append(f"10-18:  {faixa_count['10-18']} ({pct(faixa_count['10-18']):.1f}%)")
    out.append(f"19-25:  {faixa_count['19-25']} ({pct(faixa_count['19-25']):.1f}%)")
    out.append(f"Pares:  {pares} ({pct(pares):.1f}%)")
    out.append(f"Ímpares:{impares} ({pct(impares):.1f}%)")
    out.append("")

    out.append("---- LINHAS (grade 5x5) ----")
    for i in range(1, 6):
        out.append(f"Linha {i}: {linhas[i]} ({pct(linhas[i]):.1f}%)")
    out.append("")

    out.append("---- COLUNAS (grade 5x5) ----")
    for i in range(1, 6):
        out.append(f"Coluna {i}: {colunas[i]} ({pct(colunas[i]):.1f}%)")
    out.append("")

    out.append("---- QUADRANTES (grade 5x5) ----")
    for k in ["Q1", "Q2", "Q3", "Q4", "CENTRO"]:
        out.append(f"{k}: {quadrantes[k]} ({pct(quadrantes[k]):.1f}%)")
    out.append("")

    out.append("---- QUENTES / FRIAS (no recorte) ----")
    out.append(f"Quentes (top 7): {sorted(estat.quentes)}")
    out.append(f"Frias   (top 7): {sorted(estat.frias)}")
    out.append("")

    out.append("---- TOP 10 FREQUÊNCIA (contagem | freq por concurso) ----")
    for d, c, fpc in freq_sorted[:10]:
        out.append(f"{d:02d}: {c:4d} | {fpc:.3f}/conc")
    out.append("")

    out.append("---- TOP 10 ATRASOS (quanto tempo sem sair) ----")
    for d, a in atraso_sorted[:10]:
        out.append(f"{d:02d}: atraso {a} concursos")
    out.append("")

    out.append("---- LISTA COMPLETA (dezena | contagem | atraso) ----")
    for d in range(1, 26):
        out.append(f"{d:02d} | {cont[d]:4d} | atraso {atraso[d]}")
    out.append("")

    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"OK: relatório gerado em {out_path}")


if __name__ == "__main__":
    main()