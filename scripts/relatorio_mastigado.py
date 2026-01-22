from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


# -----------------------
# Helpers de colunas
# -----------------------
def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Retorna o primeiro nome de coluna existente em df a partir de candidates."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _get_count_col(df: pd.DataFrame, n: int) -> str | None:
    # tenta formatos comuns: "14.0", "14", "14.00"
    return _find_col(df, [f"{float(n)}", str(n), f"{n}.0", f"{n}.00"])


def ler_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Normaliza colunas de acertos (11..15) se tiverem nomes alternativos
    col_11 = _get_count_col(df, 11)
    col_12 = _get_count_col(df, 12)
    col_13 = _get_count_col(df, 13)
    col_14 = _get_count_col(df, 14)
    col_15 = _get_count_col(df, 15)

    # garante existência
    for n, col in [(11, col_11), (12, col_12), (13, col_13), (14, col_14), (15, col_15)]:
        if col is None:
            df[f"{float(n)}"] = 0
        else:
            # renomeia para padrão "14.0"
            std = f"{float(n)}"
            if col != std:
                df = df.rename(columns={col: std})

    # garante colunas base
    for c in ["jogo", "media_acertos", "max_acertos", "min_acertos"]:
        if c not in df.columns:
            df[c] = 0

    # score_13plus
    if "score_13plus" not in df.columns:
        df["score_13plus"] = (
            df.get("13.0", 0).astype(int)
            + df.get("14.0", 0).astype(int)
            + df.get("15.0", 0).astype(int)
        )

    # qtd_14plus
    df["qtd_14plus"] = df.get("14.0", 0).astype(int) + df.get("15.0", 0).astype(int)

    # score_alvo (se não existir, recalcula)
    if "score_alvo" not in df.columns:
        df["score_alvo"] = (
            100 * df.get("15.0", 0).astype(int)
            + 40 * df.get("14.0", 0).astype(int)
            + 10 * df.get("13.0", 0).astype(int)
            + 2 * df.get("12.0", 0).astype(int)
            + 0 * df.get("11.0", 0).astype(int)
        )

    # força numérico
    for c in ["media_acertos", "max_acertos", "min_acertos", "score_alvo", "score_13plus", "qtd_14plus"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df


def top_alvo(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    # Ranking focado em 14/15 primeiro, depois 13+, depois max/média
    return (
        df.sort_values(
            by=["qtd_14plus", "score_alvo", "score_13plus", "max_acertos", "media_acertos"],
            ascending=[False, False, False, False, False],
        )
        .head(n)
        .reset_index(drop=True)
    )


def fmt(df: pd.DataFrame) -> str:
    cols = [
        "jogo",
        "media_acertos",
        "max_acertos",
        "min_acertos",
        "11.0",
        "12.0",
        "13.0",
        "14.0",
        "15.0",
        "qtd_14plus",
        "score_alvo",
        "score_13plus",
    ]
    cols = [c for c in cols if c in df.columns]
    # arredonda média pra ficar legível
    if "media_acertos" in df.columns:
        df = df.copy()
        df["media_acertos"] = df["media_acertos"].astype(float).round(4)
    return df[cols].to_string(index=False)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agressivo", required=True)
    p.add_argument("--conservador", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--ultimos", type=int, default=300, help="Qtd de concursos usados no backtest (para prob)")
    args = p.parse_args()

    ag = ler_csv(Path(args.agressivo))
    co = ler_csv(Path(args.conservador))

    ag_top = top_alvo(ag, 5)
    co_top = top_alvo(co, 5)

    # melhores 1-2 pra aposta
    ag_1 = ag_top.iloc[0].to_dict() if len(ag_top) else {}
    ag_2 = ag_top.iloc[1].to_dict() if len(ag_top) > 1 else {}
    co_1 = co_top.iloc[0].to_dict() if len(co_top) else {}
    co_2 = co_top.iloc[1].to_dict() if len(co_top) > 1 else {}

    def _line_best(prefix: str, row: dict) -> str:
        if not row:
            return f"{prefix}: (sem dados)"
        prob = float(row.get("qtd_14plus", 0)) / float(args.ultimos) if args.ultimos else 0.0
        return (
            f"{prefix}: jogo {int(row.get('jogo', 0))} | "
            f"14+15={int(row.get('qtd_14plus', 0))} | "
            f"13+={int(row.get('score_13plus', 0))} | "
            f"max={int(row.get('max_acertos', 0))} | "
            f"média={float(row.get('media_acertos', 0)):.4f} | "
            f"score_alvo={int(row.get('score_alvo', 0))} | "
            f"prob_14+15≈{prob:.2%}"
        )

    out = []
    out.append("==============================================")
    out.append("RELATÓRIO MASTIGADO — FOCO EM 14/15")
    out.append(f"DATA: {args.data}")
    out.append("==============================================")
    out.append("")
    out.append("Ranking principal (prioridade):")
    out.append("1) qtd_14plus = (14 + 15)  [mais importante]")
    out.append("2) score_alvo = 100*(15) + 40*(14) + 10*(13) + 2*(12) + 0*(11)")
    out.append("3) score_13plus = (13+14+15)")
    out.append("4) max_acertos")
    out.append("5) media_acertos")
    out.append("")

    out.append("RECOMENDAÇÃO (1 ou 2 apostas):")
    out.append(_line_best("AGRESSIVO #1", ag_1))
    out.append(_line_best("AGRESSIVO #2", ag_2))
    out.append(_line_best("CONSERVADOR #1", co_1))
    out.append(_line_best("CONSERVADOR #2", co_2))
    out.append("")
    out.append("Dica prática:")
    out.append("- Se você vai jogar SÓ 1: pegue o #1 (modo que tiver maior 14+15; se empatar, maior score_alvo).")
    out.append("- Se você vai jogar 2: pegue o #1 agressivo + #1 conservador (tende a diversificar).")
    out.append("")

    out.append("------------ TOP 5 (AGRESSIVO) ------------")
    out.append(fmt(ag_top))
    out.append("")
    out.append("------------ TOP 5 (CONSERVADOR) ------------")
    out.append(fmt(co_top))
    out.append("")

    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()