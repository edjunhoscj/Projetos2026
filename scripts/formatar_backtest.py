from __future__ import annotations

from pathlib import Path
import argparse
import io

import pandas as pd


def ler_csv_backtest(csv_path: Path) -> pd.DataFrame:
    """
    Lê o CSV de backtest, ignorando ponteiros do Git LFS
    (linhas que começam com 'version ', 'oid sha256:' ou 'size ').
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV de backtest não encontrado: {csv_path}")

    raw = csv_path.read_text(encoding="utf-8").splitlines()

    # Remove linhas típicas de ponteiro LFS
    linhas_validas: list[str] = []
    for ln in raw:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("version https://git-lfs.github.com/spec/v1"):
            continue
        if s.startswith("oid sha256:"):
            continue
        if s.startswith("size "):
            continue
        linhas_validas.append(ln)

    if not linhas_validas:
        # Não tem nada de CSV de verdade
        raise ValueError(
            "Arquivo de backtest parece ser só um ponteiro Git LFS "
            "(não contém dados em formato CSV)."
        )

    # Junta de volta e manda pro pandas
    buf = io.StringIO("\n".join(linhas_validas))
    df = pd.read_csv(buf)

    # Normaliza o nome da coluna do jogo
    if "Jogo" in df.columns:
        df = df.rename(columns={"Jogo": "jogo"})
    elif "jogo" not in df.columns:
        first = df.columns[0]
        df = df.rename(columns={first: "jogo"})

    return df


def formatar_backtest(csv_path: Path, modo: str, out_path: Path) -> None:
    try:
        df = ler_csv_backtest(csv_path)
    except ValueError as e:
        # Gera um TXT explicando o problema (melhor do que jogar lixo)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "========================================\n"
            f" BACKTEST - MODO {modo.upper()}\n"
            "========================================\n\n"
            f"Não foi possível ler dados válidos no arquivo:\n  {csv_path}\n\n"
            f"Motivo: {e}\n\n"
            "Verifique se o CSV não está só como ponteiro Git LFS.\n",
            encoding="utf-8",
        )
        print(f"TXT gerado com aviso em: {out_path}")
        return

    # Ordena por melhor média de acertos
    if "media_acertos" in df.columns:
        df = df.sort_values("media_acertos", ascending=False)

    # Formata colunas numéricas
    if "media_acertos" in df.columns:
        df["media_acertos"] = df["media_acertos"].map(lambda x: f"{float(x):.4f}")

    for col in df.columns:
        if col.startswith(("max_", "min_")):
            df[col] = df[col].map(lambda x: f"{int(float(x))}")
        # colunas tipo 11.0, 12.0, 13.0...
        elif col.replace(".", "", 1).isdigit():
            df[col] = df[col].map(lambda x: f"{int(float(x))}")

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
    linhas.append(
        "  - colunas 11.0, 12.0, 13.0 etc: "
        "quantas vezes o jogo fez 11, 12, 13 pontos..."
    )

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
        help="Rótulo do modo (agressivo, conservador, etc.).",
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