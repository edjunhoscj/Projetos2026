from __future__ import annotations

from datetime import datetime
import csv
import os
from pathlib import Path

from processamento.reajustar_dados import remover_resultado_concursos
from processamento.possibilidades import obter_possibilidades
from processamento.resultados import resultados_ordenados
from calculos.pesos import calcular_numero_pesos
from sorteios.sortear import sortear_numeros
from modelo.modelo import criar_modelo
from dados.dados import carregar_dados

from pandas import DataFrame


# ---------- AJUSTE: garante que caminhos relativos funcionem ----------
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
# --------------------------------------------------------------------


def salvar_saida(pontuacao, predicao_alvo, probabilidade, sorteados, jogo):
    os.makedirs("outputs", exist_ok=True)
    agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    acuracia = round((pontuacao * 100), 1)
    pred = float(predicao_alvo[0][0])
    nums_sorteados = [int(n[0]) for n in sorteados]
    nums_ordenados = [int(x) for x in jogo]

    # TXT
    txt_path = os.path.join("outputs", f"resultado_{agora}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Acuracidade do Modelo: {acuracia}%\n")
        f.write("0 = Não tem chance (no modelo) | 1 = Tem chance (no modelo)\n")
        f.write(f"Resultado (Previsão Modelo): {pred}\n\n")
        f.write(f"Score do modelo (0–100): {probabilidade}%\n")
        f.write("Obs.: isso NÃO é chance real de prêmio; é um score interno do modelo.\n\n")
        f.write(f"Números sorteados: {nums_sorteados}\n")
        f.write(f"Números ordenados: {nums_ordenados}\n")

    # CSV (histórico)
    csv_path = os.path.join("outputs", "historico_resultados.csv")
    header = [
        "timestamp",
        "acuracia_modelo",
        "pred_modelo",
        "score_0_100",
        "numeros_ordenados",
        "numeros_sorteados",
    ]
    row = [
        agora,
        acuracia,
        pred,
        float(probabilidade),
        " ".join(map(str, nums_ordenados)),
        " ".join(map(str, nums_sorteados)),
    ]

    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow(row)

    print(f"\n✅ Saída salva em:\n- {txt_path}\n- {csv_path}\n")


# ===================== EXECUÇÃO DO PROJETO ===================== #

# Carrega a base de dados (agora prioriza base/base_limpa.xlsx no dados.py)
dados = carregar_dados()

# Inicialização das variáveis
probabilidade = 0.0
predicao_alvo = 0.0
sorteados = []
procurando = 0

# Score desejado
prob_alvo = 100.0

# Pesos das dezenas
peso, numero_pesos = calcular_numero_pesos(dados)

# Modelo e acuracidade
modelo, pontuacao = criar_modelo(dados)

# Ajustes iniciais
print()
print("\033[1;33m[Carregando e reajustando os demais dados...]\033[m")
print()

possibilidades = obter_possibilidades()
resultado_concursos = resultados_ordenados(dados)
possibilidades_atualizada = remover_resultado_concursos(
    possibilidades,
    resultado_concursos
)

jogo_aceito = False

# Loop principal
while probabilidade < prob_alvo and not jogo_aceito:

    sorteados = sortear_numeros(peso, numero_pesos)
    jogo = sorted([n[0] for n in sorteados])

    y_alvo = DataFrame(sorteados)
    y_alvo = y_alvo.iloc[:, 0].values.reshape(1, 15)

    predicao_alvo = modelo.predict(y_alvo)
    probabilidade = round((predicao_alvo[0][0] * 100), 1)

    if probabilidade >= prob_alvo:
        jogo_aceito = True if jogo in possibilidades_atualizada else False
    else:
        jogo_aceito = False

    procurando += 1

    sequencia = [str(n[0]).zfill(2) for n in sorteados]

    print(
        f"Alvo = ({prob_alvo}%) - ACURAC.: {round((pontuacao * 100), 1)}% "
        f"- Rep.: {str(procurando).zfill(7)} "
        f"- Score Enc.: ({str(probabilidade).zfill(2)}%) Sequência: [ ",
        end=""
    )
    print(*sequencia, "]")

    if not jogo_aceito:
        probabilidade = 0.0


# ===================== RESULTADOS FINAIS ===================== #

print(f"\nAcuracidade do Modelo: {round((pontuacao * 100), 1)}%")

print("\n0 = Não tem chance de ganhar | 1 = Tem chance de ganhar")
print(f"Resultado: (Previsão Modelo) = {predicao_alvo[0][0]}")

print(f"\nScore do modelo (0–100): {probabilidade}%")
print("Obs.: isso NÃO é chance real de prêmio; é um score interno do modelo.")

print(f"\nNúmeros sorteados:  {[n[0] for n in sorteados]}")
print(f"\nNúmeros ordenados:  {jogo}")

# Salva os resultados
salvar_saida(pontuacao, predicao_alvo, probabilidade, sorteados, jogo)
