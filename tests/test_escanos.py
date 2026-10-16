import warnings

import numpy as np
import pytest

from motor.escanos import dhondt_exacto, dhondt_vectorizado


def test_ejemplo_clasico():
    # Ejemplo de libro: 7 escaños, A 100k, B 80k, C 30k, D 20k -> 3, 3, 1, 0
    r = dhondt_exacto({"A": 100_000, "B": 80_000, "C": 30_000, "D": 20_000}, 7)
    assert r == {"A": 3, "B": 3, "C": 1, "D": 0}


def test_umbral_3_por_ciento_incluye_blancos():
    # C tiene el 3,0% sin contar blancos pero <3% contando blancos -> excluido
    votos = {"A": 600, "B": 370, "C": 30}
    assert dhondt_exacto(votos, 100, blancos=0)["C"] > 0
    assert dhondt_exacto(votos, 100, blancos=20)["C"] == 0


def test_desempate_por_votos_totales():
    # A/2 = 50 y B/1 = 50 empatan por el último escaño: gana A (más votos)
    r = dhondt_exacto({"A": 100, "B": 50}, 2)
    assert r == {"A": 2, "B": 0}


def test_empate_total_avisa():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = dhondt_exacto({"A": 100, "B": 100}, 1)
    assert sum(r.values()) == 1
    assert any("sorteo" in str(x.message) for x in w)


def test_circunscripcion_uninominal():
    # Ceuta / Melilla: 1 escaño, gana el más votado
    assert dhondt_exacto({"A": 10, "B": 9, "C": 8}, 1) == {"A": 1, "B": 0, "C": 0}


@pytest.mark.parametrize("escanos", [1, 2, 3, 5, 8, 16, 38])
def test_vectorizado_coincide_con_exacto(escanos):
    rng = np.random.default_rng(escanos)
    n_sim, n_part = 500, 8
    votos = rng.integers(0, 200_000, size=(n_sim, n_part))
    blancos = rng.integers(0, 5_000, size=n_sim)
    vec = dhondt_vectorizado(votos, escanos, blancos)
    for i in range(n_sim):
        ex = dhondt_exacto({str(j): int(votos[i, j]) for j in range(n_part)}, escanos, int(blancos[i]))
        assert list(vec[i]) == [ex[str(j)] for j in range(n_part)]
    assert (vec.sum(axis=1) == escanos).all()
