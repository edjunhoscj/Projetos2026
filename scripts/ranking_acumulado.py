from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re

import pandas as pd


OUT_DIR = Path("outputs")


def extrair_data_do_nome(path: Path) -> datetime | None:
    """
    backtest_agressivo_14-01-2026_22h03min.csv
    """
    m = re.search(r"(\d{2}-\d{2}-\d{4}_\d{2}h\d{2}min)", path.stem)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%d-%m-%Y_%Hh%Mmin")


def carregar_backtests() -> pd.DataFrame:
    arquivos = list(OUT_DIR.glob("backtest_agressivo_*.csv")) + list(
        OUT_DIR.glob("backtest_conservador_*.csv")
    )

    registros = []
    for arq in arquivos:
        modo = "agressivo" if "agressivo" in arq.name else "conservador"
        data_ref = extrair_data_do_nome(arq)

        df = pd.read_csv(arq)
        if "Jogo" not in df.columns:
            continue

        df2 = df.copy()
        df2["modo"] = modo
        df2["arquivo"] = arq.name
        df2["data_ref"] = data_ref

        registros.append(df2)

    if not registros:
        return pd.DataFrame()

    return pd.concat(registros, ignore_index=True)


def main() -> None:
    df = carregar_backtests()
    if df.empty:
        print("⚠️ Nenhum backtest encontrado para montar ranking.")
        return

    # Garante colunas principais
    for col in ["media_acertos", "max_acertos", "min_acertos"]:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    # Ranking: média > máximo > mínimo
    df_rank = df.sort_values(
        by=["media_acertos", "max_acertos", "min_acertos"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    df_rank.insert(0, "rank", df_rank.index + 1)

    # Salva CSV completo
    csv_path = OUT_DIR / "ranking_acumulado.csv"
    df_rank.to_csv(csv_path, index=False)

    # TXT resumido (top 30)
    txt_path = OUT_DIR / "ranking_acumulado.txt"
    linhas = []
    linhas.append("========================================")
    linhas.append("        RANKING ACUMULADO DE JOGOS      ")
    linhas.append("========================================\n")
    linhas.append("Ordenado por: média de acertos, depois máximo e mínimo.\n")
    linhas.append("Top 30 jogos:\n")

    col_11 = "11.0"
    col_12 = "12.0"
    col_13 = "13.0"
    col_14 = "14.0" if "14.0" in df_rank.columns else None
    col_15 = "15.0" if "15.0" in df_rank.columns else None

    for _, row in df_rank.head(30).iterrows():
        jogo = row["Jogo"]
        rank = int(row["rank"])
        modo = row["modo"]
        media = row["media_acertos"]
        max_a = row["max_acertos"]
        min_a = row["min_acertos"]
        data_ref = row.get("data_ref")

        data_str = (
            data_ref.strftime("%d/%m/%Y %H:%M") if isinstance(data_ref, datetime) else "-"
        )

        linhas.append(
            f"{rank:02d}. {jogo}  | modo: {modo} | média: {media:.3f} | "
            f"max: {max_a} | min: {min_a} | último backtest: {data_str}"
        )

        extras = []
        if col_11 in df_rank.columns:
            extras.append(f"11 pts: {row[col_11]}")
        if col_12 in df_rank.columns:
            extras.append(f"12 pts: {row[col_12]}")
        if col_13 in df_rank.columns:
            extras.append(f"13 pts: {row[col_13]}")
        if col_14 and col_14 in df_rank.columns:
            extras.append(f"14 pts: {row[col_14]}")
        if col_15 and col_15 in df_rank.columns:
            extras.append(f"15 pts: {row[col_15]}")

        if extras:
            linhas.append("    " + " | ".join(extras))

    txt_path.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✅ Ranking salvo em:\n - {csv_path}\n - {txt_path}")


if __name__ == "__main__":
    main()