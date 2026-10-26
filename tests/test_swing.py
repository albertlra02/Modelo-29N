import numpy as np
import pandas as pd
import pytest

from motor.swing import METODOS, proyectar


def _caso():
    prov = ["a", "b", "c", "d"]
    base = pd.DataFrame(
        {"X": [0.40, 0.30, 0.20, 0.10], "Y": [0.30, 0.30, 0.0, 0.0],  # Y regional
         "OTROS": [0.28, 0.38, 0.78, 0.88], "BLANCO": [0.02, 0.02, 0.02, 0.02]},
        index=prov,
    )
    pesos = pd.Series([100.0, 200.0, 300.0, 400.0], index=prov)
    region = pd.Series("R", index=prov)
    obj = pd.DataFrame({"X": [0.25], "Y": [0.10], "OTROS": [0.63], "BLANCO": [0.02]}, index=["R"])
    return base, pesos, region, obj


@pytest.mark.parametrize("metodo", METODOS)
def test_cuadra_con_el_objetivo_regional(metodo):
    base, pesos, region, obj = _caso()
    p = proyectar(base, pesos, obj, region, metodo)
    agg = p.mul(pesos, axis=0).sum() / pesos.sum()
    assert np.allclose(agg[obj.columns], obj.iloc[0], atol=1e-3)
    assert np.allclose(p.sum(axis=1), 1.0)


@pytest.mark.parametrize("metodo", METODOS)
def test_respeta_ausencias(metodo):
    # Y no se presenta en c y d: debe seguir a 0 ahí aunque su objetivo suba
    base, pesos, region, obj = _caso()
    p = proyectar(base, pesos, obj, region, metodo)
    assert (p.loc[["c", "d"], "Y"] == 0).all()


def test_siembra_presencias_nuevas():
    base, pesos, region, obj = _caso()
    pres = base > 0
    pres.loc["c", "Y"] = True
    p = proyectar(base, pesos, obj, region, "proporcional", presencia=pres)
    assert p.at["c", "Y"] > 0
