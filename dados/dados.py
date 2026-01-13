from __future__ import annotations

from pathlib import Path
import pandas as pd


def carregar_dados() -> pd.DataFrame:
    """
    Carrega a base de dados para o projeto.

    Prioridade:
    1) base/base_limpa.xlsx (base tabular e consistente)
    2) base/base_dados.xlsx (fallback)
    """
    root = Path(__file__).resolve().parents[1]
    base_limpa = root / "base" / "base_limpa.xlsx"
    base_original = root / "base" / "base_dados.xlsx"

    base_path = base_limpa if base_limpa.exists() else base_original
    print("Usando base:", base_path)

    df = pd.read_excel(base_path)

    # Normaliza nomes de colunas
    df.columns = df.columns.astype(str).str.strip()

    # Se já veio limpo, normalmente terá Concurso, D1..D15 e Ciclo.
    # Garante Ciclo se faltar.
    if "Ciclo" not in df.columns:
        if "Concurso" in df.columns:
            df["Concurso"] = pd.to_numeric(df["Concurso"], errors="coerce")
            df = df.dropna(subset=["Concurso"])
            df["Concurso"] = df["Concurso"].astype(int)
            tamanho = 25
            df["Ciclo"] = ((df["Concurso"] - df["Concurso"].min()) // tamanho) + 1
        else:
            raise ValueError(
                f"Base carregada não possui 'Ciclo' nem 'Concurso'. Colunas: {list(df.columns)}"
            )

    return df


from sklearn.model_selection import train_test_split

def dividir_dados(df, test_size=0.2, random_state=42):
    """
    Divide o DataFrame em treino e teste e retorna também a lista de atributos (features).

    Retorna:
      x_treino, x_teste, y_treino, y_teste, atributos
    """
    df = df.copy()

    # Features: D1..D15
    atributos = [c for c in df.columns if str(c).startswith("D")]
    if not atributos:
        raise ValueError(f"Não encontrei colunas D1..D15. Colunas: {list(df.columns)}")

    X = df[atributos].values

    # ⚠️ ALVO (y)
    # Como sua base não tem um alvo "real", criamos um alvo dummy.
    # Isso só serve para o modelo não quebrar. O ideal é definir um alvo real no modelo.
    y = [0] * len(df)

    x_treino, x_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    return x_treino, x_teste, y_treino, y_teste, atributos
