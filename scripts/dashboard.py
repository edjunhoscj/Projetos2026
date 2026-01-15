from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # backend para rodar sem tela (GitHub Actions)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTPUTS_DIR = Path("outputs")


# =========================================
#   HELPERS
# =========================================

def _encontrar_arquivo_mais_recente(padrao: str) -> Optional[Path]:
    """
    Procura em outputs/ o arquivo mais recente que case com o padrão,
    ex.: "backtest_agressivo_*.csv".
    """
    candidatos = list(OUTPUTS_DIR.glob(padrao))
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def _detectar_coluna_acertos(df: pd.DataFrame) -> str:
    """
    Tenta descobrir qual coluna representa o número de acertos no backtest.
    Ajusta aqui se seu backtest.py usar outro nome.
    """
    candidatos = [
        "melhor_acerto",
        "melhor_acertos",
        "max_acertos",
        "melhor_resultado",
        "acertos",
    ]
    for c in candidatos:
        if c in df.columns:
            return c
    raise ValueError(
        f"Não encontrei coluna de acertos. Colunas disponíveis: {list(df.columns)}"
    )


def _carregar_backtest(modo: str) -> pd.DataFrame:
    """
    Carrega o CSV de backtest mais recente para o modo informado
    (“agressivo” ou “conservador”).
    """
    padrao = f"backtest_{modo}_*.csv"
    caminho = _encontrar_arquivo_mais_recente(padrao)

    if caminho is None:
        raise FileNotFoundError(
            f"Não encontrei arquivos de backtest com padrão: {padrao} em {OUTPUTS_DIR}"
        )

    print(f"[{modo}] Usando backtest: {caminho.name}")
    df = pd.read_csv(caminho)
    df["modo"] = modo
    return df


# =========================================
#   DASHBOARD / MÉTRICAS
# =========================================

def gerar_dashboard():
    OUTPUTS_DIR.mkdir(exist_ok=True)

    # 1) Carrega agressivo + conservador
    df_ag = _carregar_backtest("agressivo")
    df_cs = _carregar_backtest("conservador")

    df = pd.concat([df_ag, df_cs], ignore_index=True)

    # Descobre qual coluna representa acertos
    col_acertos = _detectar_coluna_acertos(df)
    print(f"Coluna de acertos detectada: {col_acertos}")

    # Se não tiver coluna de índice de jogo, cria uma só para ordenação
    if "jogo" not in df.columns:
        # só para não quebrar — porém assume que existe alguma coluna identificando o jogo
        df["jogo"] = np.arange(1, len(df) + 1)

    # =====================================
    #  A) Distribuição de acertos (CSV + PNG)
    # =====================================
    dist = (
        df.groupby(["modo", col_acertos])
        .size()
        .reset_index(name="qtd")
        .sort_values([col_acertos, "modo"])
    )

    dist_csv = OUTPUTS_DIR / "dashboard_distribuicao_acertos.csv"
    dist.to_csv(dist_csv, index=False, encoding="utf-8-sig")
    print(f"Distribuição de acertos salva em: {dist_csv}")

    # Gráfico de barras comparando modos
    valores_acertos = sorted(dist[col_acertos].unique())
    x_idx = np.arange(len(valores_acertos))

    largura = 0.35  # deslocamento das barras

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, modo in enumerate(["agressivo", "conservador"]):
        sub = dist[dist["modo"] == modo]
        # garante alinhamento por valor de acertos
        y = []
        for v in valores_acertos:
            linha = sub[sub[col_acertos] == v]
            y.append(int(linha["qtd"].iloc[0]) if not linha.empty else 0)

        desloc = (i - 0.5) * largura
        ax.bar(x_idx + desloc, y, width=largura, label=modo.capitalize())

    ax.set_xticks(x_idx)
    ax.set_xticklabels([str(v) for v in valores_acertos])
    ax.set_xlabel("Número de acertos")
    ax.set_ylabel("Quantidade de jogos")
    ax.set_title("Distribuição de acertos - agressivo x conservador")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    dist_png = OUTPUTS_DIR / "dashboard_distribuicao_acertos.png"
    fig.tight_layout()
    fig.savefig(dist_png, dpi=150)
    plt.close(fig)
    print(f"Gráfico de distribuição salvo em: {dist_png}")

    # =====================================
    #  B) Desempenho por jogo + média móvel
    # =====================================

    resumo_linhas = []

    fig2, ax2 = plt.subplots(figsize=(10, 6))

    janela_mm = 5  # média móvel em 5 jogos (ajuste se quiser)

    for modo, estilo in [("agressivo", "-"), ("conservador", "--")]:
        sub = df[df["modo"] == modo].copy()

        # ordena pela coluna de acertos, só para fins visuais (maior para menor)
        sub = sub.sort_values(col_acertos, ascending=False).reset_index(drop=True)
        sub["idx"] = np.arange(1, len(sub) + 1)

        # curva de acertos por jogo
        ax2.plot(sub["idx"], sub[col_acertos], linestyle=estilo, marker="", label=f"{modo} (acertos)")

        # média móvel simples
        sub["mm"] = sub[col_acertos].rolling(window=janela_mm, min_periods=1).mean()
        ax2.plot(sub["idx"], sub["mm"], linestyle=":", marker="", label=f"{modo} (MM {janela_mm})")

        resumo_linhas.append(
            {
                "modo": modo,
                "jogos_avaliados": len(sub),
                "media_acertos": sub[col_acertos].mean(),
                "mediana_acertos": sub[col_acertos].median(),
                "max_acertos": sub[col_acertos].max(),
                "min_acertos": sub[col_acertos].min(),
            }
        )

    ax2.set_xlabel("Jogos (ordenados por desempenho)")
    ax2.set_ylabel("Acertos")
    ax2.set_title("Desempenho dos jogos e média móvel")
    ax2.grid(True, linestyle="--", alpha=0.3)
    ax2.legend()

    desempenho_png = OUTPUTS_DIR / "dashboard_desempenho_e_mm.png"
    fig2.tight_layout()
    fig2.savefig(desempenho_png, dpi=150)
    plt.close(fig2)
    print(f"Gráfico de desempenho salvo em: {desempenho_png}")

    # =====================================
    #  C) Resumo geral em CSV
    # =====================================

    resumo_df = pd.DataFrame(resumo_linhas)
    resumo_csv = OUTPUTS_DIR / "dashboard_resumo_geral.csv"
    resumo_df.to_csv(resumo_csv, index=False, encoding="utf-8-sig")
    print(f"Resumo geral salvo em: {resumo_csv}")

    print("\n✅ Dashboard gerado com sucesso (opção B - PNG + CSV).")


if __name__ == "__main__":
    gerar_dashboard()