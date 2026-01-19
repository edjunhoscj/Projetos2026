from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Set, Tuple, Optional

import pandas as pd


RE_15_NUMS = re.compile(r"(?:^|:)\s*((?:\d{1,2}\s+){14}\d{1,2})\s*$")


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_jogos_arquivo(path: Path) -> List[Set[int]]:
    """
    Extrai jogos (15 dezenas) de um TXT do wizard.

    Aceita linhas como:
      - "Jogo 01: 02 03 ... 25"
      - "02 03 05 ... 25"
    """
    txt = _read_text(path)
    linhas = txt.splitlines()

    jogos: List[Set[int]] = []

    for ln in linhas:
        ln = ln.strip()
        if not ln:
            continue

        m = RE_15_NUMS.search(ln)
        if m:
            nums = [int(x) for x in m.group(1).split()]
            if len(nums) == 15:
                jogos.append(set(nums))
            continue

        # fallback: pega qualquer linha que tenha exatamente 15 números 1-25
        nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", ln)]
        nums = [n for n in nums if 1 <= n <= 25]
        if len(nums) == 15:
            jogos.append(set(nums))

    # remove duplicados preservando ordem
    uniq: List[Set[int]] = []
    seen = set()
    for s in jogos:
        key = tuple(sorted(s))
        if key not in seen:
            seen.add(key)
            uniq.append(s)

    if not uniq:
        head = "\n".join(linhas[:120])
        raise ValueError(
            "Nenhum jogo foi encontrado no arquivo.\n"
            "Confirme se o TXT foi gerado pelo wizard e contém linhas com 15 dezenas.\n\n"
            "---- HEAD (primeiras 120 linhas) ----\n"
            f"{head}\n"
        )

    return uniq


def _detect_dezenas_cols(df: pd.DataFrame) -> List[str]:
    """
    Tenta detectar automaticamente colunas que representem dezenas (15 colunas).
    Estratégia: pega colunas numéricas com valores entre 1 e 25, e escolhe as 15 primeiras.
    """
    numeric_cols = []
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() < 0.6:
            continue
        vmin = s.min(skipna=True)
        vmax = s.max(skipna=True)
        if pd.notna(vmin) and pd.notna(vmax) and 1 <= vmin <= 25 and 1 <= vmax <= 25:
            numeric_cols.append(c)

    # se tiver colunas com nomes típicos
    prefer = [c for c in df.columns if str(c).lower() in {f"d{i}" for i in range(1, 16)}]
    if len(prefer) >= 15:
        return prefer[:15]

    if len(numeric_cols) >= 15:
        return numeric_cols[:15]

    raise ValueError(
        "Não consegui detectar 15 colunas de dezenas na base.\n"
        "Verifique o formato do arquivo base/base_limpa.xlsx."
    )


def load_base_sorteios(base_path: Path, ultimos: int) -> List[Set[int]]:
    """
    Lê base/base_limpa.xlsx e devolve lista dos últimos N concursos como conjuntos de dezenas.
    """
    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    # tenta carregar a primeira planilha
    df = pd.read_excel(base_path)

    if df.empty:
        raise ValueError("Base está vazia.")

    cols = _detect_dezenas_cols(df)

    # pega os últimos N registros
    df_tail = df.tail(int(ultimos)).copy()

    sorteios: List[Set[int]] = []
    for _, row in df_tail.iterrows():
        nums = []
        for c in cols:
            v = row.get(c)
            try:
                n = int(v)
            except Exception:
                continue
            if 1 <= n <= 25:
                nums.append(n)
        if len(nums) >= 15:
            sorteios.append(set(nums[:15]))
        elif len(nums) == 15:
            sorteios.append(set(nums))

    if not sorteios:
        raise ValueError("Não consegui extrair sorteios (15 dezenas) da base.")

    return sorteios


def backtest(jogos: List[Set[int]], sorteios: List[Set[int]]) -> pd.DataFrame:
    rows = []
    for idx, jogo in enumerate(jogos, start=1):
        acertos = [len(jogo.intersection(s)) for s in sorteios]
        rows.append(
            {
                "jogo": idx,
                "media_acertos": sum(acertos) / len(acertos),
                "max_acertos": max(acertos),
                "min_acertos": min(acertos),
                "11.0": acertos.count(11),
                "12.0": acertos.count(12),
                "13.0": acertos.count(13),
                "14.0": acertos.count(14),
                "15.0": acertos.count(15),
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["media_acertos", "max_acertos"], ascending=[False, False]).reset_index(drop=True)
    return df


def write_txt(df: pd.DataFrame, out_txt: Path, titulo: str) -> None:
    lines = []
    lines.append("=" * 46)
    lines.append(f"{titulo}")
    lines.append("=" * 46)
    lines.append("")
    lines.append("Resumo por jogo (ordenado pela melhor média de acertos):")
    lines.append("")
    # mostra colunas principais
    view_cols = ["jogo", "media_acertos", "max_acertos", "min_acertos", "11.0", "12.0", "13.0"]
    view = df[view_cols].copy()
    view["media_acertos"] = view["media_acertos"].map(lambda x: f"{x:.4f}")
    lines.append(view.to_string(index=False))
    lines.append("")
    lines.append("Legenda:")
    lines.append("- media_acertos : média de acertos do jogo nos concursos analisados")
    lines.append("- max_acertos   : maior número de acertos que o jogo já fez")
    lines.append("- min_acertos   : menor número de acertos que o jogo já fez")
    lines.append("- colunas 11.0, 12.0, 13.0 etc: quantas vezes o jogo fez 11, 12, 13 pontos...")
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jogos-file", required=True, help="TXT gerado pelo wizard (com dezenas)")
    ap.add_argument("--base", default="base/base_limpa.xlsx", help="Base limpa (xlsx)")
    ap.add_argument("--ultimos", type=int, default=20, help="Quantidade de concursos a considerar")
    ap.add_argument("--csv-out", required=True, help="Saída CSV do backtest")
    ap.add_argument("--out", default=None, help="Saída TXT formatada (opcional)")
    ap.add_argument("--titulo", default="BACKTEST", help="Título do TXT (se --out for usado)")
    args = ap.parse_args()

    jogos_file = Path(args.jogos_file)
    base_path = Path(args.base)
    csv_out = Path(args.csv_out)
    txt_out: Optional[Path] = Path(args.out) if args.out else None

    jogos = parse_jogos_arquivo(jogos_file)
    sorteios = load_base_sorteios(base_path, args.ultimos)
    df = backtest(jogos, sorteios)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False)

    if txt_out is not None:
        txt_out.parent.mkdir(parents=True, exist_ok=True)
        write_txt(df, txt_out, args.titulo)

    print("OK - Backtest concluído")
    print(f"CSV: {csv_out}")
    if txt_out is not None:
        print(f"TXT: {txt_out}")


if __name__ == "__main__":
    main()