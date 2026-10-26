from datetime import date

import pandas as pd

from interfaz import calculo
from motor.pipeline import PART_BASE, Escenario
from motor.proyeccion import FECHA


def test_fechas_semanales_terminan_en_la_ultima_encuesta():
    f = calculo.fechas_semanales()
    assert f[-1] == FECHA and date.fromisoformat(f[0]) >= calculo.INICIO_EVOLUCION
    assert set(pd.to_datetime(f).to_series().diff().dropna().dt.days) == {7}


def test_con_participacion_base_el_reparto_no_cuenta():
    a = calculo.normalizar(Escenario(FECHA, "registradas", PART_BASE, "muy_asimetrico"))
    assert a.reparto == "historico"
    b = calculo.normalizar(Escenario(FECHA, "registradas", 0.70, "muy_asimetrico"))
    assert b.reparto == "muy_asimetrico"


def test_rejilla_sin_duplicados_e_incluye_el_escenario_por_defecto():
    r = calculo.rejilla()
    assert len(r) == len(set(r))
    assert Escenario(FECHA, "registradas", PART_BASE, "historico", calculo.N_SIM, calculo.SEMILLA) in r


def test_escenario_se_guarda_y_se_lee_de_disco(tmp_path, monkeypatch):
    monkeypatch.setattr(calculo, "CACHE", tmp_path)
    esc = Escenario(FECHA, "registradas", PART_BASE, "historico", n_sim=300, semilla=1)
    assert not calculo.en_disco(esc, "v1")
    a = calculo.escenario(esc, "v1")
    assert calculo.en_disco(esc, "v1")
    b = calculo.escenario(esc, "v1")
    assert a["sim"].equals(b["sim"]) and (a["sim"].sum(axis=1) == 350).all()
    (tmp_path / "v0").mkdir()
    calculo.limpiar_cache("v1")
    assert not (tmp_path / "v0").exists() and calculo.en_disco(esc, "v1")


def test_la_cache_no_depende_de_pyarrow():
    """La web publicada no instala pyarrow: los escenarios guardados no pueden llevar texto de pyarrow."""
    import pickle

    import pandas as pd

    import interfaz.calculo  # noqa: F401  (fija el formato del texto)
    assert b"pyarrow" not in pickle.dumps(pd.DataFrame({"a": ["x", "y"]}))
