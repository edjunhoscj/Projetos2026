import requests
import pandas as pd
from pathlib import Path
import time

BASE_PATH = Path(__file__).resolve().parents[1] / "base"
BASE_PATH.mkdir(exist_ok=True)
ARQ_BASE = BASE_PATH / "base_limpa.xlsx"

URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/{}"
HEADERS = {"Accept": "application/json"}

def baixar_todos_concursos():
    concursos = []
    concurso_atual = 1

    # Primeiro obtenha o último concurso
    r = requests.get(URL.format(""), headers=HEADERS)
    ultimo = r.json()["numero"]

    print(f"🔍 Último concurso encontrado: {ultimo}")

    for n in range(1, ultimo + 1):
        try:
            r = requests.get(URL.format(n), headers=HEADERS, timeout=10)
            if r.status_code != 200:
                print(f"⚠ Falha no concurso {n}, pulando...")
                continue

            dados = r.json()
            dezenas = dados["listaDezenas"]

            registro = {
                "Concurso": n,
                **{f"D{i+1}": int(dezenas[i]) for i in range(15)},
            }

            concursos.append(registro)

            # Evitar bloqueio por excesso de chamadas
            time.sleep(0.2)

        except Exception as e:
            print(f"⚠ Erro ao obter concurso {n}: {e}")

    return concursos

def atualizar_base():
    registros = baixar_todos_concursos()

    df = pd.DataFrame(registros)
    df = df.sort_values("Concurso")

    df.to_excel(ARQ_BASE, index=False)

    print(f"✅ Base atualizada com {len(df)} concursos")
    print(f"📁 Arquivo salvo: {ARQ_BASE}")

if __name__ == "__main__":
    atualizar_base()
