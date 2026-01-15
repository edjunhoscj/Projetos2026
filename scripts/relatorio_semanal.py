from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
import re

import pandas as pd


OUT_DIR = Path("outputs")


def extrair_data_do_nome(path: Path) -> datetime | None:
    m = re.search(r"(\d{2}-\d{2}-\d{4}_\d{2}h\d{2}min)", path.stem)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%d-%m-%Y_%Hh%Mmin")


def carregar_backtests_ultima_semana(dias: int = 7) -> pd.DataFrame:
    arquivos = list(OUT_DIR.glob("backtest_agressivo_*.csv")) + list(
        OUT_DIR.glob("backtest_conservador_*.csv")
    )

    limite = datetime.now() - timedelta(days=dias)
    registros = []

    for arq in arquivos:
        dt = extrair_data_do_nome(arq)
        if not dt or dt < limite:
            continue

        modo = "agressivo" if "agressivo" in arq.name else "conservador"
        df = pd.read_csv(arq)
        if "Jogo" not in df.columns or "media_acertos" not in df.columns:
            continue

        df2 = df.copy()
        df2["modo"] = modo
        df2["arquivo"] = arq.name
        df2["data_ref"] = dt
        registros.append(df2)

    if not registros:
        return pd.DataFrame()

    return pd.concat(registros, ignore_index=True)


def main() -> None:
    df = carregar_backtests_ultima_semana(dias=7)
    path_txt = OUT_DIR / "relatorio_semanal.txt"

    if df.empty:
        path_txt.write_text(
            "Relatório semanal Wizard Lotofácil\n\n"
            "Não foram encontrados backtests nos últimos 7 dias.",
            encoding="utf-8",
        )
        print("⚠️ Sem dados para relatório semanal (últimos 7 dias).")
        return

    linhas = []
    linhas.append("========================================")
    linhas.append("     RELATÓRIO SEMANAL – WIZARD LOTOFÁCIL")
    linhas.append("========================================\n")

    min_data = df["data_ref"].min()
    max_data = df["data_ref"].max()
    linhas.append(
        f"Período analisado: {min_data.strftime('%d/%m/%Y %H:%M')} "
        f"até {max_data.strftime('%d/%m/%Y %H:%M')}\n"
    )

    # Visão geral
    linhas.append("VISÃO GERAL")
    linhas.append("-----------")
    linhas.append(f"Total de registros de backtest: {len(df)}")

    for modo in ["agressivo", "conservador"]:
        df_m = df[df["modo"] == modo]
        if df_m.empty:
            continue

        media_medias = df_m["media_acertos"].mean()
        melhor = df_m.sort_values(
            by=["media_acertos", "max_acertos"],
            ascending=[False, False],
        ).iloc[0]

        linhas.append(f"\nModo {modo}:")
        linhas.append(f"- média geral das médias de acertos: {media_medias:.3f}")
        linhas.append(
            f"- melhor jogo da semana: {melhor['Jogo']} "
            f"(média={melhor['media_acertos']:.3f}, "
            f"max={melhor['max_acertos']}, "
            f"min={melhor.get('min_acertos', '-')})"
        )

    # Contagem de jogos que bateram 13+ / 14+
    if "max_acertos" in df.columns:
        n13 = (df["max_acertos"] >= 13).sum()
        n14 = (df["max_acertos"] >= 14).sum()
        n15 = (df["max_acertos"] >= 15).sum()
        linhas.append("\nFREQUÊNCIA DE JOGOS COM ALTA PONTUAÇÃO")
        linhas.append("---------------------------------------")
        linhas.append(f"- Jogos com pelo menos 13 pts: {n13}")
        linhas.append(f"- Jogos com pelo menos 14 pts: {n14}")
        linhas.append(f"- Jogos com 15 pts: {n15}")

    path_txt.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✅ Relatório semanal salvo em {path_txt}")


if __name__ == "__main__":
    main()