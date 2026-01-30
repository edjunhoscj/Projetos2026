from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from wizard_brain import construir_bandas


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="Base limpa XLSX")
    p.add_argument("--ultimos", type=int, default=300, help="Janela de análise")
    p.add_argument("--out", required=True, help="TXT de saída")
    args = p.parse_args()

    base_path = Path(args.base)
    df = pd.read_excel(base_path)

    bandas = construir_bandas(df, ultimos=int(args.ultimos))

    out = []
    out.append("==============================================")
    out.append("ANÁLISE DE PADRÕES — BANDAS (ÚLTIMOS N)")
    out.append("==============================================")
    out.append(f"N = {bandas.ultimos}")
    out.append("")

    out.append("SOMA das dezenas:")
    out.append(f"  média = {bandas.soma_mu:.2f} | sd = {bandas.soma_sd:.2f}")
    out.append(f"  banda (k={bandas.cfg.k_std}) = [{bandas.soma_lo:.2f}, {bandas.soma_hi:.2f}]")
    out.append("")

    out.append("PARES (qtd):")
    out.append(f"  média = {bandas.pares_mu:.2f} | sd = {bandas.pares_sd:.2f}")
    out.append(f"  banda (k={bandas.cfg.k_std}) = [{bandas.pares_lo:.2f}, {bandas.pares_hi:.2f}]")
    out.append("")

    out.append("FAIXAS (qtd por bloco):")
    for k in ["f1_5", "f6_10", "f11_15", "f16_20", "f21_25"]:
        out.append(
            f"  {k}: média={bandas.faixa_mu[k]:.2f} sd={bandas.faixa_sd[k]:.2f} "
            f"banda=[{bandas.faixa_lo[k]:.2f}, {bandas.faixa_hi[k]:.2f}]"
        )
    out.append("")

    out.append("MAX RUN (maior sequência consecutiva):")
    out.append(f"  média = {bandas.run_mu:.2f} | sd = {bandas.run_sd:.2f}")
    out.append(f"  banda (k={bandas.cfg.k_std}) = [{bandas.run_lo:.2f}, {bandas.run_hi:.2f}]")
    out.append("")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()