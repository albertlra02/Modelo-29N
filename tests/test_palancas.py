from dataclasses import replace

import numpy as np
import pytest

from datos.familias import CCAA
from motor.palancas import Palancas, aplicar
from motor.pipeline import Escenario, ejecutar, piezas_centrales, registradas
from web import datos as D


@pytest.fixture(scope="module")
def c():
    return registradas(piezas_centrales("2026-10-12", 0.65, "historico"))


def test_sin_palancas_no_cambia_nada(c):
    assert aplicar(c, Palancas()) is c
    assert not Palancas(mov_ambito="Cataluña", util_sin_escano=False).activas


def test_movilizacion_solo_en_su_ambito(c):
    m = aplicar(c, Palancas(mov_nac=-20, mov_ambito="Cataluña"))
    cat, resto = CCAA["Cataluña"], [p for p in c["s0"].index if p not in CCAA["Cataluña"]]
    assert (m["s0"].loc[cat, "ERC"] < c["s0"].loc[cat, "ERC"]).all()
    assert np.allclose(m["s0"].loc[resto], c["s0"].loc[resto])
    assert np.allclose(m["s0"].sum(axis=1), 1)
    assert m["nacional"]["ERC"] < c["nacional"]["ERC"] and abs(m["nacional"].sum() - 1) < 1e-9


def test_voto_util_conserva_votos_y_respeta_donde(c):
    m = aplicar(c, Palancas(util_vox_pp=20))
    donde = m["palancas_donde"]["vox_pp"]
    assert 0 < len(donde) < 52
    otras = [p for p in c["s0"].index if p not in donde]
    assert np.allclose(m["s0"].loc[otras], c["s0"].loc[otras])
    p = donde[0]
    assert np.isclose(m["s0"].at[p, "VOX"], 0.8 * c["s0"].at[p, "VOX"])
    assert np.isclose(m["s0"].at[p, "PP"] + m["s0"].at[p, "VOX"], c["s0"].at[p, "PP"] + c["s0"].at[p, "VOX"])
    todas = aplicar(c, Palancas(util_vox_pp=20, util_sin_escano=False))
    assert len(todas["palancas_donde"]["vox_pp"]) == 52


def test_palancas_mueven_la_simulacion():
    base = Escenario(n_sim=300, semilla=3)
    r0 = ejecutar(base)
    r1 = ejecutar(replace(base, palancas=Palancas(mov_izda=15)))
    assert r1.sim.PSOE.mean() > r0.sim.PSOE.mean() and r1.sim.PP.mean() < r0.sim.PP.mean()
    assert (r1.sim.sum(axis=1) == 350).all() and (r1.senado["sim"].sum(axis=1) == 208).all()


def test_palancas_en_la_url():
    p = D.Params.de_query({"mov_izda": "8", "ambito": "Cataluña", "util_vox_pp": "90", "util_donde": "todas"})
    assert (p.mov_izda, p.mov_ambito, p.util_vox_pp, p.util_donde) == (8, "Cataluña", D.LIMITE_UTIL, "todas")
    pal = p.escenario().palancas
    assert pal.activas and not pal.util_sin_escano and pal.mov_ambito == "Cataluña"
    assert "mov_izda=8" in p.query() and "util_donde=todas" in p.query()
    # sin palancas, el ámbito y el «dónde» no cuentan: el escenario por defecto sigue siendo el mismo
    assert D.Params.de_query({"ambito": "Cataluña", "util_donde": "todas"}) == D.Params()
