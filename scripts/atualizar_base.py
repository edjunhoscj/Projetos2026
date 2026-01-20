#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


API_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"


@dataclass
class Concurso:
    numero: int
    data: str  # normalmente vem "dd/mm/aaaa"
    dezenas: List[int]


def _get_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Wizard Lotofacil Diario)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _extrair_numero_concurso(payload: Dict[str, Any]) -> Optional[int]:
    # chaves mais comuns
    for k in ("numero", "numeroConcurso", "concurso", "nr_concurso"):
        v = payload.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
    return None


def _extrair_data(payload: Dict[str, Any]) -> str:
    for k in ("dataApuracao", "data", "dtApuracao", "dataStr"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extrair_dezenas(payload: Dict[str, Any]) -> List[int]:
    # servicebus2 costuma trazer dezenas como strings ["01","02",...]
    candidatos = []
    for k in ("listaDezenas", "listaDezenasOrdemSorteio", "dezenas", "resultado"):
        v = payload.get(k)
        if isinstance(v, list) and v:
            candidatos = v
            break
        if isinstance(v, str) and v.strip():
            # às vezes vem "01-02-03-..."
            if "-" in v:
                candidatos = v.split("-")
                break

    dezenas: List[int] = []
    for x in candidatos:
        try:
            dezenas.append(int(str(x).strip()))
        except Exception:
            pass

    dezenas = [d for d in dezenas if 1 <= d <= 25]
    dezenas = sorted(dezenas)
    return dezenas


def _buscar_concurso(n: int) -> Concurso:
    payload = _get_json(f"{API_BASE}/{n}")
    numero = _extrair_numero_concurso(payload) or n
    data = _extrair_data(payload)
    dezenas = _extrair_dezenas(payload)

    if len(dezenas) != 15:
        raise ValueError(
            f"Concurso {n}: esperado 15 dezenas, veio {len(dezenas)} -> {dezenas}. "
            "A API retornou um formato inesperado."
        )

    return Concurso(numero=numero, data=data, dezenas=dezenas)


def _buscar_ultimo_concurso() -> int:
    payload = _get_json(API_BASE)
    ultimo = _extrair_numero_concurso(payload)
    if not ultimo:
        raise ValueError("Não consegui identificar o número do último concurso na API.")
    return int(ultimo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ultimos", type=int, default=1000, help="Quantos concursos mais recentes baixar")
    ap.add_argument("--out", type=str, default="base/base_dados_atualizada.xlsx", help="Caminho do XLSX de saída")
    args = ap.parse_args()

    ultimos = max(1, int(args.ultimos))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"🔎 Consultando último concurso via API: {API_BASE}")
    ultimo = _buscar_ultimo_concurso()
    inicio = max(1, ultimo - ultimos + 1)

    print(f"📌 Último concurso: {ultimo}")
    print(f"📥 Baixando concursos de {inicio} até {ultimo} (total ~{ultimo - inicio + 1})")

    concursos: List[Concurso] = []
    erros: List[str] = []

    for n in range(inicio, ultimo + 1):
        try:
            c = _buscar_concurso(n)
            concursos.append(c)
        except Exception as e:
            erros.append(f"{n}: {e}")

    if not concursos:
        print("❌ Nenhum concurso foi baixado. Não vou sobrescrever sua base.")
        if erros:
            print("Erros (primeiros 10):")
            for line in erros[:10]:
                print(" -", line)
        return 1

    # monta DataFrame no formato que o resto do projeto espera
    rows = []
    for c in concursos:
        row = {"Concurso": c.numero, "Data": c.data}
        # D1..D15
        for i, dez in enumerate(sorted(c.dezenas), start=1):
            row[f"D{i}"] = int(dez)
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("Concurso").drop_duplicates(subset=["Concurso"], keep="last").reset_index(drop=True)

    # validações finais
    faltando = [col for col in ["Concurso"] + [f"D{i}" for i in range(1, 16)] if col not in df.columns]
    if faltando:
        print("❌ Estrutura inesperada ao montar DataFrame. Faltando colunas:", faltando)
        return 1

    if df["Concurso"].isna().all():
        print("❌ Coluna Concurso ficou vazia (NaN). Abortando.")
        return 1

    print(f"✅ Concursos carregados: {len(df)} | Primeiro: {df['Concurso'].min()} | Último: {df['Concurso'].max()}")
    df.to_excel(out_path, index=False)

    print(f"✅ Base atualizada salva em: {out_path.as_posix()}")

    if erros:
        print(f"⚠️ Atenção: {len(erros)} concursos falharam (mantive os que deram certo). Exibindo primeiros 10:")
        for line in erros[:10]:
            print(" -", line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())