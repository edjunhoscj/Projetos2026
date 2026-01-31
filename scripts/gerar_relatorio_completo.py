from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd


# -----------------------------
# I/O helpers
# -----------------------------
def ler_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def ler_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


# -----------------------------
# Parsing do TXT do wizard
# -----------------------------
RX_JOGO_LINE = re.compile(r"^\s*Jogo\s+(\d{1,2})\s*:\s*(.*)$", re.IGNORECASE)
RX_NUM = re.compile(r"\b\d{1,2}\b")


def extrair_jogos_de_txt(path: Path) -> Dict[int, List[int]]:
    """
    Extrai do TXT do wizard linhas no formato:
      "Jogo 01: 01 02 ... 25"
    Retorna {1: [15 dezenas], 2: ...}
    """
    txt = ler_txt(path)
    jogos: Dict[int, List[int]] = {}

    for line in txt.splitlines():
        m = RX_JOGO_LINE.match(line.strip())
        if not m:
            continue

        idx = int(m.group(1))
        nums = [int(x) for x in RX_NUM.findall(m.group(2))]

        if len(nums) != 15:
            # em geral, o wizard imprime exatamente 15 dezenas
            # mas se vier algo estranho, tentamos pegar as últimas 15
            if len(nums) < 15:
                continue
            nums = nums[-15:]

        if all(1 <= d <= 25 for d in nums) and len(set(nums)) == 15:
            jogos[idx] = sorted(nums)

    return jogos


def fmt_dezenas(dezenas: List[int]) -> str:
    return " ".join(f"{d:02d}" for d in sorted(dezenas))


def overlap(a: List[int], b: List[int]) -> int:
    return len(set(a) & set(b))


# -----------------------------
# Ranking / métricas
# -----------------------------
def _as_float(x, default=0.0) -> float:
    try:
        if pd.isna(x):
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def _col_count(df: pd.DataFrame, nome: str) -> pd.Series:
    if nome in df.columns:
        return pd.to_numeric(df[nome], errors="coerce").fillna(0.0)
    return pd.Series([0.0] * len(df))


def _hist_cols(df: pd.DataFrame) -> List[str]:
    """
    Detecta colunas do tipo "10.0", "11.0", ..., "15.0" (ou "10", "11"...)
    """
    cols = []
    for c in df.columns:
        s = str(c).strip()
        if re.fullmatch(r"\d+(\.\d+)?", s):
            cols.append(c)
    return cols


def garantir_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que existam as colunas usadas no ranking:
      - qtd_14plus (se não existir, tenta inferir por 14/15)
      - score_alvo
      - score_13plus
      - max_acertos
      - media_acertos
    Também calcula:
      - score_cauda (foco 11/12+)
      - prob_11plus, prob_12plus
    """
    df = df.copy()

    # Normaliza colunas esperadas
    for c in ["jogo", "qtd_14plus", "score_alvo", "score_13plus", "max_acertos", "media_acertos"]:
        if c not in df.columns:
            df[c] = 0

    # Histograma por acertos (se existir)
    cols_hist = _hist_cols(df)
    # tenta suportar nomes "11.0" etc como strings
    # Backtest costuma produzir 11.0..15.0; alguns podem vir como float->string no pandas
    def get_hist(k: int) -> pd.Series:
        # tenta achar "k.0" e "k"
        for key in (f"{k}.0", f"{k}"):
            if key in df.columns:
                return pd.to_numeric(df[key], errors="coerce").fillna(0.0)
        # às vezes vem como float 11.0 (colunas não-string)
        for col in df.columns:
            try:
                if float(col) == float(k):
                    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            except Exception:
                pass
        return pd.Series([0.0] * len(df))

    c10 = get_hist(10)
    c11 = get_hist(11)
    c12 = get_hist(12)
    c13 = get_hist(13)
    c14 = get_hist(14)
    c15 = get_hist(15)

    # Inferir qtd_14plus se estiver zerada (usa hist se existir)
    if df["qtd_14plus"].isna().any():
        df["qtd_14plus"] = pd.to_numeric(df["qtd_14plus"], errors="coerce").fillna(0.0)
    if (df["qtd_14plus"].astype(float) == 0).all():
        # se hist tem algo, inferimos (14 + 15)
        if (c14.sum() + c15.sum()) > 0:
            df["qtd_14plus"] = (c14 + c15)

    # Recalcula score_alvo se vier faltando/zerado mas hist existir
    df["score_alvo"] = pd.to_numeric(df["score_alvo"], errors="coerce").fillna(0.0)
    if (df["score_alvo"].astype(float) == 0).all() and (c12.sum() + c13.sum() + c14.sum() + c15.sum()) > 0:
        df["score_alvo"] = 100 * c15 + 40 * c14 + 10 * c13 + 2 * c12

    # score_13plus se faltar
    df["score_13plus"] = pd.to_numeric(df["score_13plus"], errors="coerce").fillna(0.0)
    if (df["score_13plus"].astype(float) == 0).all() and (c13.sum() + c14.sum() + c15.sum()) > 0:
        df["score_13plus"] = (c13 + c14 + c15)

    # Métricas de cauda (11/12+)
    # “Score cauda” é mais realista para 15 dezenas: valoriza 12+ e 11
    # Ajuste pesos se quiser:
    df["score_cauda"] = (5.0 * c12) + (2.0 * c11) + (1.0 * c10) + (0.5 * c13)

    # Probabilidades aproximadas usando N do hist (se existir)
    if cols_hist:
        n = pd.Series([0.0] * len(df))
        # soma as colunas numéricas detectadas
        for col in cols_hist:
            n = n + pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        n = n.replace(0, pd.NA)

        df["prob_11plus"] = ((c11 + c12 + c13 + c14 + c15) / n).fillna(0.0)
        df["prob_12plus"] = ((c12 + c13 + c14 + c15) / n).fillna(0.0)
    else:
        df["prob_11plus"] = 0.0
        df["prob_12plus"] = 0.0

    # max/media
    df["max_acertos"] = pd.to_numeric(df["max_acertos"], errors="coerce").fillna(0.0)
    df["media_acertos"] = pd.to_numeric(df["media_acertos"], errors="coerce").fillna(0.0)
    df["jogo"] = pd.to_numeric(df["jogo"], errors="coerce").fillna(0).astype(int)

    return df


def rank_alvo(df: pd.DataFrame) -> pd.DataFrame:
    df = garantir_scores(df)
    # Prioridade: (qtd_14plus) > score_alvo > 13+ > max > média
    return df.sort_values(
        by=["qtd_14plus", "score_alvo", "score_13plus", "max_acertos", "media_acertos"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def rank_cauda(df: pd.DataFrame) -> pd.DataFrame:
    df = garantir_scores(df)
    # Para 11/12+: prioriza score_cauda e prob_12plus (se disponível)
    return df.sort_values(
        by=["score_cauda", "prob_12plus", "max_acertos", "media_acertos", "score_alvo"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


# -----------------------------
# Escolha de duplas com diversidade
# -----------------------------
@dataclass
class Candidato:
    modo: str   # "AG" ou "CO"
    jogo: int
    dezenas: Optional[List[int]]
    score_ref: float  # score do ranking usado (alvo ou cauda)


def escolher_dupla_diversa(cands: List[Candidato], top_n: int = 20) -> Tuple[Candidato, Candidato]:
    """
    Pega o melhor candidato e escolhe o segundo com menor overlap
    entre os top_n restantes. Desempate por score_ref.
    """
    if not cands:
        raise ValueError("Sem candidatos para escolher dupla.")

    base = cands[0]
    if not base.dezenas:
        # fallback: pega o 2º se existir
        return base, cands[1] if len(cands) > 1 else base

    melhores = []
    for c in cands[1: min(len(cands), top_n)]:
        if not c.dezenas:
            continue
        ov = overlap(base.dezenas, c.dezenas)
        melhores.append((ov, -c.score_ref, c))

    if not melhores:
        return base, cands[1] if len(cands) > 1 else base

    melhores.sort(key=lambda x: (x[0], x[1]))
    return base, melhores[0][2]


# -----------------------------
# Main
# -----------------------------
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

    out: List[str] = []
    out.append("==============================================")
    out.append("RELATÓRIO COMPLETO DO WIZARD")
    out.append(f"DATA: {args.data}")
    out.append("==============================================")
    out.append("")
    out.append("Nota: Para jogos de 15 dezenas, a média esperada por acaso é ~9 acertos.")
    out.append("O foco aqui é tentar aumentar a ocorrência de 11/12+ (cauda), além do alvo 14/15.")
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

    # Carrega CSVs e TXT (mapa jogo->dezenas)
    df_ag_raw = ler_csv(Path(args.bt_ag_csv))
    df_co_raw = ler_csv(Path(args.bt_cons_csv))

    df_ag_alvo = rank_alvo(df_ag_raw)
    df_co_alvo = rank_alvo(df_co_raw)

    df_ag_cauda = rank_cauda(df_ag_raw)
    df_co_cauda = rank_cauda(df_co_raw)

    jogos_ag = extrair_jogos_de_txt(Path(args.jogos_ag))
    jogos_co = extrair_jogos_de_txt(Path(args.jogos_cons))

    # -----------------------------
    # RECOMENDAÇÃO 14/15 (ALVO)
    # -----------------------------
    out.append("============ RECOMENDAÇÃO FINAL — FOCO 14/15 ============")
    out.append("Ranking principal:")
    out.append("Prioridade: (qtd_14plus) > score_alvo > 13+ > max > média")
    out.append("score_alvo = 100*(15) + 40*(14) + 10*(13) + 2*(12) + 0*(11)")
    out.append("")

    # Melhor de cada modo
    best_ag = int(df_ag_alvo.loc[0, "jogo"]) if len(df_ag_alvo) else 0
    best_co = int(df_co_alvo.loc[0, "jogo"]) if len(df_co_alvo) else 0

    d_best_ag = jogos_ag.get(best_ag)
    d_best_co = jogos_co.get(best_co)

    # Melhor GLOBAL (corrige bug: compara AG vs CO)
    cand_global_alvo: List[Candidato] = []

    for i in range(min(len(df_ag_alvo), 50)):
        j = int(df_ag_alvo.loc[i, "jogo"])
        cand_global_alvo.append(
            Candidato("AG", j, jogos_ag.get(j), _as_float(df_ag_alvo.loc[i, "score_alvo"]))
        )
    for i in range(min(len(df_co_alvo), 50)):
        j = int(df_co_alvo.loc[i, "jogo"])
        cand_global_alvo.append(
            Candidato("CO", j, jogos_co.get(j), _as_float(df_co_alvo.loc[i, "score_alvo"]))
        )

    # ordenar global pelo mesmo critério do alvo (reaproveita dataframes)
    # fazemos uma ordenação “manual” usando as colunas relevantes
    def chave_alvo(modo: str, jogo: int) -> Tuple[float, float, float, float, float]:
        if modo == "AG":
            row = df_ag_alvo[df_ag_alvo["jogo"] == jogo].iloc[0]
        else:
            row = df_co_alvo[df_co_alvo["jogo"] == jogo].iloc[0]
        return (
            _as_float(row.get("qtd_14plus", 0.0)),
            _as_float(row.get("score_alvo", 0.0)),
            _as_float(row.get("score_13plus", 0.0)),
            _as_float(row.get("max_acertos", 0.0)),
            _as_float(row.get("media_acertos", 0.0)),
        )

    cand_global_alvo.sort(key=lambda c: chave_alvo(c.modo, c.jogo), reverse=True)
    best_global_alvo = cand_global_alvo[0] if cand_global_alvo else None

    out.append("Se você for apostar SÓ 1 jogo (recomendado) — MELHOR GLOBAL:")
    if best_global_alvo and best_global_alvo.dezenas:
        out.append(f"➡️  {best_global_alvo.modo} (Jogo {best_global_alvo.jogo:02d}): {fmt_dezenas(best_global_alvo.dezenas)}")
    else:
        out.append("➡️  Não foi possível identificar o melhor global (ver CSV/TXT).")
    out.append("")

    out.append("Se você for apostar 2 jogos (opções):")

    # Opção A — 2 do MESMO MODO do melhor global, com menor overlap
    if best_global_alvo:
        if best_global_alvo.modo == "AG":
            cands_modo = [
                Candidato("AG", int(df_ag_alvo.loc[i, "jogo"]), jogos_ag.get(int(df_ag_alvo.loc[i, "jogo"])),
                          _as_float(df_ag_alvo.loc[i, "score_alvo"]))
                for i in range(min(len(df_ag_alvo), 50))
            ]
        else:
            cands_modo = [
                Candidato("CO", int(df_co_alvo.loc[i, "jogo"]), jogos_co.get(int(df_co_alvo.loc[i, "jogo"])),
                          _as_float(df_co_alvo.loc[i, "score_alvo"]))
                for i in range(min(len(df_co_alvo), 50))
            ]

        a1, a2 = escolher_dupla_diversa(cands_modo, top_n=20)
        if a1.dezenas and a2.dezenas:
            out.append("✅ Opção A — 2 do MESMO MODO do melhor global (maior coerência + diversidade):")
            out.append(f"   - {a1.modo} {a1.jogo:02d}: {fmt_dezenas(a1.dezenas)}")
            out.append(f"   - {a2.modo} {a2.jogo:02d}: {fmt_dezenas(a2.dezenas)}")
            out.append(f"   (overlap: {overlap(a1.dezenas, a2.dezenas)} dezenas repetidas)")
        else:
            out.append("✅ Opção A — não consegui formar dupla diversa (ver CSV/TXT).")
        out.append("")
    else:
        out.append("✅ Opção A — indisponível (sem melhor global).")
        out.append("")

    # Opção B — 1 AG + 1 CO (melhores de cada)
    if d_best_ag and d_best_co:
        out.append("✅ Opção B — 1 AGRESSIVO + 1 CONSERVADOR (diversificação de estilo):")
        out.append(f"   - AG {best_ag:02d}: {fmt_dezenas(d_best_ag)}")
        out.append(f"   - CO {best_co:02d}: {fmt_dezenas(d_best_co)}")
        out.append(f"   (overlap: {overlap(d_best_ag, d_best_co)} dezenas repetidas)")
    else:
        out.append("✅ Opção B — melhor AG + melhor CO pelo score_alvo (ver CSV/TXT).")
    out.append("")

    # Opção C — 2 GLOBAIS com menor overlap entre os top
    if cand_global_alvo:
        c1, c2 = escolher_dupla_diversa(cand_global_alvo, top_n=30)
        if c1.dezenas and c2.dezenas:
            out.append("✅ Opção C — 2 MELHORES GLOBAIS com menor overlap (mistura AG/CO se valer):")
            out.append(f"   - {c1.modo} {c1.jogo:02d}: {fmt_dezenas(c1.dezenas)}")
            out.append(f"   - {c2.modo} {c2.jogo:02d}: {fmt_dezenas(c2.dezenas)}")
            out.append(f"   (overlap: {overlap(c1.dezenas, c2.dezenas)} dezenas repetidas)")
        else:
            out.append("✅ Opção C — não consegui formar dupla global diversa (ver CSV/TXT).")
    else:
        out.append("✅ Opção C — indisponível (sem candidatos globais).")

    out.append("")

    # -----------------------------
    # RECOMENDAÇÃO 11/12+ (CAUDA)
    # -----------------------------
    out.append("============ RECOMENDAÇÃO ALTERNATIVA — FOCO 11/12+ (CAUDA) ============")
    out.append("Objetivo: aumentar ocorrência de 11/12+ no recorte (mais realista do que 14/15).")
    out.append("score_cauda = 5*(12) + 2*(11) + 1*(10) + 0.5*(13)")
    out.append("Desempate: prob_12plus > max > média > score_alvo")
    out.append("")

    cand_global_cauda: List[Candidato] = []

    for i in range(min(len(df_ag_cauda), 50)):
        j = int(df_ag_cauda.loc[i, "jogo"])
        cand_global_cauda.append(
            Candidato("AG", j, jogos_ag.get(j), _as_float(df_ag_cauda.loc[i, "score_cauda"]))
        )
    for i in range(min(len(df_co_cauda), 50)):
        j = int(df_co_cauda.loc[i, "jogo"])
        cand_global_cauda.append(
            Candidato("CO", j, jogos_co.get(j), _as_float(df_co_cauda.loc[i, "score_cauda"]))
        )

    def chave_cauda(modo: str, jogo: int) -> Tuple[float, float, float, float, float]:
        if modo == "AG":
            row = df_ag_cauda[df_ag_cauda["jogo"] == jogo].iloc[0]
        else:
            row = df_co_cauda[df_co_cauda["jogo"] == jogo].iloc[0]
        return (
            _as_float(row.get("score_cauda", 0.0)),
            _as_float(row.get("prob_12plus", 0.0)),
            _as_float(row.get("max_acertos", 0.0)),
            _as_float(row.get("media_acertos", 0.0)),
            _as_float(row.get("score_alvo", 0.0)),
        )

    cand_global_cauda.sort(key=lambda c: chave_cauda(c.modo, c.jogo), reverse=True)
    best_global_cauda = cand_global_cauda[0] if cand_global_cauda else None

    out.append("Se você for apostar SÓ 1 jogo (recomendado) — MELHOR GLOBAL (CAUDA):")
    if best_global_cauda and best_global_cauda.dezenas:
        out.append(f"➡️  {best_global_cauda.modo} (Jogo {best_global_cauda.jogo:02d}): {fmt_dezenas(best_global_cauda.dezenas)}")
    else:
        out.append("➡️  Não foi possível identificar o melhor global (cauda).")
    out.append("")

    out.append("Se você for apostar 2 jogos (CAUDA) — dupla mais diversa:")
    if cand_global_cauda:
        c1, c2 = escolher_dupla_diversa(cand_global_cauda, top_n=30)
        if c1.dezenas and c2.dezenas:
            out.append(f"   - {c1.modo} {c1.jogo:02d}: {fmt_dezenas(c1.dezenas)}")
            out.append(f"   - {c2.modo} {c2.jogo:02d}: {fmt_dezenas(c2.dezenas)}")
            out.append(f"   (overlap: {overlap(c1.dezenas, c2.dezenas)} dezenas repetidas)")
        else:
            out.append("   - Não consegui formar dupla (cauda).")
    else:
        out.append("   - Indisponível (sem candidatos).")

    out.append("")

    # Grava arquivo
    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()