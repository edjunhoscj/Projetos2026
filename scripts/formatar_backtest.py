from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def formatar_backtest(csv_path: Path, modo: str, out_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV de backtest não encontrado: {csv_path}")

    df = pd.read_csv(csv_path)

    # Normaliza nome da coluna do jogo: "Jogo" ou "jogo"
    if "Jogo" in df.columns:
        df = df.rename(columns={"Jogo": "jogo"})
    elif "jogo" not in df.columns:
        # se a primeira coluna tiver outro nome, assume como jogo
        first = df.columns[0]
        df = df.rename(columns={first: "jogo"})

    # Ordena do melhor para o pior (maior média de acertos primeiro)
    if "media_acertos" in df.columns:
        df = df.sort_values("media_acertos", ascending=False)

    # Formata colunas numéricas para ficar mais legível
    if "media_acertos" in df.columns:
        df["media_acertos"] = df["media_acertos"].map(lambda x: f"{float(x):.2f}")

    for col in df.columns:
        if col.startswith(("max_", "min_")) or col.endswith(".0"):
            # contagens e máximos/mínimos como inteiros
            df[col] = df[col].map(lambda x: f"{int(float(x))}")

    # Constrói o texto final
    linhas: list[str] = []
    linhas.append("========================================")
    linhas.append(f" BACKTEST - MODO {modo.upper()}")
    linhas.append("========================================")
    linhas.append("")
    linhas.append("Resumo por jogo (ordenado pela melhor média de acertos):")
    linhas.append("")
    linhas.append(df.to_string(index=False))
    linhas.append("")
    linhas.append("Legenda:")
    linhas.append("  - media_acertos : média de acertos do jogo nos concursos analisados")
    linhas.append("  - max_acertos   : maior número de acertos que o jogo já fez")
    linhas.append("  - min_acertos   : menor número de acertos que o jogo já fez")
    linhas.append("  - colunas 11.0, 12.0, 13.0 etc: quantas vezes o jogo fez 11, 12, 13 pontos...")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(linhas), encoding="utf-8")
    print(f"TXT gerado em: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Formata o resultado do backtest (CSV) em TXT legível."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Caminho do arquivo CSV de backtest.",
    )
    parser.add_argument(
        "--modo",
        required=True,
        help="Rótulo do modo (agressivo, conservador, etc.) para aparecer no cabeçalho.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Caminho do arquivo TXT de saída.",
    )

    args = parser.parse_args()
    formatar_backtest(Path(args.csv), args.modo, Path(args.out))


if __name__ == "__main__":
    main()