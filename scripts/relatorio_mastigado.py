from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd


def _read_backtest_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    df = pd.read_csv(path)

    # normaliza nomes comuns
    rename = {}
    for col in df.columns:
        c = col.strip().lower()
        if c == "jogo":
            rename[col] = "jogo"
        elif c in ("media_acertos", "média_acertos", "media"):
            rename[col] = "media_acertos"
        elif c in ("max_acertos", "max"):
            rename[col] = "max_acertos"
        elif c in ("min_acertos", "min"):
            rename[col] = "min_acertos"
    df = df.rename(columns=rename)

    required = {"jogo", "media_acertos", "max_acertos", "min_acertos"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias faltando em {path}: {sorted(missing)}")

    # garante tipos
    df["jogo"] = pd.to_numeric(df["jogo"], errors="coerce")
    df["media_acertos"] = pd.to_numeric(df["media_acertos"], errors="coerce")
    df["max_acertos"] = pd.to_numeric(df["max_acertos"], errors="coerce")
    df["min_acertos"] = pd.to_numeric(df["min_acertos"], errors="coerce")
    df = df.dropna(subset=["jogo", "media_acertos", "max_acertos", "min_acertos"]).copy()

    # colunas "11.0, 12.0, 13.0..." (se existirem)
    # mantém como strings para exibir bonito
    for col in df.columns:
        if col not in required:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


def _pick_best(df: pd.DataFrame) -> dict:
    # Melhor geral: maior média (desempate: maior max, maior min)
    best = df.sort_values(
        by=["media_acertos", "max_acertos", "min_acertos"],
        ascending=[False, False, False],
    ).iloc[0]

    # Explosivo: maior max (desempate: maior média)
    explosivo = df.sort_values(
        by=["max_acertos", "media_acertos", "min_acertos"],
        ascending=[False, False, False],
    ).iloc[0]

    # Estável: maior min (desempate: maior média)
    estavel = df.sort_values(
        by=["min_acertos", "media_acertos", "max_acertos"],
        ascending=[False, False, False],
    ).iloc[0]

    return {
        "best": best,
        "explosivo": explosivo,
        "estavel": estavel,
    }


def _format_table(df: pd.DataFrame) -> str:
    show_cols = ["jogo", "media_acertos", "max_acertos", "min_acertos"]
    # inclui colunas de contagem (11.0, 12.0, 13.0...) se existirem
    extra = [c for c in df.columns if c not in show_cols]
    extra_sorted = sorted(extra, key=lambda x: float(str(x).replace(",", ".")) if str(x).replace(".", "", 1).isdigit() else 9999)
    cols = show_cols + extra_sorted

    out = df[cols].copy()

    out["jogo"] = out["jogo"].astype(int)
    out["media_acertos"] = out["media_acertos"].map(lambda x: f"{x:.4f}")
    out["max_acertos"] = out["max_acertos"].astype(int)
    out["min_acertos"] = out["min_acertos"].astype(int)

    # deixa ordenado por melhor média
    out = out.sort_values(by=["media_acertos"], ascending=False)

    return out.to_string(index=False)


def _section(mode_name: str, df: pd.DataFrame) -> str:
    picks = _pick_best(df)
    best = picks["best"]
    explosivo = picks["explosivo"]
    estavel = picks["estavel"]

    # tenta pegar contagens de 11/12/13 se houver
    def get_count(row, colname: str) -> int | None:
        return int(row[colname]) if colname in df.columns else None

    c11 = get_count(best, "11.0")
    c12 = get_count(best, "12.0")
    c13 = get_count(best, "13.0")

    lines = []
    lines.append(f"------------ BACKTEST — MODO {mode_name.upper()} ------------")
    lines.append(_format_table(df))
    lines.append("")
    lines.append("🧠 Leitura mastigada:")
    lines.append(f"• Melhor geral: Jogo {int(best['jogo'])}  | média {best['media_acertos']:.2f} | max {int(best['max_acertos'])} | min {int(best['min_acertos'])}")
    if c11 is not None and c12 is not None and c13 is not None:
        lines.append(f"  ↳ ocorrência (11/12/13): {c11}/{c12}/{c13}")
    lines.append(f"• Mais explosivo (maior pico): Jogo {int(explosivo['jogo'])} | max {int(explosivo['max_acertos'])} | média {explosivo['media_acertos']:.2f}")
    lines.append(f"• Mais estável (melhor piso): Jogo {int(estavel['jogo'])} | min {int(estavel['min_acertos'])} | média {estavel['media_acertos']:.2f}")
    lines.append("")
    return "\n".join(lines), int(best["jogo"])


def main():
    p = argparse.ArgumentParser(description="Gera relatório mastigado do backtest (agressivo + conservador).")
    p.add_argument("--agressivo", type=str, required=True, help="CSV do backtest agressivo")
    p.add_argument("--conservador", type=str, required=True, help="CSV do backtest conservador")
    p.add_argument("--out", type=str, required=True, help="TXT de saída do relatório")
    p.add_argument("--data", type=str, default="", help="Data a imprimir no topo (opcional)")
    args = p.parse_args()

    ag_csv = Path(args.agressivo)
    co_csv = Path(args.conservador)
    out_path = Path(args.out)

    df_ag = _read_backtest_csv(ag_csv)
    df_co = _read_backtest_csv(co_csv)

    if not args.data:
        data_str = datetime.now().strftime("%d-%m-%Y")
    else:
        data_str = args.data

    header = [
        "==============================================",
        "        RELATÓRIO MASTIGADO DO BACKTEST",
        f"        DATA: {data_str}",
        "==============================================",
        "",
    ]

    sec_ag, best_ag = _section("agressivo", df_ag)
    sec_co, best_co = _section("conservador", df_co)

    # recomendação final simples e clara
    rec = []
    rec.append("============ RECOMENDAÇÃO FINAL ============")
    rec.append(f"✔ Se apostar só 1 jogo (mais consistente): use o melhor do AGRESSIVO (Jogo {best_ag})")
    rec.append(f"✔ Para 2 jogos: melhor AGRESSIVO (Jogo {best_ag}) + melhor CONSERVADOR (Jogo {best_co})")
    rec.append("✔ Para 3 jogos: melhor AGRESSIVO + melhor CONSERVADOR + o mais explosivo (max maior) do modo que preferir")
    rec.append("============================================")
    rec.append("")

    text = "\n".join(header) + sec_ag + sec_co + "\n".join(rec)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"✅ Relatório gerado em: {out_path}")


if __name__ == "__main__":
    main()