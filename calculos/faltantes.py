from __future__ import annotations

import pandas as pd


def numeros_faltantes_ciclo(base_dados):
    """
    Calcula os números faltantes dentro do ciclo atual.

    Espera colunas:
      - Concurso
      - D1 ... D15
      - Ciclo

    Retorna (compatível com o restante do projeto):
      - faltantes: list[int]
      - maior_peso: int  (frequência máxima de uma dezena no ciclo atual)
    """

    # Verificação básica
    if base_dados is None or base_dados.empty:
        raise ValueError("Base de dados vazia ou não carregada.")

    if "Ciclo" not in base_dados.columns:
        raise ValueError("Coluna 'Ciclo' não encontrada na base.")

    # Descobre colunas de dezenas existentes
    dezenas_cols = [c for c in base_dados.columns if str(c).startswith("D")]
    if len(dezenas_cols) < 15:
        # fallback se vier no formato 1..15
        dezenas_cols = [c for c in base_dados.columns if str(c).isdigit()]

    if not dezenas_cols:
        raise ValueError(
            f"Não encontrei colunas de dezenas (D1..D15). Colunas: {list(base_dados.columns)}"
        )

    # Último ciclo disponível
    ciclo_atual = base_dados["Ciclo"].max()

    # Filtra apenas registros do ciclo atual
    df_ciclo = base_dados[base_dados["Ciclo"] == ciclo_atual].copy()

    if df_ciclo.empty:
        raise ValueError("Nenhum registro encontrado para o ciclo atual.")

    # Todas as dezenas possíveis (1 a 25)
    todas = set(range(1, 26))

    # Coleta as dezenas já usadas no ciclo e também calcula frequência
    usadas = set()
    contagem = {}

    for _, linha in df_ciclo.iterrows():
        for col in dezenas_cols:
            valor = linha.get(col)
            if pd.notna(valor):
                try:
                    dz = int(valor)
                except Exception:
                    continue
                if 1 <= dz <= 25:
                    usadas.add(dz)
                    contagem[dz] = contagem.get(dz, 0) + 1

    # Dezenas que ainda não saíram
    faltantes = sorted(todas - usadas)

    # Maior peso (maior frequência no ciclo atual)
    maior_peso = max(contagem.values()) if contagem else 0

    return faltantes, maior_peso
