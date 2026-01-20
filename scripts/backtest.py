from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd


def ler_jogos_de_txt(path: Path) -> List[List[int]]:
    """
    Lê um TXT do wizard e extrai linhas com 15 dezenas.
    Aceita linhas tipo:
    'Jogo 01: 01 02 03 ... 15' ou só '01 02 03 ... 15'
    """
    if not path.exists():
        raise FileNotFoundError(path)

    jogos: List[List[int]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        # pega somente números
        parts = [p for p in line.replace(":", " ").split() if p.isdigit()]
        nums = [int(x) for x in parts if 1 <= int(x) <= 25]
        # filtra exatamente 15
        if len(nums) >= 15:
            # pega os últimos 15 números da linha (caso tenha “Jogo 01” etc)
            nums = nums[-15:]
        if len(nums) == 15:
            nums = sorted(nums)
            jogos.append(nums)

    # remove duplicados preservando ordem
    seen = set()
    unique = []
    for j in jogos:
        t = tuple(j)
        if t in seen:
            continue
        seen.add(t)
        unique.append(j)
    return unique


def carregar_base(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_excel(path)
    cols = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    df = df[cols].copy().sort_values("Concurso").reset_index(drop=True)
    for c in cols:
        if c != "Concurso":
            df[c] = df[c].astype(int)
    df["Concurso"] = df["Concurso"].astype(int)
    return df


def acertos(jogo: List[int], concurso_row: pd.Series) -> int:
    dezenas = {int(concurso_row[f"D{i}"]) for i in range(1, 16)}
    return len(set(jogo).intersection(dezenas))


def backtest(jogos: List[List[int]], base_df: pd.DataFrame, ultimos: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base_use = base_df.tail(int(ultimos)).copy()

    rows_resumo = []
    rows_long = []  # para distribuição

    for idx, jogo in enumerate(jogos, start=1):
        hits = []
        for _, row in base_use.iterrows():
            h = acertos(jogo, row)
            hits.append(h)

        hits_arr = np.array(hits, dtype=int)
        media = float(np.mean(hits_arr))
        mx = int(np.max(hits_arr))
        mn = int(np.min(hits_arr))

        # contagens 11..15
        cont = {float(k): int(np.sum(hits_arr == k)) for k in range(11, 16)}

        rows_resumo.append(
            {
                "jogo": idx,
                "media_acertos": round(media, 4),
                "max_acertos": mx,
                "min_acertos": mn,
                **cont,
            }
        )

        rows_long.append({"modo": "NA", "jogo": idx, "max_acertos": mx})

    df_resumo = pd.DataFrame(rows_resumo).sort_values("media_acertos", ascending=False).reset_index(drop=True)
    df_long = pd.DataFrame(rows_long)
    return df_resumo, df_long


def formatar_tabela(df: pd.DataFrame) -> str:
    return df.to_string(index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest dos jogos do Wizard (gera CSV + TXT bonito).")
    ap.add_argument("--jogos-file", required=True, help="TXT com jogos")
    ap.add_argument("--base", required=True, help="base_limpa.xlsx")
    ap.add_argument("--ultimos", type=int, default=200, help="Quantos concursos usar no backtest")
    ap.add_argument("--csv-out", required=True, help="Saída CSV")
    ap.add_argument("--out", required=True, help="Saída TXT formatado")
    ap.add_argument("--titulo", default="BACKTEST", help="Título do relatório TXT")
    args = ap.parse_args()

    jogos_file = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)
    txt_out = Path(args.out)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    txt_out.parent.mkdir(parents=True, exist_ok=True)

    jogos = ler_jogos_de_txt(jogos_file)
    if not jogos:
        raise ValueError(f"Nenhum jogo válido (15 dezenas) encontrado em: {jogos_file}")

    base_df = carregar_base(base_path)
    df_resumo, _ = backtest(jogos, base_df, int(args.ultimos))

    df_resumo.to_csv(csv_out, index=False)

    # TXT bonito
    texto = []
    texto.append("==============================================")
    texto.append(args.titulo)
    texto.append("==============================================\n")
    texto.append("Resumo por jogo (ordenado pela melhor média de acertos):\n")
    texto.append(formatar_tabela(df_resumo))
    texto.append("\n\nLegenda:")
    texto.append("- media_acertos : média de acertos do jogo nos concursos analisados")
    texto.append("- max_acertos   : maior número de acertos que o jogo já fez")
    texto.append("- min_acertos   : menor número de acertos que o jogo já fez")
    texto.append("- colunas 11.0, 12.0, 13.0 etc: quantas vezes o jogo fez 11, 12, 13 pontos...")
    texto.append("")

    txt_out.write_text("\n".join(texto), encoding="utf-8")

    print(f"✅ CSV salvo: {csv_out}")
    print(f"✅ TXT salvo: {txt_out}")
    print(f"Jogos avaliados: {len(jogos)} | Concursos usados: {int(args.ultimos)}")


if __name__ == "__main__":
    main()