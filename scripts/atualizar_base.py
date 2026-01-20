from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd


CAIXA_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"


def _fetch_json() -> Dict[str, Any]:
    """
    Busca a API da Caixa.
    Usa urllib para evitar dependência extra.
    """
    import urllib.request

    req = urllib.request.Request(
        CAIXA_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _parse_concursos(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    A API retorna 'listaResultado' com concursos recentes.
    Cada item tem 'numero' e 'listaDezenas' (strings).
    """
    lista = data.get("listaResultado", [])
    concursos: List[Dict[str, Any]] = []
    for item in lista:
        numero = int(item["numero"])
        dezenas = [int(x) for x in item["listaDezenas"]]
        dezenas = sorted(dezenas)
        row = {"Concurso": numero}
        for i, d in enumerate(dezenas, start=1):
            row[f"D{i}"] = d
        concursos.append(row)
    concursos.sort(key=lambda r: r["Concurso"])
    return concursos


def main() -> None:
    ap = argparse.ArgumentParser(description="Atualiza base de resultados da Lotofácil via API da Caixa.")
    ap.add_argument("--ultimos", type=int, default=1000, help="Quantos concursos manter (default: 1000)")
    ap.add_argument("--out", type=str, default="base/base_dados_atualizada.xlsx", help="Arquivo de saída .xlsx")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = _fetch_json()
    concursos = _parse_concursos(data)

    # A API normalmente não devolve TUDO (somente um bloco). Se quiser “histórico total”,
    # precisaria scrapping/arquivos oficiais. Aqui a ideia é manter últimos N rapidamente.
    n = int(args.ultimos)
    if n > 0 and len(concursos) > n:
        concursos = concursos[-n:]

    df = pd.DataFrame(concursos)

    # Normaliza colunas
    cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[cols].sort_values("Concurso").reset_index(drop=True)

    df.to_excel(out_path, index=False)
    print(f"✅ Base atualizada salva em: {out_path}")
    print(f"Total de concursos no arquivo: {len(df)}")
    print(f"Último concurso no arquivo: {int(df['Concurso'].max())}")


if __name__ == "__main__":
    main()