from __future__ import annotations

from pathlib import Path
import pandas as pd


OUT_DIR = Path("outputs")


def pegar_mais_recente(padrao: str) -> Path | None:
    arquivos = sorted(OUT_DIR.glob(padrao))
    return arquivos[-1] if arquivos else None


def gerar_alerta_para_modo(modo: str, limite_max: int = 13) -> str:
    padrao = f"backtest_{modo}_*.csv"
    arq = pegar_mais_recente(padrao)
    if not arq or not arq.exists():
        return ""

    df = pd.read_csv(arq)

    # garante colunas
    if "Jogo" not in df.columns or "max_acertos" not in df.columns:
        return ""

    fortes = df[df["max_acertos"] >= limite_max].copy()
    if fortes.empty:
        return ""

    linhas = []
    linhas.append(f"### Modo {modo} – jogos com max_acertos >= {limite_max}")
    for _, row in fortes.iterrows():
        jogo = row["Jogo"]
        media = row.get("media_acertos", None)
        max_a = row["max_acertos"]
        min_a = row.get("min_acertos", None)

        base = f"- {jogo} | max: {max_a}"
        extras = []
        if media is not None:
            extras.append(f"média: {media:.3f}")
        if min_a is not None:
            extras.append(f"min: {min_a}")
        if extras:
            base += " | " + " | ".join(extras)

        linhas.append(base)

    linhas.append("")  # linha em branco
    return "\n".join(linhas)


def main() -> None:
    texto_ag = gerar_alerta_para_modo("agressivo", limite_max=13)
    texto_co = gerar_alerta_para_modo("conservador", limite_max=13)

    alerta_path = OUT_DIR / "alertas_email.txt"

    if not texto_ag and not texto_co:
        alerta_path.write_text("", encoding="utf-8")
        print("Nenhum alerta gerado (nenhum jogo com max_acertos >= 13).")
        return

    linhas = []
    linhas.append("ALERTAS WIZARD LOTOFÁCIL\n")
    linhas.append("Jogos que já fizeram 13 pontos ou mais nos backtests recentes.\n")
    if texto_ag:
        linhas.append(texto_ag)
    if texto_co:
        linhas.append(texto_co)

    alerta_path.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✅ Alerta escrito em {alerta_path}")


if __name__ == "__main__":
    main()