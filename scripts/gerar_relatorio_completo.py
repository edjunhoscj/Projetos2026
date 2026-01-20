from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return f"[ARQUIVO NÃO ENCONTRADO: {path}]"
    txt = path.read_text(encoding="utf-8", errors="ignore")
    # detecta ponteiro git-lfs
    if txt.strip().startswith("version https://git-lfs.github.com/spec/v1"):
        return (
            "⚠️ ESTE ARQUIVO APARECE COMO PONTEIRO DO GIT-LFS (não é o conteúdo real).\n"
            "Isso acontece quando o CSV foi trackeado por LFS.\n"
            "Solução: tirar esse arquivo do LFS ou baixar o artefato real.\n\n"
            + txt
        )
    return txt


def _safe_read_csv(path: Path) -> str:
    if not path.exists():
        return f"[CSV NÃO ENCONTRADO: {path}]"
    try:
        df = pd.read_csv(path)
        return df.to_string(index=False)
    except Exception as e:
        return f"[ERRO LENDO CSV {path}: {e}]"


def main() -> None:
    ap = argparse.ArgumentParser(description="Monta um relatório completo TXT único.")
    ap.add_argument("--data", required=True, help="Data DD-MM-YYYY")
    ap.add_argument("--jogos-ag", required=True)
    ap.add_argument("--jogos-cons", required=True)
    ap.add_argument("--bt-ag-txt", required=True)
    ap.add_argument("--bt-cons-txt", required=True)
    ap.add_argument("--dash-resumo", required=True)
    ap.add_argument("--dash-dist", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("==============================================")
    lines.append("RELATÓRIO COMPLETO DO WIZARD")
    lines.append(f"DATA: {args.data}")
    lines.append("==============================================\n")

    lines.append("------------ BACKTEST — MODO AGRESSIVO ------------")
    lines.append(_safe_read_text(Path(args.bt_ag_txt)))
    lines.append("\n------------ BACKTEST — MODO CONSERVADOR ------------")
    lines.append(_safe_read_text(Path(args.bt_cons_txt)))

    lines.append("\n------------ DASHBOARD — RESUMO GERAL (CSV) ------------")
    lines.append(_safe_read_csv(Path(args.dash_resumo)))
    lines.append("\n------------ DISTRIBUIÇÃO DE ACERTOS (CSV) ------------")
    lines.append(_safe_read_csv(Path(args.dash_dist)))

    lines.append("\n------------ JOGOS GERADOS — AGRESSIVO ------------")
    lines.append(_safe_read_text(Path(args.jogos_ag)))
    lines.append("\n------------ JOGOS GERADOS — CONSERVADOR ------------")
    lines.append(_safe_read_text(Path(args.jogos_cons)))

    # interpretação: pega melhores do CSV do backtest agressivo (se existir)
    try:
        # tenta achar CSV irmão do TXT
        bt_ag_csv = Path(args.bt_ag_txt).with_suffix(".csv")
        if bt_ag_csv.exists():
            df = pd.read_csv(bt_ag_csv).sort_values(["media_acertos", "max_acertos"], ascending=[False, False])
            best = df.iloc[0]
            lines.append("\n============ INTERPRETAÇÃO DO MELHOR DO DIA ============")
            lines.append(f"Melhor jogo do modo agressivo: jogo {best['jogo']}")
            lines.append(f"Média: {float(best['media_acertos']):.2f}")
            lines.append(f"Máximo atingido: {best['max_acertos']}")
            lines.append(f"Mínimo atingido: {best['min_acertos']}")
    except Exception:
        pass

    lines.append("\n============ RECOMENDAÇÃO FINAL ============")
    lines.append("✔ Use o melhor jogo do agressivo para explosão")
    lines.append("✔ Combine com o mais estável do conservador")
    lines.append("✔ Para apostar só 1 jogo: use o melhor agressivo")
    lines.append("✔ Para 3 jogos: melhor agressivo + mais estável conservador + melhor equilíbrio")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Relatório completo salvo: {out}")


if __name__ == "__main__":
    main()