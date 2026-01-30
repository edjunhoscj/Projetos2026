from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple, Set, Dict, Optional

import numpy as np
import pandas as pd

from wizard_brain import (
    detectar_quentes_frias,
    clusterizar_concursos,
    construir_bandas,
    calcular_score_inteligente,
)


@dataclass
class WizardConfig:
    modo: str
    ultimos: int
    jogos_finais: int

    # filtros / score
    max_seq_run: int = 4
    min_score: float = -1e18

    # amostragem
    candidatos_amostragem: int = 80_000
    seed: int = 42

    # presets
    preset: str = "auto"     # auto|solo|cobertura
    bandas: str = "soft"     # off|soft|hard


def carregar_base(base_path: Path) -> pd.DataFrame:
    if not base_path.exists():
        raise FileNotFoundError(f"Base histórica não encontrada em: {base_path}")

    df = pd.read_excel(base_path)
    esperadas = ["Concurso"] + [f"D{i}" for i in range(1, 16)]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas faltando na base: {faltando}")

    return df


def pegar_ultimos_concursos(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if "Concurso" in df.columns:
        df = df.sort_values("Concurso")
    return df.tail(int(n)).reset_index(drop=True)


def respeita_sequencia_maxima(dezenas: List[int], max_seq_run: int) -> bool:
    dezenas = sorted(dezenas)
    run = 1
    for i in range(1, len(dezenas)):
        if dezenas[i] == dezenas[i - 1] + 1:
            run += 1
            if run > max_seq_run:
                return False
        else:
            run = 1
    return True


def _parse_linha_jogo(jogo_str: str) -> List[int] | None:
    jogo_str = (jogo_str or "").strip()
    if not jogo_str:
        return None
    try:
        dezenas = [int(x) for x in jogo_str.split()]
    except ValueError:
        return None
    if len(dezenas) != 15:
        return None
    if any(d < 1 or d > 25 for d in dezenas):
        return None
    if len(set(dezenas)) != 15:
        return None
    return sorted(dezenas)


def amostrar_candidatos(
    comb_path: Path,
    ultimos_tuplas: Set[Tuple[int, ...]],
    max_seq_run: int,
    k: int,
    seed: int,
) -> List[Tuple[int, ...]]:
    """
    Reservoir sampling: amostra k candidatos sem viés de ordem.
    """
    rng = np.random.default_rng(seed)

    if not comb_path.exists():
        raise FileNotFoundError(f"Arquivo de combinações não encontrado: {comb_path}")

    amostra: List[Tuple[int, ...]] = []
    vistos: Set[Tuple[int, ...]] = set()

    chunk_size = 50_000
    reader = pd.read_csv(comb_path, header=None, chunksize=chunk_size)

    n_validos = 0
    for chunk in reader:
        for _, row in chunk.iterrows():
            jogo_str = str(row.iloc[0])
            dezenas = _parse_linha_jogo(jogo_str)
            if dezenas is None:
                continue

            jogo_tupla = tuple(dezenas)

            if jogo_tupla in ultimos_tuplas:
                continue

            if not respeita_sequencia_maxima(dezenas, max_seq_run):
                continue

            if jogo_tupla in vistos:
                continue

            n_validos += 1

            if len(amostra) < k:
                amostra.append(jogo_tupla)
                vistos.add(jogo_tupla)
            else:
                j = int(rng.integers(0, n_validos))
                if j < k:
                    antigo = amostra[j]
                    vistos.discard(antigo)
                    amostra[j] = jogo_tupla
                    vistos.add(jogo_tupla)

    return amostra


def escolher_jogos(
    comb_path: Path,
    ultimos_df: pd.DataFrame,
    base_df: pd.DataFrame,
    config: WizardConfig,
    freq: Dict[int, float],
    quentes: Set[int],
    frias: Set[int],
    modelo_cluster,
) -> List[Tuple[int, ...]]:
    modo = config.modo
    finais = config.jogos_finais

    print(f"🔍 Lendo combinações de: {comb_path}")
    print(f"Modo: {modo} | Jogos finais desejados: {finais}")
    print(f"Candidatos (amostragem): {config.candidatos_amostragem}")
    print(f"Preset: {config.preset}")
    print(f"Bandas: {config.bandas}")

    # tuplas dos últimos concursos (evitar repetição exata)
    ultimos_tuplas: Set[Tuple[int, ...]] = set()
    for _, linha in ultimos_df.iterrows():
        dezenas_ult = [int(linha[f"D{i}"]) for i in range(1, 16)]
        ultimos_tuplas.add(tuple(sorted(dezenas_ult)))

    # Bandas (model) baseado na base, recortado nos últimos N do wizard
    bandas_model = None
    if str(config.bandas).lower() in ("soft", "hard"):
        bandas_model = construir_bandas(base_df, ultimos=int(config.ultimos))

    candidatos = amostrar_candidatos(
        comb_path=comb_path,
        ultimos_tuplas=ultimos_tuplas,
        max_seq_run=config.max_seq_run,
        k=config.candidatos_amostragem,
        seed=config.seed,
    )

    if not candidatos:
        print("⚠️ Nenhum candidato válido encontrado na amostragem.")
        return []

    escolhidos: List[Tuple[int, ...]] = []
    cobertura_contagem: Dict[int, int] = {d: 0 for d in range(1, 26)}
    candidatos_restantes = candidatos.copy()

    for _ in range(finais):
        melhor = None
        melhor_score = -1e18

        for jogo_tupla in candidatos_restantes:
            dezenas = list(jogo_tupla)

            score = calcular_score_inteligente(
                dezenas=dezenas,
                ultimos_tuplas=ultimos_tuplas,
                cobertura_contagem=cobertura_contagem,
                quentes=quentes,
                frias=frias,
                freq=freq,
                modelo_cluster=modelo_cluster,
                config=config,
                escolhidos=escolhidos,
                bandas_model=bandas_model,
            )

            if score > melhor_score:
                melhor_score = score
                melhor = jogo_tupla

        if melhor is None:
            break

        if melhor_score < config.min_score:
            break

        escolhidos.append(melhor)
        for d in melhor:
            cobertura_contagem[int(d)] += 1

        candidatos_restantes = [c for c in candidatos_restantes if c != melhor]

    return escolhidos


def imprimir_resumo(jogos: List[Tuple[int, ...]], config: WizardConfig) -> None:
    print("\n========================================")
    print("        JOGOS GERADOS PELO WIZARD       ")
    print("========================================")
    print(f"Modo: {config.modo}")
    print(f"Jogos finais: {len(jogos)}")
    print(f"Preset: {config.preset}")
    print(f"Bandas: {config.bandas}\n")

    for idx, jogo in enumerate(jogos, start=1):
        seq = " ".join(f"{d:02d}" for d in jogo)
        print(f"Jogo {idx:02d}: {seq}")

    print("\nBoa sorte! 🍀")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wizard Lotofácil - gera jogos filtrando combinações.")
    parser.add_argument("--modo", choices=["agressivo", "conservador"], default="conservador")
    parser.add_argument("--ultimos", type=int, default=300)
    parser.add_argument("--finais", type=int, default=5)
    parser.add_argument("--candidatos", type=int, default=300_000)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--preset",
        choices=["auto", "solo", "cobertura"],
        default="auto",
        help="Preset de diversidade: auto|solo|cobertura",
    )

    parser.add_argument(
        "--bandas",
        choices=["off", "soft", "hard"],
        default="soft",
        help="Bandas de padrões (off|soft|hard). soft = penaliza fora do típico",
    )

    args = parser.parse_args()

    base_path = Path("base/base_limpa.xlsx")
    comb_path = Path("combinacoes/combinacoes_inteligentes.csv")

    config = WizardConfig(
        modo=args.modo,
        ultimos=args.ultimos,
        jogos_finais=args.finais,
        max_seq_run=4,
        min_score=-1e18,
        candidatos_amostragem=args.candidatos,
        seed=args.seed,
        preset=args.preset,
        bandas=args.bandas,
    )

    print("==============================================")
    print("WIZARD LOTOFÁCIL - CLI")
    print("==============================================")
    print(f"Base histórica: {base_path}")
    print(f"Modo: {config.modo}")
    print(f"Últimos: {config.ultimos} concursos")
    print(f"Jogos finais desejados: {config.jogos_finais}")
    print(f"Candidatos (amostragem): {config.candidatos_amostragem}")
    print(f"Preset: {config.preset}")
    print(f"Bandas: {config.bandas}")
    print("==============================================\n")

    base_df = carregar_base(base_path)
    ultimos_df = pegar_ultimos_concursos(base_df, config.ultimos)

    estat = detectar_quentes_frias(base_df, ultimos=min(600, max(50, config.ultimos)))
    freq = estat.freq
    quentes = estat.quentes
    frias = estat.frias

    modelo_cluster = clusterizar_concursos(base_df)

    jogos = escolher_jogos(
        comb_path=comb_path,
        ultimos_df=ultimos_df,
        base_df=base_df,
        config=config,
        freq=freq,
        quentes=quentes,
        frias=frias,
        modelo_cluster=modelo_cluster,
    )

    imprimir_resumo(jogos, config)


if __name__ == "__main__":
    main()