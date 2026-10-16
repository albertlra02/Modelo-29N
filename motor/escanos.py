"""
Motor de reparto de escaños del Congreso (LOREG art. 163).

Dos implementaciones:
  - dhondt_exacto: aritmética entera, desempates según la ley. Para validar
    contra resultados reales.
  - dhondt_vectorizado: numpy, procesa miles de simulaciones a la vez.
    Para el Monte Carlo (los empates exactos son irrelevantes ahí).

Reglas aplicadas (art. 163.1 LOREG):
  a) Se excluyen las candidaturas con menos del 3% de los votos válidos
     de la circunscripción (votos válidos = votos a candidaturas + blanco).
  b) D'Hondt: se divide el voto de cada candidatura por 1, 2, ..., n
     y se asignan los n mayores cocientes.
  c) Empate de cocientes: el escaño va a la candidatura con más votos totales.
     Si también empatan en votos, la ley manda sorteo; aquí se lanza un aviso
     y se resuelve por orden alfabético para que sea reproducible.
"""
from __future__ import annotations

import warnings
from fractions import Fraction

import numpy as np

UMBRAL = 0.03


def dhondt_exacto(
    votos: dict[str, int],
    escanos: int,
    blancos: int = 0,
    umbral: float = UMBRAL,
) -> dict[str, int]:
    """Reparto exacto en una circunscripción. Devuelve {candidatura: escaños}."""
    validos = sum(votos.values()) + blancos
    minimo = Fraction(umbral).limit_denominator() * validos
    elegibles = {p: v for p, v in votos.items() if v > 0 and v >= minimo}

    resultado = {p: 0 for p in votos}
    if not elegibles or escanos <= 0:
        return resultado

    cocientes = [
        (Fraction(v, d), v, p)
        for p, v in elegibles.items()
        for d in range(1, escanos + 1)
    ]
    # Orden: cociente desc, votos totales desc (desempate legal), nombre asc.
    cocientes.sort(key=lambda t: (-t[0], -t[1], t[2]))

    corte = cocientes[escanos - 1]
    if escanos < len(cocientes):
        siguiente = cocientes[escanos]
        if siguiente[0] == corte[0] and siguiente[1] == corte[1] and siguiente[2] != corte[2]:
            warnings.warn(
                f"Empate total entre {corte[2]} y {siguiente[2]} por el último escaño: "
                "la ley prevé sorteo; resuelto por orden alfabético."
            )

    for _, _, p in cocientes[:escanos]:
        resultado[p] += 1
    return resultado


def dhondt_vectorizado(
    votos: np.ndarray,
    escanos: int,
    blancos: np.ndarray | float = 0.0,
    umbral: float = UMBRAL,
) -> np.ndarray:
    """
    Reparto D'Hondt para muchas simulaciones de una misma circunscripción.

    votos:   array (n_sim, n_partidos) con votos (o cuotas) de cada candidatura.
    blancos: array (n_sim,) o escalar, en la misma unidad que `votos`.
    Devuelve array de enteros (n_sim, n_partidos) con los escaños.
    """
    votos = np.atleast_2d(np.asarray(votos, dtype=float))
    n_sim, n_part = votos.shape
    validos = votos.sum(axis=1) + np.broadcast_to(blancos, (n_sim,))
    v = np.where(votos >= umbral * validos[:, None], votos, 0.0)

    if escanos <= 0:
        return np.zeros((n_sim, n_part), dtype=int)

    divisores = np.arange(1, escanos + 1, dtype=float)
    # cocientes: (n_sim, n_part * escanos)
    coc = (v[:, :, None] / divisores[None, None, :]).reshape(n_sim, -1)
    # índices de los `escanos` mayores cocientes en cada simulación
    top = np.argpartition(-coc, escanos - 1, axis=1)[:, :escanos]
    partido = top // escanos
    # cocientes nulos (partidos bajo umbral o sin votos) no reciben escaño
    validos_top = np.take_along_axis(coc, top, axis=1) > 0

    out = np.zeros((n_sim, n_part), dtype=int)
    filas = np.repeat(np.arange(n_sim), escanos)
    np.add.at(out, (filas[validos_top.ravel()], partido.ravel()[validos_top.ravel()]), 1)
    return out
