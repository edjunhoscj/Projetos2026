import pandas as pd
import requests
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parents[1] / "base"
BASE_PATH.mkdir(exist_ok=True)
ARQ_BASE = BASE_PATH / "base_limpa.xlsx"

URL_CAIXA = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"


def baixar_concursos():
    """
    Tenta baixar os concursos da API da Caixa.

    Em caso de erro de rede, timeout ou resposta estranha,
    NÃO levanta exceção: apenas imprime um aviso e retorna None.

    Isso é importante pro GitHub Actions não falhar o workflow inteiro.
    """
    try:
        print(f"🔎 Acessando API da Caixa em: {URL_CAIXA}")
        r = requests.get(URL_CAIXA, timeout=30)
        r.raise_for_status()

        dados = r.json()

        # A API normalmente retorna uma lista de concursos
        if not isinstance(dados, list) or len(dados) == 0:
            print("⚠️ Resposta inesperada da API da Caixa. Mantendo base atual.")
            return None

        print(f"✅ API respondeu com {len(dados)} concursos.")
        return dados

    except Exception as e:
        print("⚠️ Erro ao acessar API da Caixa.")
        print(f"   Detalhes: {e}")
        print("   A base NÃO será atualizada nesta execução.")
        return None


def atualizar_base():
    dados = baixar_concursos()

    # Se não conseguiu baixar, não quebra o job
    if dados is None:
        if ARQ_BASE.exists():
            print("ℹ️ Usando arquivo de base já existente:")
            print(f"   {ARQ_BASE}")
        else:
            print("❌ Nenhum arquivo base_limpa.xlsx existe ainda.")
            print("   Rode o script localmente quando a API estiver ok para criar a base.")
        return False

    registros = []
    for d in dados:
        dezenas = sorted(d["dezenas"])
        registro = {
            "Concurso": d["concurso"],
            **{f"D{i+1}": dezenas[i] for i in range(15)},
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

    return True


if __name__ == "__main__":
    atualizar_base()
