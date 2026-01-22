from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Dict

import numpy as np
import pandas as pd


def extrair_jogos_de_txt(path: Path) -> List[List[int]]:
    """
    Lê TXT do wizard e extrai jogos com 15 dezenas.
    Aceita:
      - "Jogo 01: 01 02 ... 15"
      - ou linhas contendo 15 números
    """
    txt = path.read_text(encoding="utf-8", errors="ignore")
    jogos: List[List[int]] = []

    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue

        nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", line)]
        if len(nums) < 15:
            continue

        # Se capturou o "01" do "Jogo 01", pegamos as últimas 15 dezenas
        dezenas = nums[-15:]
        if all(1 <= d <= 25 for d in dezenas) and len(set(dezenas)) == 15:
            jogos.append(sorted(dezenas))

    # remove duplicados mantendo ordem
    seen = set()
    uniq = []
    for j in jogos:
        t = tuple(j)
        if t not in seen:
            seen.add(t)
            uniq.append(j)

    return uniq


def carregar_base_xlsx(base_path: Path) -> pd.DataFrame:
    df = pd.read_excel(base_path)

    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Base inválida. Colunas faltando: {faltando}")

    return df.sort_values("Concurso").reset_index(drop=True)


def ultimos_concursos(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.tail(int(n)).reset_index(drop=True)


def acertos_jogo_vs_concurso(jogo: List[int], concurso: List[int]) -> int:
    return len(set(jogo) & set(concurso))


def backtest_jogo(jogo: List[int], df_ultimos: pd.DataFrame) -> List[int]:
    acertos = []
    for _, row in df_ultimos.iterrows():
        dezenas = [int(row[f"D{i}"]) for i in range(1, 16)]
        acertos.append(acertos_jogo_vs_concurso(jogo, dezenas))
    return acertos


def resumo_jogo(acertos: List[int]) -> Dict[str, float]:
    """
    Retorna métricas do jogo no recorte:
      - média/max/min
      - contagem de 11..15
      - score_alvo e variantes
      - probabilidades (baseadas no recorte)
    """
    arr = np.array(acertos, dtype=float)
    n = int(len(arr))

    out: Dict[str, float] = {
        "n_concursos": float(n),
        "media_acertos": float(arr.mean()) if n else 0.0,
        "max_acertos": float(arr.max()) if n else 0.0,
        "min_acertos": float(arr.min()) if n else 0.0,
    }

    # contagens
    for k in [11, 12, 13, 14, 15]:
        out[f"{float(k)}"] = int(np.sum(arr == k))

    c11 = int(out["11.0"])
    c12 = int(out["12.0"])
    c13 = int(out["13.0"])
    c14 = int(out["14.0"])
    c15 = int(out["15.0"])

    # alvo: 14/15 muito acima, depois 13, depois 12
    score_alvo = (100 * c15) + (40 * c14) + (10 * c13) + (2 * c12) + (0 * c11)
    out["score_alvo"] = float(score_alvo)

    # auxiliares de desempate
    out["qtd_14plus"] = float(c14 + c15)
    out["score_13plus"] = float(c13 + c14 + c15)

    # probabilidades no recorte (em %)
    if n:
        out["prob_15"] = 100.0 * (c15 / n)
        out["prob_14plus"] = 100.0 * ((c14 + c15) / n)
        out["prob_13plus"] = 100.0 * ((c13 + c14 + c15) / n)
        out["score_alvo_por100"] = (score_alvo / n) * 100.0  # normaliza por 100 concursos
    else:
        out["prob_15"] = 0.0
        out["prob_14plus"] = 0.0
        out["prob_13plus"] = 0.0
        out["score_alvo_por100"] = 0.0

    return out


def formatar_tabela(df: pd.DataFrame) -> str:
    """
    Tabela mastigada (mostra o que importa pro alvo 14/15).
    """
    cols_ordem = [
        "jogo",
        "qtd_14plus",
        "prob_14plus",
        "prob_15",
        "score_alvo",
        "score_alvo_por100",
        "score_13plus",
        "media_acertos",
        "max_acertos",
        "min_acertos",
        "11.0",
        "12.0",
        "13.0",
        "14.0",
        "15.0",
    ]
    cols = [c for c in cols_ordem if c in df.columns]
    view = df[cols].copy()

    # arredondamentos pra leitura
    for c in ["media_acertos", "score_alvo_por100", "prob_14plus", "prob_15", "prob_13plus"]:
        if c in view.columns:
            view[c] = view[c].astype(float).round(4)

    for c in ["qtd_14plus", "score_13plus", "score_alvo", "max_acertos", "min_acertos"]:
        if c in view.columns:
            view[c] = view[c].astype(float).round(0).astype(int)

    return view.to_string(index=False)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--jogos-file", required=True, help="TXT com jogos do wizard")
    p.add_argument("--base", required=True, help="Base limpa XLSX")
    p.add_argument("--ultimos", type=int, default=300, help="Qtd de concursos no backtest (default: 300)")
    p.add_argument("--csv-out", required=True, help="Saída CSV do backtest")
    p.add_argument("--out", required=False, help="Saída TXT formatada do backtest")
    p.add_argument("--titulo", default="BACKTEST", help="Título no TXT")
    args = p.parse_args()

    jogos_path = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)
    txt_out = Path(args.out) if args.out else None

    jogos = extrair_jogos_de_txt(jogos_path)
    if not jogos:
        raise SystemExit(f"Nenhum jogo válido encontrado em: {jogos_path}")

    base_df = carregar_base_xlsx(base_path)
    df_ult = ultimos_concursos(base_df, args.ultimos)

    rows = []
    for idx, jogo in enumerate(jogos, start=1):
        acertos = backtest_jogo(jogo, df_ult)
        r = resumo_jogo(acertos)
        r["jogo"] = idx
        rows.append(r)

    df = pd.DataFrame(rows)

    # RANKING PRINCIPAL: ALVO 14/15
    # prioridade:
    # 1) mais vezes 14/15 (qtd_14plus)
    # 2) score_alvo (15 muito acima de 14, etc)
    # 3) mais 13+ (score_13plus)
    # 4) max
    # 5) média
    df_rank_alvo = df.sort_values(
        by=["qtd_14plus", "score_alvo", "score_13plus", "max_acertos", "media_acertos"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)

    # RANKING SECUNDÁRIO: MÉDIA (pra comparação)
    df_rank_media = df.sort_values(
        by=["media_acertos", "max_acertos", "qtd_14plus", "score_alvo"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df_rank_alvo.to_csv(csv_out, index=False)

    if txt_out:
        txt_out.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("=" * 56)
        lines.append(args.titulo)
        lines.append("=" * 56)
        lines.append("")
        lines.append(f"Recorte analisado: últimos {int(args.ultimos)} concursos")
        lines.append("")
        lines.append("Ranking PRINCIPAL (ALVO 14/15):")
        lines.append("Prioridade: (qtd_14plus) > score_alvo > 13+ > max > média")
        lines.append("score_alvo = 100*(15) + 40*(14) + 10*(13) + 2*(12) + 0*(11)")
        lines.append("")
        lines.append(formatar_tabela(df_rank_alvo))
        lines.append("")
        lines.append("Ranking SECUNDÁRIO (por média):")
        lines.append("")
        lines.append(formatar_tabela(df_rank_media))
        lines.append("")

        txt_out.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: CSV gerado em: {csv_out}")
    if txt_out:
        print(f"OK: TXT gerado em: {txt_out}")


if __name__ == "__main__":
    main()