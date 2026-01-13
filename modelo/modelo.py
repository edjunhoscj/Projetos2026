from __future__ import annotations

import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Input

from dados.dados import dividir_dados


def criar_modelo(
    base_dados,
    primeira_camada: int = 30,
    segunda_camada: int = 15,
    terceira_camada: int = 15,
    saida: int = 1,
    periodo: int = 50,
    lote: int = 15,
):
    """
    Cria o modelo sequencial com três camadas.

    Retorna:
      (modelo, acuracia_float)
    """

    x_treino, x_teste, y_treino, y_teste, atributos = dividir_dados(base_dados)

    # --------- garante tipos/formatos aceitos pelo Keras ---------
    x_treino = np.asarray(x_treino, dtype=np.float32)
    x_teste = np.asarray(x_teste, dtype=np.float32)

    y_treino = np.asarray(y_treino, dtype=np.float32).reshape(-1, 1)
    y_teste = np.asarray(y_teste, dtype=np.float32).reshape(-1, 1)
    # ------------------------------------------------------------

    # Criando o modelo (Input primeiro, sem input_dim nas Dense)
    modelo = Sequential()
    modelo.add(Input(shape=(len(atributos),)))
    modelo.add(Dense(primeira_camada, activation="relu"))
    modelo.add(Dense(segunda_camada, activation="relu"))
    modelo.add(Dense(terceira_camada, activation="relu"))
    modelo.add(Dense(saida, activation="sigmoid"))

    # Compilando o modelo
    modelo.compile(
        loss="binary_crossentropy",
        optimizer="adam",
        metrics=["accuracy"],
    )

    # Treinando o modelo
    modelo.fit(
        x_treino,
        y_treino,
        epochs=periodo,
        batch_size=lote,
        verbose=1,
    )

    # Avaliação do modelo
    loss, acc = modelo.evaluate(x_teste, y_teste, verbose=0)

    return modelo, float(acc)
