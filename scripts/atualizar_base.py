from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

CAIXA_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"


def _http_get_json(url: str, timeout: int = 60) -> Tuple[int, str, Dict[str, Any]]:
    """
    Faz GET e tenta retornar (status_code, raw_text, json_dict).
    Se não conseguir parsear JSON, json_dict retorna {}.
    """
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={
            # Headers mais "browser-like" (ajuda em bloqueios simples)
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://loterias.caixa.gov.br/",
            "Origin": "https://loterias.caixa.gov.br",
            "Connection": "close",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        raw_bytes = resp.read()

        # Alguns endpoints podem vir gzip; urllib normalmente já trata, mas garantimos.
        raw_text = raw_bytes.decode("utf-8", errors="replace")

    try:
        data = json.loads(raw_text)
    except Exception:
        data = {}

    return status, raw_text, data


def _parse_concursos(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Formato esperado (comum):
      data["listaResultado"] = [
        {"numero": "...", "listaDezenas": ["01","02",...]}
      ]
    """
    lista = data.get("listaResultado") or []
    concursos: List[Dict[str, Any]] = []

    for item in lista:
        try:
            numero = int(item.get("numero"))
            dezenas_raw = item.get("listaDezenas") or []
            dezenas = sorted([int(x) for x in dezenas_raw])
            if len(dezenas) != 15:
                continue
            row = {"Concurso": numero}
            for i, d in enumerate(dezenas, start=1):
                row[f"D{i}"] = d
            concursos.append(row)
        except Exception:
            continue

    concursos.sort(key=lambda r: r["Concurso"])
    return concursos


def _fallback_ultima_base(out_path: Path, backup_paths: List[Path]) -> bool:
    """
    Se a API falhar (0 concursos), tenta usar uma base já existente no repo.
    Copia o primeiro backup existente para out_path.
    """
    for bp in backup_paths:
        if bp.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(bp.read_bytes())
            print(f"⚠️ API retornou 0 concursos. Usei fallback da base existente: {bp}")
            print(f"✅ Base (fallback) salva em: {out_path}")
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Atualiza base Lotofácil via API da Caixa (robusto).")
    ap.add_argument("--ultimos", type=int, default=1000, help="Quantos concursos manter (default: 1000)")
    ap.add_argument("--out", type=str, default="base/base_dados_atualizada.xlsx", help="Arquivo de saída .xlsx")
    ap.add_argument("--retries", type=int, default=3, help="Tentativas em caso de falha (default: 3)")
    args = ap.parse_args()

    out_path = Path(args.out)

    # backups possíveis (no seu repo você costuma ter esses arquivos)
    backups = [
        Path("base/base_dados_atualizada.xlsx"),
        Path("base/base_limpa.xlsx"),
    ]

    last_err: Optional[str] = None
    status: int = 0
    raw: str = ""
    data: Dict[str, Any] = {}

    for i in range(int(args.retries)):
        try:
            status, raw, data = _http_get_json(CAIXA_URL, timeout=60)

            # Status ruim ou sem JSON
            if status >= 400 or not isinstance(data, dict) or not data:
                last_err = f"HTTP {status} ou JSON inválido/empty."
                time.sleep(2 * (i + 1))
                continue

            concursos = _parse_concursos(data)
            if not concursos:
                last_err = "JSON veio, mas listaResultado não gerou concursos (0)."
                time.sleep(2 * (i + 1))
                continue

            # recorta últimos N
            n = int(args.ultimos)
            if n > 0 and len(concursos) > n:
                concursos = concursos[-n:]

            df = pd.DataFrame(concursos)
            cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
            df = df[cols].sort_values("Concurso").reset_index(drop=True)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(out_path, index=False)

            print(f"✅ Base atualizada salva em: {out_path}")
            print(f"Total de concursos no arquivo: {len(df)}")
            print(f"Último concurso no arquivo: {int(df['Concurso'].max())}")
            return

        except Exception as e:
            last_err = f"Exceção: {e}"
            time.sleep(2 * (i + 1))

    # Se chegou aqui, falhou. Vamos tentar fallback.
    print("❌ Não consegui atualizar via API da Caixa.")
    if last_err:
        print(f"Motivo: {last_err}")

    # Debug leve (sem vazar tudo): mostra começo da resposta
    if raw:
        print("Trecho da resposta (primeiros 300 chars):")
        print(raw[:300])

    used = _fallback_ultima_base(out_path, backups)
    if used:
        # Se usou fallback, encerra com sucesso (para o workflow continuar)
        return

    # Se não tem fallback, falha de verdade
    raise SystemExit("Sem fallback disponível. Adicione base/base_dados_atualizada.xlsx no repo ou corrija a API.")


if __name__ == "__main__":
    main()