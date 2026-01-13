#!/usr/bin/env python3
"""
gerar_combinacoes.py

Gera o arquivo combinacoes/combinacoes.csv com TODAS as combinações
possíveis da Lotofácil (25 dezenas escolhendo 15).

Formato do CSV:
- 1 coluna (sem cabeçalho)
- cada linha = string com 15 dezenas zero-padded, separadas por espaço
  ex: "01 02 03 04 05 06 07 08 09 10 11 12 13 14 15"

Esse formato é compatível com o que o código usa quando monta a coluna
"jogo" como string.
"""

import csv
import itertools
import logging
import os
import sys
import time
from math import comb
from pathlib import Path


# ---------------- LOGGING ---------------- #

def configurar_logger() -> logging.Logger:
    raiz = Path(__file__).resolve().parent.parent  # pasta do projeto
    logs_dir = raiz / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_path = logs_dir / "gerar_combinacoes.log"

    logger = logging.getLogger("gerar_combinacoes")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch_fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
    ch.setFormatter(ch_fmt)

    # Arquivo
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fh_fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)

    logger.info("Logger inicializado. Log em: %s", log_path)
    return logger


# ------------- GERAÇÃO DAS COMBINAÇÕES ------------- #

def gerar_combinacoes_lotofacil(logger: logging.Logger) -> None:
    raiz = Path(__file__).resolve().parent.parent
    combinacoes_dir = raiz / "combinacoes"
    combinacoes_dir.mkdir(exist_ok=True)

    saida_path = combinacoes_dir / "combinacoes.csv"

    # Número total de combinações C(25, 15)
    total = comb(25, 15)  # 3.268.760
    logger.info("Iniciando geração das combinações Lotofácil.")
    logger.info("Total esperado de combinações: %d", total)
    logger.info("Arquivo de saída: %s", saida_path)

    if saida_path.exists():
        logger.warning("Arquivo já existe e será sobrescrito: %s", saida_path)

    inicio = time.time()
    linhas_geradas = 0
    checkpoint = 100_000  # log a cada 100k linhas

    try:
        with saida_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Gera combinações: números de 1 a 25, escolhendo 15
            for idx, comb15 in enumerate(
                itertools.combinations(range(1, 26), 15),
                start=1
            ):
                # Ex: "01 02 03 ... 15"
                jogo_str = " ".join(f"{n:02d}" for n in comb15)
                writer.writerow([jogo_str])
                linhas_geradas += 1

                if idx % checkpoint == 0:
                    perc = idx / total * 100
                    logger.info(
                        "Progresso: %d/%d (%.2f%%)",
                        idx, total, perc
                    )

    except Exception as e:
        logger.exception("Erro ao gerar combinações: %s", e)
        raise

    fim = time.time()
    duracao = fim - inicio
    logger.info("Geração concluída.")
    logger.info("Linhas geradas: %d", linhas_geradas)
    logger.info("Tempo total: %.2f segundos (%.2f minutos)",
                duracao, duracao / 60.0)

    if linhas_geradas != total:
        logger.warning(
            "ATENÇÃO: linhas_geradas (%d) diferente do total esperado (%d)!",
            linhas_geradas, total
        )
    else:
        logger.info("Linhas conferidas: quantidade bate com o esperado.")


def main():
    logger = configurar_logger()
    try:
        gerar_combinacoes_lotofacil(logger)
    except Exception:
        logger.error("Falha na geração das combinações.")
        sys.exit(1)
    logger.info("Processo finalizado com sucesso.")
    sys.exit(0)


if __name__ == "__main__":
    main()
