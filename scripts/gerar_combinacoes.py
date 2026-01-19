from __future__ import annotations

import argparse
import random
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="combinacoes/combinacoes_inteligentes.txt")
    ap.add_argument("--qtd", type=int, default=200000, help="quantidade de combinações para gerar")
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    random.seed(args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen = set()
    linhas = []

    # gera por amostragem e evita duplicados
    # OBS: 25C15 é gigante, então aqui é amostra "boa o suficiente"
    target = int(args.qtd)
    tries = 0
    max_tries = target * 10

    while len(linhas) < target and tries < max_tries:
        tries += 1
        jogo = tuple(sorted(random.sample(range(1, 26), 15)))
        if jogo in seen:
            continue
        seen.add(jogo)
        linhas.append(" ".join(f"{x:02d}" for x in jogo))

    out_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"OK - Geradas {len(linhas)} combinações em: {out_path}")


if __name__ == "__main__":
    main()