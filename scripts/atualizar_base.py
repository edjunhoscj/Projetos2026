# scripts/atualizar_base.py
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import requests
except Exception as e:
    raise SystemExit("Faltou instalar requests. Rode: pip install requests") from e


BASE_DIR = Path("base")
BASE_DIR.mkdir(parents=True, exist_ok=True)

ARQ_ATUALIZADA = BASE_DIR / "base_dados_atualizada.xlsx"

# Endpoint mais comum (pode falhar em cloud/CI; deixei configurável por env)
DEFAULT_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"


def _http_get_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    headers = {
        # headers “de navegador” ajudam quando o servidor é mais restritivo
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://loterias.caixa.gov.br/",
        "Origin": "https://loterias.caixa.gov.br",
        "Connection": "keep-alive",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    # Se o host bloquear (401/403), isso vai aparecer aqui
    r.raise_for_status()
    return r.json()


def _fetch_concurso(api_base: str, concurso: Optional[int] = None) -> Dict[str, Any]:
    """
    Tenta:
      - {api_base}                  (último concurso)
      - {api_base}/{concurso}       (concurso específico)
    """
    if concurso is None:
        return _http_get_json(api_base)

    # alguns ambientes aceitam /{n}, outros aceitam ?concurso={n}
    try_urls = [
        f"{api_base}/{concurso}",
        f"{api_base}?concurso={concurso}",
    ]
    last_err = None
    for u in try_urls:
        try:
            return _http_get_json(u)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Falha ao buscar concurso {concurso}. Último erro: {last_err}")


def _normalize_dezenas(payload: Dict[str, Any]) -> List[int]:
    """
    A API costuma trazer 'listaDezenas' como strings ["01","02",...]
    """
    dezenas = payload.get("listaDezenas") or payload.get("dezenas") or payload.get("lista_dezenas")
    if not dezenas:
        return []
    out: List[int] = []
    for d in dezenas:
        try:
            out.append(int(str(d).strip()))
        except Exception:
            pass
    return out


def _row_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    n = payload.get("numero") or payload.get("concurso") or payload.get("numeroConcurso")
    if n is None:
        return None

    dezenas = _normalize_dezenas(payload)
    if len(dezenas) != 15:
        return None

    data = payload.get("dataApuracao") or payload.get("data") or payload.get("dataSorteio")
    # tenta padronizar data
    dt = None
    if data:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(str(data)[:10], fmt).strftime("%d-%m-%Y")
                break
            except Exception:
                continue

    row: Dict[str, Any] = {"Concurso": int(n), "Data": dt or ""}
    dezenas_sorted = sorted(dezenas)
    for i, dez in enumerate(dezenas_sorted, start=1):
        row[f"D{i}"] = int(dez)
    return row


def _load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["Concurso", "Data"] + [f"D{i}" for i in range(1, 16)])
    df = pd.read_excel(path)
    # normaliza nomes de colunas
    df.columns = [str(c).strip() for c in df.columns]
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ultimos", type=int, default=1000, help="Quantos últimos concursos manter")
    ap.add_argument(
        "--api",
        default=os.getenv("LOTOFACIL_API_URL", DEFAULT_API),
        help="Endpoint da API (pode sobrescrever via env LOTOFACIL_API_URL)",
    )
    args = ap.parse_args()

    df_old = _load_existing(ARQ_ATUALIZADA)
    last_old = int(df_old["Concurso"].max()) if (not df_old.empty and pd.notna(df_old["Concurso"]).any()) else 0

    print(f"📦 Base atual em disco: {ARQ_ATUALIZADA} (ultimo concurso = {last_old})")

    # 1) tenta descobrir o último concurso online
    try:
        payload_last = _fetch_concurso(args.api, None)
        row_last = _row_from_payload(payload_last)
        if not row_last:
            raise RuntimeError("Não consegui ler o último concurso (payload sem dezenas).")
        last_online = int(row_last["Concurso"])
        print(f"🌐 Último concurso online detectado: {last_online}")
    except Exception as e:
        print("⚠️ Falha ao acessar a API da CAIXA/endpoint.")
        print(f"⚠️ Motivo: {e}")
        print("✅ Vou manter a base existente (não vou sobrescrever).")
        return 0

    # 2) define intervalo pra buscar
    start = max(1, last_online - args.ultimos + 1)
    # se já temos parte local, podemos buscar só o “delta”
    if last_old >= start:
        start = last_old + 1

    new_rows: List[Dict[str, Any]] = []
    if start <= last_online:
        print(f"⬇️ Baixando concursos {start}..{last_online} (delta)")
        for n in range(start, last_online + 1):
            try:
                payload = _fetch_concurso(args.api, n)
                row = _row_from_payload(payload)
                if row:
                    new_rows.append(row)
            except Exception as e:
                # não quebra geral: loga e continua
                print(f"⚠️ Falhou concurso {n}: {e}")

    # 3) monta DF final
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_old.copy()

    # remove duplicados, ordena
    if "Concurso" in df.columns:
        df = df.drop_duplicates(subset=["Concurso"]).sort_values("Concurso").reset_index(drop=True)

    # sanity check: precisa ter pelo menos algumas linhas e D1..D15
    need_cols = ["Concurso", "Data"] + [f"D{i}" for i in range(1, 16)]
    for c in need_cols:
        if c not in df.columns:
            df[c] = ""

    # se ficou vazio, NÃO sobrescreve
    if df.empty or df["Concurso"].dropna().shape[0] == 0:
        print("❌ A base ficou vazia (0 concursos). Não vou sobrescrever o arquivo.")
        return 1

    # mantém só os últimos N
    if args.ultimos > 0 and df.shape[0] > args.ultimos:
        df = df.tail(args.ultimos).reset_index(drop=True)

    # salva
    df.to_excel(ARQ_ATUALIZADA, index=False)
    print(f"✅ Base atualizada salva em: {ARQ_ATUALIZADA}")
    print(f"✅ Total de concursos no arquivo: {df.shape[0]}")
    print(f"✅ Último concurso no arquivo: {int(df['Concurso'].max())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())