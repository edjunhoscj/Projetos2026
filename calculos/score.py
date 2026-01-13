def score_jogo(jogo, freq, atraso):
    s1 = sum(freq.get(n, 0) for n in jogo)
    s2 = sum(atraso.get(n, 0) for n in jogo)

    pares = sum(1 for n in jogo if n % 2 == 0)
    impares = 15 - pares
    equilibrio_pi = 1 - abs(pares - impares)/15

    baixos = sum(1 for n in jogo if n <= 13)
    altos = 15 - baixos
    equilibrio_ba = 1 - abs(baixos - altos)/15

    return (
        0.4 * s1 +
        0.2 * s2 +
        0.15 * equilibrio_pi +
        0.15 * equilibrio_ba
    )
