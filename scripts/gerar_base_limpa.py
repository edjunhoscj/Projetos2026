import pandas as pd
from pathlib import Path


def is_dezena(x):
    return isinstance(x, (int, float)) and pd.notna(x) and 1 <= int(x) <= 25


def main():
    base_path = Path(__file__).resolve().parents[1] / "base" / "base_dados.xlsx"
    raw = pd.read_excel(base_path, header=None)

    rows = []
    for r in range(len(raw)):
        # pega a linha e tenta extrair números 1..25
        vals = raw.iloc[r].tolist()
        nums = [int(v) for v in vals if is_dezena(v)]

        # um sorteio da lotofácil tem 15 dezenas distintas
        if len(nums) >= 15:
            # tenta manter só 15 primeiras distintas preservando ordem
            seen = set()
            dezenas = []
            for n in nums:
                if n not in seen:
                    seen.add(n)
                    dezenas.append(n)
                if len(dezenas) == 15:
                    break

            if len(dezenas) == 15:
                rows.append(dezenas)

    if not rows:
        raise ValueError(
            "Não consegui extrair nenhum sorteio (15 dezenas) da planilha. "
            "Sua base está muito fora do padrão esperado."
        )

    # Cria dataframe: Concurso sequencial + D1..D15
    out = pd.DataFrame(rows, columns=[f"D{i}" for i in range(1, 16)])
    out.insert(0, "Concurso", range(1, len(out) + 1))

    # Cria Ciclo (a cada 25 concursos)
    tamanho = 25
    out["Ciclo"] = ((out["Concurso"] - out["Concurso"].min()) // tamanho) + 1

    saida = base_path.with_name("base_limpa.xlsx")
    out.to_excel(saida, index=False)

    print("✅ Base limpa criada com sucesso:")
    print(saida)
    print("Colunas:", list(out.columns))
    print("Total de linhas:", len(out))
    print(out.head(3))


if __name__ == "__main__":
    main()
