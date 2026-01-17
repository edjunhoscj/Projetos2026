from __future__ import annotations

import argparse
from pathlib import Path


def read_text_safe(path: Path) -> str:
    if not path.exists():
        return f"[AVISO] Arquivo não encontrado: {path}\n"
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    p = argparse.ArgumentParser(description="Gera um relatório completo (TXT) juntando outputs do dia.")
    p.add_argument("--data", required=True, help="Data no formato DD-MM-YYYY_HHhMMmin (mesmo timestamp do workflow)")
    p.add_argument("--out", default="", help="Saída TXT. Se vazio, usa outputs/relatorio_completo_{data}.txt")

    args = p.parse_args()
    data = args.data.strip()

    out = Path(args.out) if args.out.strip() else Path(f"outputs/relatorio_completo_{data}.txt")
    out.parent.mkdir(parents=True, exist_ok=True)

    # Arquivos padrão do seu pipeline
    jogos_ag = Path(f"outputs/jogos_agressivo_{data}.txt")
    jogos_co = Path(f"outputs/jogos_conservador_{data}.txt")
    bt_ag_csv = Path(f"outputs/backtest_agressivo_{data}.csv")
    bt_co_csv = Path(f"outputs/backtest_conservador_{data}.csv")
    bt_ag_txt = Path(f"outputs/backtest_agressivo_{data}.txt")  # se você estiver gerando
    bt_co_txt = Path(f"outputs/backtest_conservador_{data}.txt")  # se você estiver gerando
    dashboard_resumo = Path("outputs/dashboard_resumo_geral.csv")
    dashboard_dist = Path("outputs/dashboard_distribuicao_acertos.csv")
    ranking_txt = Path("outputs/ranking_acumulado.txt")
    ranking_csv = Path("outputs/ranking_acumulado.csv")

    parts = []
    parts.append("==============================================")
    parts.append("        RELATÓRIO COMPLETO DO WIZARD")
    parts.append(f"        DATA: {data}")
    parts.append("==============================================\n")

    parts.append("------------ BACKTEST — AGRESSIVO (CSV) ------------")
    parts.append(read_text_safe(bt_ag_csv))
    parts.append("\n------------ BACKTEST — CONSERVADOR (CSV) ------------")
    parts.append(read_text_safe(bt_co_csv))

    parts.append("\n------------ BACKTEST FORMATADO (TXT) ------------")
    parts.append("AGRESSIVO:\n")
    parts.append(read_text_safe(bt_ag_txt))
    parts.append("\nCONSERVADOR:\n")
    parts.append(read_text_safe(bt_co_txt))

    parts.append("\n------------ DASHBOARD (RESUMO) ------------")
    parts.append(read_text_safe(dashboard_resumo))

    parts.append("\n------------ DASHBOARD (DISTRIBUIÇÃO) ------------")
    parts.append(read_text_safe(dashboard_dist))

    parts.append("\n------------ RANKING ACUMULADO ------------")
    parts.append(read_text_safe(ranking_txt))
    parts.append("\n(Ranking CSV)")
    parts.append(read_text_safe(ranking_csv))

    parts.append("\n------------ JOGOS GERADOS — AGRESSIVO ------------")
    parts.append(read_text_safe(jogos_ag))
    parts.append("\n------------ JOGOS GERADOS — CONSERVADOR ------------")
    parts.append(read_text_safe(jogos_co))

    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"OK: gerado {out}")


if __name__ == "__main__":
    main()