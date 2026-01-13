# lotofacil/scripts/gerar_combinacoes.py
from itertools import combinations
from pathlib import Path
import csv


def gerar_combinacoes(
    n_dezenas: int = 25,
    tamanho_jogo: int = 15,
    nome_arquivo: str = "combinacoes.csv",
):
    """
    Gera todas as combinações possíveis de 'tamanho_jogo' dezenas
    a partir de 'n_dezenas' (1..n_dezenas) e salva em CSV.

    Exemplo: n_dezenas=25, tamanho_jogo=15 -> 3.268.760 linhas.
    """

    # pasta combinacoes/ dentro do projeto
    raiz = Path(__file__).resolve().parents[1]  # sobe de scripts/ para raiz do projeto
    pasta_combinacoes = raiz / "combinacoes"
    pasta_combinacoes.mkdir(exist_ok=True)

    saida = pasta_combinacoes / nome_arquivo

    print(f"📂 Gerando combinações em: {saida}")
    print(f"- Dezenas: 1..{n_dezenas}")
    print(f"- Tamanho do jogo: {tamanho_jogo}")

    total = 0

    with open(saida, "w", newline="") as f:
        writer = csv.writer(f)

        # Cabeçalho: Jogo, D1..D15
        header = ["Jogo"] + [f"D{i}" for i in range(1, tamanho_jogo + 1)]
        writer.writerow(header)

        # Gera as combinações em streaming (sem lotar memória)
        for idx, comb in enumerate(
            combinations(range(1, n_dezenas + 1), tamanho_jogo), start=1
        ):
            writer.writerow((idx, *comb))
            total += 1

            # feedback a cada 100.000 linhas
            if idx % 100_000 == 0:
                print(f"- {idx:,} combinações geradas...")

    print(f"✅ Concluído! Total de jogos gerados: {total:,}")
    print(f"Arquivo salvo em: {saida}")


if __name__ == "__main__":
    gerar_combinacoes()
