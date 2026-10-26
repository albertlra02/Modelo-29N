import pytest

from datos.familias import CCAA
from motor.pipeline import Escenario, ejecutar


@pytest.fixture(scope="module")
def base():
    return ejecutar(Escenario(n_sim=400, semilla=7))


def test_escenario_base_reparte_350_y_probabilidades_validas(base):
    assert (base.sim.sum(axis=1) == 350).all()
    assert base.probs.between(0, 1).all()
    assert len(base.provincias) == 52


def test_candidaturas_registradas(base):
    s0 = base.central["s0"]
    assert "FRENTE_AMPLIO" in base.sim and "PODEMOS" in base.sim and "SUMAR" not in base.sim
    # Podemos no presenta lista propia en Cataluña (va con ERC), C. Valenciana ni Canarias (listas conjuntas)
    sin_podemos = CCAA["Cataluña"] + CCAA["C. Valenciana"] + CCAA["Canarias"]
    assert (s0.loc[sin_podemos, "PODEMOS"] == 0).all()
    assert (s0.drop(index=sin_podemos).PODEMOS > 0).all()
    assert "NC" not in s0                     # Nueva Canarias va en la lista conjunta canaria
    assert abs(s0.sum(axis=1) - 1).max() < 1e-9
    assert abs(base.nacional.sum() - 1) < 1e-9


def test_lista_unica_y_participacion(base):
    lu = ejecutar(Escenario(n_sim=400, semilla=7, candidaturas="lista_unica", participacion=0.72))
    assert "FRENTE_AMPLIO" in lu.sim and "PODEMOS" not in lu.sim and "SUMAR" not in lu.sim
    assert (lu.sim.sum(axis=1) == 350).all()
    # más participación con reparto histórico: la izquierda sube en voto central
    assert lu.nacional["PSOE"] > base.nacional["PSOE"]


def test_candidaturas_desconocidas():
    with pytest.raises(ValueError):
        ejecutar(Escenario(n_sim=10, candidaturas="separados"))


def test_senado(base):
    s = base.senado
    assert (s["sim"].sum(axis=1) == 208).all() and (s["sin_coalicion"].sum(axis=1) == 208).all()
    assert "PROGRESO" in s["sim"] and "PROGRESO" not in s["sin_coalicion"]
    assert len(s["circunscripciones"]) == 59
    assert s["probs"].between(0, 1).all()
    # la coalición no puede dejar a PSOE + Frente Amplio con menos senadores de los que tendrían por separado
    con = s["sim"][[x for x in ("PROGRESO", "PSOE", "FRENTE_AMPLIO") if x in s["sim"]]].sum(axis=1)
    sin = s["sin_coalicion"][[x for x in ("PSOE", "FRENTE_AMPLIO") if x in s["sin_coalicion"]]].sum(axis=1)
    assert con.mean() >= sin.mean()
