import pandas as pd
import requests
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parents[1] / "base"
BASE_PATH.mkdir(exist_ok=True)
ARQ_BASE = BASE_PATH / "base_limpa.xlsx"

URL_CAIXA = (
    "https://loteriascaixa-api.herokuapp.com/api/lotofacil"
)

def baixar_concursos():
    r = requests.get(URL_CAIXA, timeout=20)
    r.raise_for_status()
    dados = r.json()
    return dados

def atualizar_base():
    dados = baixar_concursos()

    registros = []
    for d in dados:
        dezenas = sorted(d["dezenas"])
        registro = {
            "Concurso": d["concurso"],
            **{f"D{i+1}": dezenas[i] for i in range(15)}
        }
        registros.append(registro)

    df = pd.DataFrame(registros).sort_values("Concurso")

    # Ciclo simples: reseta quando fecha 25 dezenas
    ciclo = 1
    usadas = set()
    ciclos = []
    for _, row in df.iterrows():
        usadas |= set(row[f"D{i}"] for i in range(1, 16))
        if len(usadas) == 25:
            usadas.clear()
            ciclo += 1
        ciclos.append(ciclo)

    df["Ciclo"] = ciclos
    df.to_excel(ARQ_BASE, index=False)

    print(f"✅ Base atualizada com {len(df)} concursos")
    print(f"📁 Arquivo: {ARQ_BASE}")

if __name__ == "__main__":
    atualizar_base()
