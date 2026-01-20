# scripts/gerar_base_limpa.py
from __future__ import annotations

from pathlib import Path
import pandas as pd


BASE_DIR = Path("base")
ARQ_ATUALIZADA = BASE_DIR / "base_dados_atualizada.xlsx"
ARQ_LIMPA = BASE_DIR / "base_limpa.xlsx"


def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in str(s).strip())


def main() -> int:
    if not ARQ_ATUALIZADA.exists():
        raise SystemExit(f"Arquivo não encontrado: {ARQ_ATUALIZADA}")

    df = pd.read_excel(ARQ_ATUALIZADA)
    df.columns = [str(c).strip() for c in df.columns]
    cols_norm = {_norm(c): c for c in df.columns}

    # tenta mapear concurso
    concurso_col = None
    for key in ["concurso", "numero", "numeroconcurso"]:
        if key in cols_norm:
            concurso_col = cols_norm[key]
            break
    if not concurso_col:
        raise ValueError(f"Coluna de concurso não encontrada. Colunas: {list(df.columns)}")

    # tenta mapear data
    data_col = None
    for key in ["data", "dataapuracao", "datasorteio"]:
        if key in cols_norm:
            data_col = cols_norm[key]
            break

    # dezenas: D1..D15 (ou variações)
    dezenas_cols = []
    for i in range(1, 16):
        key = _norm(f"D{i}")
        if key in cols_norm:
            dezenas_cols.append(cols_norm[key])

    # fallback: se vier como Dezena 1, Dezena 2...
    if len(dezenas_cols) != 15:
        dezenas_cols = []
        for i in range(1, 16):
            for pat in [f"dezena{i}", f"dezena_{i}", f"dezena {i}"]:
                if pat in cols_norm:
                    dezenas_cols.append(cols_norm[pat])
                    break

    if len(dezenas_cols) != 15:
        raise ValueError(
            f"Colunas faltando na base atualizada (preciso 15 dezenas). "
            f"Encontrei {len(dezenas_cols)}. Colunas: {list(df.columns)}"
        )

    out_cols = ["Concurso", "Data"] + [f"D{i}" for i in range(1, 16)]
    out = pd.DataFrame()
    out["Concurso"] = pd.to_numeric(df[concurso_col], errors="coerce").astype("Int64")
    out["Data"] = df[data_col].fillna("") if data_col else ""

    # coloca D1..D15 já como int
    for i, src in enumerate(dezenas_cols, start=1):
        out[f"D{i}"] = pd.to_numeric(df[src], errors="coerce").astype("Int64")

    out = out.dropna(subset=["Concurso"]).sort_values("Concurso").reset_index(drop=True)

    # sanity
    if out.empty:
        raise ValueError("Base limpa ficou vazia. Verifique se a base atualizada tem concursos válidos.")

    ARQ_LIMPA.parent.mkdir(parents=True, exist_ok=True)
    out.to_excel(ARQ_LIMPA, index=False)

    print(f"✅ Base limpa gerada em: {ARQ_LIMPA}")
    print(f"✅ Total concursos: {out.shape[0]} | Último: {int(out['Concurso'].max())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())