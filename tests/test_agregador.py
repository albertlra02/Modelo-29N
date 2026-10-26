import numpy as np
import pandas as pd

from motor.agregador import agregar


def _sinteticas(seed=0):
    """Tres casas con sesgos conocidos (+2, 0, -2) midiendo un 30 % que sube a 32 %."""
    rng = np.random.default_rng(seed)
    filas = []
    for dia in range(0, 120, 2):
        verdad = 30 + 2 * dia / 120
        for casa, sesgo in [("A", 2.0), ("B", 0.0), ("C", -2.0)]:
            t = pd.Timestamp("2026-01-01") + pd.Timedelta(days=dia)
            filas.append({"casa": casa, "t": t, "n_ef": 1500, "X": verdad + sesgo + rng.normal(0, 0.8)})
    return pd.DataFrame(filas)


def test_recupera_efectos_de_casa_y_nivel():
    e = _sinteticas()
    r = agregar(e, "X", "2026-04-30")
    efectos = r.casas.set_index("casa").efecto
    assert abs(efectos["A"] - 2) < 0.4 and abs(efectos["B"]) < 0.4 and abs(efectos["C"] + 2) < 0.4
    m, _ = r.final
    assert abs(m - 32) < 0.6


def test_sigue_la_tendencia():
    e = _sinteticas(1)
    serie = agregar(e, "X", "2026-04-30").serie.set_index("fecha").media
    assert serie.iloc[-1] - serie.iloc[10] > 1.0
