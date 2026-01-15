from __future__ import annotations
import pandas as pd
from datetime import datetime
from pathlib import Path

OUTPUT = Path("outputs")

def carregar_csv_recente(prefixo: str) -> pd.DataFrame:
    arquivos = sorted(OUTPUT.glob(f"{prefixo}*.csv"))
    if not arquivos:
        return None
    return pd.read_csv(arquivos[-1])

def carregar_txt_recente(prefixo: str) -> list[str]:
    arquivos = sorted(OUTPUT.glob(f"{prefixo}*.txt"))
    if not arquivos:
        return []
    return Path(arquivos[-1]).read_text().splitlines()

def gerar_relatorio():
    agora = datetime.now().strftime("%d-%m-%Y")
    arquivo_saida = OUTPUT / f"relatorio_completo_{agora}.txt"

    linhas = []
    add = linhas.append

    # =========================================
    # CABEÇALHO
    # =========================================

    add("==============================================")
    add("        RELATÓRIO COMPLETO DO WIZARD")
    add(f"        DATA: {agora}")
    add("==============================================\n")

    # =========================================
    # BACKTEST AGRESSIVO
    # =========================================

    df_ag = carregar_csv_recente("backtest_agressivo")
    if df_ag is not None:
        add("------------ BACKTEST — MODO AGRESSIVO ------------")
        add(df_ag.to_string(index=False))
        add("\n")

    # =========================================
    # BACKTEST CONSERVADOR
    # =========================================

    df_cons = carregar_csv_recente("backtest_conservador")
    if df_cons is not None:
        add("------------ BACKTEST — MODO CONSERVADOR ------------")
        add(df_cons.to_string(index=False))
        add("\n")

    # =========================================
    # MÉDIA DOS MODOS
    # =========================================

    df_media = carregar_csv_recente("media")
    if df_media is not None:
        add("------------ MÉDIA COMPARATIVA ------------")
        add(df_media.to_string(index=False))
        add("\n")

    # =========================================
    # DISTRIBUIÇÃO DE ACERTOS
    # =========================================

    df_dist = carregar_csv_recente("dashboard_distribuicao_acertos")
    if df_dist is not None:
        add("------------ DISTRIBUIÇÃO DE ACERTOS ------------")
        add(df_dist.to_string(index=False))
        add("\n")

    # =========================================
    # JOGOS DO DIA (AGRESSIVO)
    # =========================================

    jogos_ag = carregar_txt_recente("jogos_agressivo")
    if jogos_ag:
        add("------------ JOGOS GERADOS — AGRESSIVO ------------")
        linhas.extend(jogos_ag)
        add("\n")

    # =========================================
    # JOGOS DO DIA (CONSERVADOR)
    # =========================================

    jogos_cons = carregar_txt_recente("jogos_conservador")
    if jogos_cons:
        add("------------ JOGOS GERADOS — CONSERVADOR ------------")
        linhas.extend(jogos_cons)
        add("\n")

    # =========================================
    # ANÁLISE INTERPRETADA
    # =========================================

    if df_ag is not None:
        melhor = df_ag.sort_values("media_acertos", ascending=False).iloc[0]
        add("============ INTERPRETAÇÃO DO MELHOR DO DIA ============")
        add(f"Melhor jogo do modo agressivo: jogo {melhor['Jogo']}")
        add(f"Média: {melhor['media_acertos']:.2f}")
        add(f"Máximo atingido: {melhor['max_acertos']}")
        add(f"Mínimo atingido: {melhor['min_acertos']}")
        add("\n")

    add("============ RECOMENDAÇÃO FINAL ============")
    add("✔ Use o melhor jogo do agressivo para explosão")
    add("✔ Combine com o mais estável do conservador")
    add("✔ Para apostar só 1 jogo: use o melhor agressivo")
    add("✔ Para 3 jogos: melhor agressivo + mais estável conservador + melhor equilíbrio")
    add("\n")

    # =========================================
    # SALVAR ARQUIVO
    # =========================================

    arquivo_saida.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Relatório salvo em: {arquivo_saida}")


if __name__ == "__main__":
    gerar_relatorio()