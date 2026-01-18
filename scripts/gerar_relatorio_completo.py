from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def _agora_sp() -> str:
    return datetime.now().strftime("%d-%m-%Y")


def _read_text_if_exists(path: Path, max_lines: int | None = None) -> str:
    if not path.exists():
        return f"[NAO ENCONTRADO] {path}"
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if max_lines is not None:
        lines = txt.splitlines()[:max_lines]
        return "\n".join(lines)
    return txt


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera um TXT unico com tudo do dia (jogos + backtests + dashboards).")
    parser.add_argument("--data", required=False, help="DD-MM-YYYY (apenas para o cabecalho)")
    parser.add_argument("--jogos-ag", required=True, help="TXT jogos agressivo do dia")
    parser.add_argument("--jogos-cons", required=True, help="TXT jogos conservador do dia")
    parser.add_argument("--bt-ag-txt", required=False, help="TXT backtest agressivo (opcional)")
    parser.add_argument("--bt-cons-txt", required=False, help="TXT backtest conservador (opcional)")
    parser.add_argument("--dash-resumo", required=False, help="CSV resumo geral (opcional)")
    parser.add_argument("--dash-dist", required=False, help="CSV distribuicao acertos (opcional)")
    parser.add_argument("--out", required=False, help="Arquivo final TXT (opcional)")
    args = parser.parse_args()

    data = args.data or _agora_sp()
    out = Path(args.out) if args.out else Path("outputs") / f"relatorio_completo_{data}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    parts = []
    parts.append("=" * 46)
    parts.append("        RELATORIO COMPLETO DO WIZARD")
    parts.append(f"        DATA: {data}")
    parts.append("=" * 46)
    parts.append("")

    # Backtests (TXT já formatado)
    if args.bt_ag_txt:
        parts.append("------------ BACKTEST — MODO AGRESSIVO ------------")
        parts.append(_read_text_if_exists(Path(args.bt_ag_txt)))
        parts.append("")

    if args.bt_cons_txt:
        parts.append("------------ BACKTEST — MODO CONSERVADOR ------------")
        parts.append(_read_text_if_exists(Path(args.bt_cons_txt)))
        parts.append("")

    # Dashboards CSV (coloca “mastigado” no txt)
    if args.dash_resumo:
        parts.append("------------ DASHBOARD — RESUMO GERAL (CSV) ------------")
        parts.append(_read_text_if_exists(Path(args.dash_resumo), max_lines=200))
        parts.append("")

    if args.dash_dist:
        parts.append("------------ DASHBOARD — DISTRIBUICAO DE ACERTOS (CSV) ------------")
        parts.append(_read_text_if_exists(Path(args.dash_dist), max_lines=200))
        parts.append("")

    # Jogos (TXT do wizard)
    parts.append("------------ JOGOS GERADOS — AGRESSIVO ------------")
    parts.append(_read_text_if_exists(Path(args.jogos_ag)))
    parts.append("")
    parts.append("------------ JOGOS GERADOS — CONSERVADOR ------------")
    parts.append(_read_text_if_exists(Path(args.jogos_cons)))
    parts.append("")

    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"✅ Relatorio completo gerado: {out}")


if __name__ == "__main__":
    main()