from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime
import glob

import pandas as pd


def _fmt_float(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


def _read_text(path: Path) -> str:
    if not path.exists():
        return f"(arquivo não encontrado: {path})\n"
    return path.read_text(encoding="utf-8", errors="replace")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {path}")
    return pd.read_csv(path)


def _best_row(df: pd.DataFrame):
    # regra: maior media_acertos, desempate por max_acertos, depois menor min_acertos
    for col in ["media_acertos", "max_acertos", "min_acertos"]:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente no backtest: {col}")
    tmp = df.copy()
    tmp["min_acertos"] = pd.to_numeric(tmp["min_acertos"], errors="coerce").fillna(0)
    tmp["max_acertos"] = pd.to_numeric(tmp["max_acertos"], errors="coerce").fillna(0)
    tmp["media_acertos"] = pd.to_numeric(tmp["media_acertos"], errors="coerce").fillna(0)
    tmp = tmp.sort_values(["media_acertos", "max_acertos", "min_acertos"], ascending=[False, False, True])
    return tmp.iloc[0]


def main():
    p = argparse.ArgumentParser(description="Gera relatório diário completo (um TXT com tudo).")
    p.add_argument("--data", default=None, help="Data (dd-mm-aaaa). Se vazio, usa hoje.")
    p.add_argument("--timestamp", default=None, help="Timestamp no formato dd-mm-aaaa_HHhMMmin. Se vazio, auto-detecta o mais recente.")
    p.add_argument("--out", required=True, help="Caminho do TXT de saída.")
    args = p.parse_args()

    outputs = Path("outputs")
    outputs.mkdir(parents=True, exist_ok=True)

    # data
    if args.data:
        dia = args.data
    else:
        dia = datetime.now().strftime("%d-%m-%Y")

    # timestamp
    if args.timestamp:
        ts = args.timestamp
    else:
        # pega o backtest agressivo mais recente
        cand = sorted(glob.glob(str(outputs / "backtest_agressivo_*.csv")))
        if not cand:
            raise FileNotFoundError("Não achei outputs/backtest_agressivo_*.csv para auto-detectar timestamp.")
        ts = Path(cand[-1]).stem.replace("backtest_agressivo_", "")

    # arquivos do dia
    ag_csv = outputs / f"backtest_agressivo_{ts}.csv"
    co_csv = outputs / f"backtest_conservador_{ts}.csv"
    ag_txt = outputs / f"jogos_agressivo_{ts}.txt"
    co_txt = outputs / f"jogos_conservador_{ts}.txt"
    mast_txt = outputs / f"relatorio_mastigado_{ts}.txt"

    # dashboard outputs (se existirem)
    dash_resumo = outputs / "dashboard_resumo_geral.csv"
    dash_dist = outputs / "dashboard_distribuicao_acertos.csv"

    # ranking (se existir)
    ranking_txt = outputs / "ranking_acumulado.txt"
    ranking_csv = outputs / "ranking_acumulado.csv"

    # carrega backtests
    df_ag = _read_csv(ag_csv)
    df_co = _read_csv(co_csv)

    best_ag = _best_row(df_ag)
    best_co = _best_row(df_co)

    # relatório
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("==============================================")
    lines.append("        RELATÓRIO DIÁRIO DO DESEMPENHO")
    lines.append(f"        DATA: {dia}")
    lines.append(f"        TIMESTAMP: {ts}")
    lines.append("==============================================\n")

    # resumo executivo (5 linhas)
    lines.append("RESUMO EXECUTIVO (5 linhas)")
    lines.append(f"1) Melhor AGRESSIVO: jogo {best_ag.get('Jogo', best_ag.get('jogo', '?'))} | média={_fmt_float(best_ag['media_acertos'])} | max={int(best_ag['max_acertos'])} | min={int(best_ag['min_acertos'])}")
    lines.append(f"2) Melhor CONSERVADOR: jogo {best_co.get('Jogo', best_co.get('jogo', '?'))} | média={_fmt_float(best_co['media_acertos'])} | max={int(best_co['max_acertos'])} | min={int(best_co['min_acertos'])}")
    lines.append("3) Se apostar 1 jogo: use o melhor do AGRESSIVO (explosão).")
    lines.append("4) Se apostar 3 jogos: melhor AGRESSIVO + melhor CONSERVADOR + o mais estável (maior média e menor variação).")
    lines.append("5) Confira o ranking acumulado para ver padrões que repetem boa performance.\n")

    # backtests “mastigados” (tabelas)
    lines.append("------------ BACKTEST — MODO AGRESSIVO ------------")
    lines.append(df_ag.to_string(index=False))
    lines.append("\n------------ BACKTEST — MODO CONSERVADOR ------------")
    lines.append(df_co.to_string(index=False))
    lines.append("")

    # explicação das colunas
    cols_111213 = [c for c in df_ag.columns if str(c).endswith(".0")]
    lines.append("INTERPRETAÇÃO DO BACKTEST")
    lines.append("- media_acertos: média de acertos do jogo nos concursos analisados (quanto maior, melhor).")
    lines.append("- max_acertos: o maior número de acertos que esse jogo já conseguiu no backtest (pico).")
    lines.append("- min_acertos: o menor número de acertos no backtest (pior dia).")
    if cols_111213:
        lines.append(f"- colunas {', '.join(map(str, cols_111213))}: quantas vezes fez 11, 12, 13 acertos etc (frequência de bons resultados).")
    lines.append("")

    # jogos gerados (copia os txt)
    lines.append("------------ JOGOS GERADOS — AGRESSIVO ------------")
    lines.append(_read_text(ag_txt).strip() + "\n")
    lines.append("------------ JOGOS GERADOS — CONSERVADOR ------------")
    lines.append(_read_text(co_txt).strip() + "\n")

    # relatório mastigado (se existir)
    if mast_txt.exists():
        lines.append("------------ RELATÓRIO MASTIGADO (GERADO) ------------")
        lines.append(_read_text(mast_txt).strip() + "\n")

    # dashboard (se existir)
    if dash_resumo.exists():
        lines.append("------------ DASHBOARD — RESUMO GERAL (CSV) ------------")
        try:
            dr = pd.read_csv(dash_resumo)
            lines.append(dr.to_string(index=False))
        except Exception as e:
            lines.append(f"(falha ao ler {dash_resumo}: {e})")
        lines.append("")

    if dash_dist.exists():
        lines.append("------------ DASHBOARD — DISTRIBUIÇÃO DE ACERTOS (CSV) ------------")
        try:
            dd = pd.read_csv(dash_dist)
            lines.append(dd.head(50).to_string(index=False))
            lines.append("(mostrando até 50 linhas)")
        except Exception as e:
            lines.append(f"(falha ao ler {dash_dist}: {e})")
        lines.append("")

    # ranking (se existir)
    if ranking_txt.exists() or ranking_csv.exists():
        lines.append("------------ RANKING ACUMULADO ------------")
        if ranking_txt.exists():
            lines.append(_read_text(ranking_txt).strip())
        else:
            try:
                rk = pd.read_csv(ranking_csv)
                lines.append(rk.head(30).to_string(index=False))
                lines.append("(mostrando top 30)")
            except Exception as e:
                lines.append(f"(falha ao ler {ranking_csv}: {e})")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ Relatório diário gerado em: {out_path}")


if __name__ == "__main__":
    main()