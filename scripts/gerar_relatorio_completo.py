from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def ler_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def ler_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def extrair_jogos_de_txt(path: Path) -> Dict[int, List[int]]:
    """
    Extrai do TXT do wizard:
      "Jogo 01: 01 02 ... 15"
    Retorna {1: [..15..], 2: ...}
    """
    txt = ler_txt(path)
    jogos: Dict[int, List[int]] = {}

    for line in txt.splitlines():
        if "Jogo" not in line:
            continue

        nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", line)]
        if len(nums) < 16:
            continue

        idx = nums[0]  # nº do jogo
        dezenas = nums[-15:]
        if all(1 <= d <= 25 for d in dezenas) and len(set(dezenas)) == 15:
            jogos[int(idx)] = sorted(dezenas)

    return jogos


def fmt_dezenas(dezenas: List[int]) -> str:
    return " ".join(f"{d:02d}" for d in sorted(dezenas))


def overlap(a: List[int], b: List[int]) -> int:
    return len(set(a) & set(b))


def rank_alvo(df: pd.DataFrame) -> pd.DataFrame:
    for c in ["score_alvo", "score_13plus", "max_acertos", "media_acertos"]:
        if c not in df.columns:
            df[c] = 0
    return df.sort_values(
        by=["score_alvo", "score_13plus", "max_acertos", "media_acertos"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def escolher_dupla_diversa(df_rank: pd.DataFrame, jogos_map: Dict[int, List[int]]) -> Tuple[int, int]:
    # pega o melhor e escolhe o segundo com menor overlap (desempate por score_alvo)
    j1 = int(df_rank.loc[0, "jogo"])
    d1 = jogos_map.get(j1)
    if not d1:
        return j1, int(df_rank.loc[1, "jogo"]) if len(df_rank) > 1 else j1

    candidatos = []
    for i in range(1, min(len(df_rank), 20)):
        j2 = int(df_rank.loc[i, "jogo"])
        d2 = jogos_map.get(j2)
        if not d2:
            continue
        ov = overlap(d1, d2)
        candidatos.append((ov, -float(df_rank.loc[i, "score_alvo"]), j2))

    if not candidatos:
        return j1, int(df_rank.loc[1, "jogo"]) if len(df_rank) > 1 else j1

    candidatos.sort()
    return j1, candidatos[0][2]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)

    p.add_argument("--jogos-ag", required=True)
    p.add_argument("--jogos-cons", required=True)

    p.add_argument("--bt-ag-txt", required=True)
    p.add_argument("--bt-cons-txt", required=True)

    p.add_argument("--bt-ag-csv", required=True)
    p.add_argument("--bt-cons-csv", required=True)

    p.add_argument("--dash-resumo", required=True)
    p.add_argument("--dash-dist", required=True)

    p.add_argument("--out", required=True)
    args = p.parse_args()

    out = []
    out.append("==============================================")
    out.append("RELATÓRIO COMPLETO DO WIZARD")
    out.append(f"DATA: {args.data}")
    out.append("==============================================")
    out.append("")

    # Backtests TXT
    out.append("------------ BACKTEST — MODO AGRESSIVO ------------")
    out.append(ler_txt(Path(args.bt_ag_txt)))
    out.append("")
    out.append("------------ BACKTEST — MODO CONSERVADOR ------------")
    out.append(ler_txt(Path(args.bt_cons_txt)))
    out.append("")

    # Dashboard CSVs
    out.append("------------ DASHBOARD — RESUMO GERAL (CSV) ------------")
    out.append(ler_csv(Path(args.dash_resumo)).to_string(index=False))
    out.append("")
    out.append("------------ DISTRIBUIÇÃO DE ACERTOS (CSV) ------------")
    out.append(ler_csv(Path(args.dash_dist)).to_string(index=False))
    out.append("")

    # Jogos TXT
    out.append("------------ JOGOS GERADOS — AGRESSIVO ------------")
    out.append(ler_txt(Path(args.jogos_ag)))
    out.append("")
    out.append("------------ JOGOS GERADOS — CONSERVADOR ------------")
    out.append(ler_txt(Path(args.jogos_cons)))
    out.append("")

    # Recomendação final por ALVO
    out.append("============ RECOMENDAÇÃO FINAL — FOCO 14/15 ============")
    out.append("Ranking principal:")
    out.append("score_alvo = 100*(15) + 40*(14) + 10*(13) + 2*(12) + 0*(11)")
    out.append("Desempate: 13+ > max > média")
    out.append("")

    df_ag = rank_alvo(ler_csv(Path(args.bt_ag_csv)))
    df_co = rank_alvo(ler_csv(Path(args.bt_cons_csv)))

    jogos_ag = extrair_jogos_de_txt(Path(args.jogos_ag))
    jogos_co = extrair_jogos_de_txt(Path(args.jogos_cons))

    best_ag = int(df_ag.loc[0, "jogo"])
    best_co = int(df_co.loc[0, "jogo"])

    d_best_ag = jogos_ag.get(best_ag)
    d_best_co = jogos_co.get(best_co)

    out.append("Se você for apostar SÓ 1 jogo (recomendado):")
    if d_best_ag:
        out.append(f"➡️  AGRESSIVO (Jogo {best_ag:02d}): {fmt_dezenas(d_best_ag)}")
    else:
        out.append(f"➡️  Melhor AGRESSIVO: Jogo {best_ag:02d} (veja o TXT do wizard)")
    out.append("")

    out.append("Se você for apostar 2 jogos (duas opções):")

    # Opção A: 2 do agressivo, mais diferentes entre si
    j1, j2 = escolher_dupla_diversa(df_ag, jogos_ag)
    d1 = jogos_ag.get(j1)
    d2 = jogos_ag.get(j2)
    if d1 and d2:
        out.append("✅ Opção A — 2 do AGRESSIVO (maior cobertura):")
        out.append(f"   - AG {j1:02d}: {fmt_dezenas(d1)}")
        out.append(f"   - AG {j2:02d}: {fmt_dezenas(d2)}")
        out.append(f"   (overlap: {overlap(d1, d2)} dezenas repetidas)")
    else:
        out.append("✅ Opção A — use os 2 melhores do AGRESSIVO pelo score_alvo (ver CSV).")

    out.append("")

    # Opção B: 1 agressivo + 1 conservador
    if d_best_ag and d_best_co:
        out.append("✅ Opção B — 1 AGRESSIVO + 1 CONSERVADOR:")
        out.append(f"   - AG {best_ag:02d}: {fmt_dezenas(d_best_ag)}")
        out.append(f"   - CO {best_co:02d}: {fmt_dezenas(d_best_co)}")
        out.append(f"   (overlap: {overlap(d_best_ag, d_best_co)} dezenas repetidas)")
    else:
        out.append("✅ Opção B — melhor AG + melhor CO pelo score_alvo (ver CSV).")

    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()