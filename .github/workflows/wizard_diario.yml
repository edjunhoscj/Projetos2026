#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Set, Tuple, Optional

import pandas as pd


# -------------------------
# Parse de jogos (robusto)
# -------------------------
def parse_jogos_arquivo(path: Path) -> List[Tuple[int, ...]]:
    """
    Lê um TXT e extrai jogos de 15 dezenas (1..25), aceitando formatos como:
      - "02 03 05 ... 23"
      - "Jogo 01: 02 03 05 ... 23"
      - linhas com textos/emoji antes ou depois
    Regra: pega linhas que contenham EXATAMENTE 15 números válidos (1..25).
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    jogos: List[Tuple[int, ...]] = []

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue

        # extrai todos números 1-2 dígitos
        nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", line)]
        # filtra somente 1..25
        nums = [n for n in nums if 1 <= n <= 25]

        if len(nums) == 15:
            # mantém a ordem do arquivo, mas valida se são 15 distintas
            if len(set(nums)) == 15:
                jogos.append(tuple(nums))

    # fallback: às vezes o arquivo tem linhas quebradas ou formatos estranhos
    # então tentamos encontrar sequências de 15 números no arquivo inteiro.
    if not jogos:
        content = path.read_text(encoding="utf-8", errors="ignore")
        nums_all = [int(x) for x in re.findall(r"\b\d{1,2}\b", content)]
        nums_all = [n for n in nums_all if 1 <= n <= 25]

        # procura janelas de 15 números distintos
        for i in range(0, max(0, len(nums_all) - 14)):
            window = nums_all[i : i + 15]
            if len(window) == 15 and len(set(window)) == 15:
                jogos.append(tuple(window))
                # normalmente já basta (mas deixo coletar mais se houver)

    # remove duplicados mantendo ordem
    seen = set()
    jogos_uni = []
    for j in jogos:
        if j not in seen:
            seen.add(j)
            jogos_uni.append(j)

    if not jogos_uni:
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo. "
            "Confirme se é um TXT gerado pelo Wizard e contém linhas com 15 dezenas (1..25)."
        )

    return jogos_uni


# -------------------------
# Leitura da base de sorteios
# -------------------------
def _infer_dezenas_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tenta inferir as 15 dezenas por linha da base.
    Suporta:
      - colunas já numéricas (15 colunas)
      - colunas nomeadas tipo 'D1'..'D15', 'dez1'.. etc
    Retorna DF com colunas d1..d15 (int).
    """
    # pega colunas numéricas
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    # tenta usar as primeiras 15 numéricas
    if len(num_cols) >= 15:
        dez = df[num_cols[:15]].copy()
        dez.columns = [f"d{i}" for i in range(1, 16)]
        return dez.astype(int)

    # tenta achar por nomes comuns
    patterns = [
        r"^d(?:ez)?\s*0*([1-9]|1[0-5])$",
        r"^dezena\s*0*([1-9]|1[0-5])$",
        r"^bola\s*0*([1-9]|1[0-5])$",
    ]
    pick = {}
    for c in df.columns:
        name = str(c).strip().lower()
        for p in patterns:
            m = re.match(p, name)
            if m:
                idx = int(m.group(1))
                pick[idx] = c

    if len(pick) >= 15:
        cols = [pick[i] for i in range(1, 16)]
        dez = df[cols].copy()
        dez.columns = [f"d{i}" for i in range(1, 16)]
        return dez.astype(int)

    raise ValueError(
        "Não consegui inferir as 15 dezenas na base. "
        "Garanta que a planilha tenha 15 colunas numéricas de dezenas por concurso."
    )


def carregar_base(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Base não encontrada: {path}")

    # tenta Excel primeiro
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    dezenas = _infer_dezenas_from_df(df)
    return dezenas


# -------------------------
# Backtest
# -------------------------
def backtest(jogos: List[Tuple[int, ...]], base_dezenas: pd.DataFrame, ultimos: int) -> pd.DataFrame:
    # usa os últimos N concursos
    base = base_dezenas.tail(int(ultimos)).reset_index(drop=True)

    sorteios: List[Set[int]] = []
    for _, row in base.iterrows():
        s = set(int(row[f"d{i}"]) for i in range(1, 16))
        sorteios.append(s)

    rows = []
    for idx, jogo in enumerate(jogos, start=1):
        jogo_set = set(jogo)
        acertos = [len(jogo_set & s) for s in sorteios]

        # distribuição (11..15) – ajuste se quiser incluir mais faixas
        dist = {k: sum(1 for a in acertos if a == k) for k in range(11, 16)}

        rows.append(
            {
                "jogo": idx,
                "media_acertos": float(sum(acertos) / len(acertos)) if acertos else 0.0,
                "max_acertos": int(max(acertos)) if acertos else 0,
                "min_acertos": int(min(acertos)) if acertos else 0,
                **{f"{k}.0": dist[k] for k in range(11, 16)},  # compatível com seu layout 11.0,12.0...
            }
        )

    df = pd.DataFrame(rows).sort_values(["media_acertos", "max_acertos"], ascending=False).reset_index(drop=True)
    return df


def df_to_txt(df: pd.DataFrame, titulo: str) -> str:
    # mostra as colunas principais primeiro
    cols = ["jogo", "media_acertos", "max_acertos", "min_acertos"] + [c for c in df.columns if c.endswith(".0")]
    cols = [c for c in cols if c in df.columns]
    out = []
    out.append("=" * 46)
    out.append(titulo)
    out.append("=" * 46)
    out.append(df[cols].to_string(index=False))
    out.append("")
    out.append("Legenda:")
    out.append(" - media_acertos : média de acertos do jogo nos concursos analisados")
    out.append(" - max_acertos   : maior número de acertos que o jogo já fez")
    out.append(" - min_acertos   : menor número de acertos que o jogo já fez")
    out.append(" - colunas 11.0..15.0 : quantas vezes o jogo fez 11, 12, 13, 14, 15 pontos")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jogos-file", required=True, help="TXT com jogos do Wizard")
    ap.add_argument("--base", default="base/base_limpa.xlsx", help="Base histórica (xlsx/csv)")
    ap.add_argument("--ultimos", type=int, default=20, help="Quantidade de concursos a usar no backtest")
    ap.add_argument("--csv-out", required=True, help="Caminho do CSV de saída")

    # compatibilidade: você às vezes tentou --out (txt). Vamos aceitar.
    ap.add_argument("--out", dest="txt_out", default=None, help="(opcional) Caminho do TXT de saída")
    ap.add_argument("--txt-out", dest="txt_out2", default=None, help="(opcional) Caminho do TXT de saída")

    args = ap.parse_args()

    jogos_file = Path(args.jogos_file)
    base_file = Path(args.base)
    csv_out = Path(args.csv_out)

    txt_out: Optional[Path] = None
    if args.txt_out2:
        txt_out = Path(args.txt_out2)
    elif args.txt_out:
        txt_out = Path(args.txt_out)

    jogos = parse_jogos_arquivo(jogos_file)
    base = carregar_base(base_file)
    df = backtest(jogos, base, args.ultimos)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False)

    # se não especificar TXT, cria um .txt ao lado do CSV
    if txt_out is None:
        txt_out = csv_out.with_suffix(".txt")

    txt_out.parent.mkdir(parents=True, exist_ok=True)
    txt_out.write_text(df_to_txt(df, "BACKTEST"), encoding="utf-8")


if __name__ == "__main__":
    main()