"""Simulador "¿y si…?", noche electoral y actualizador de encuestas (sin red)."""
import numpy as np
import pandas as pd

from datos import escrutinio as E
from datos.cargar import cargar, escanos_2026
from motor import noche as N
from motor import simulador as M
from scripts import actualizar_encuestas as A
from web import datos as D


def _base():
    d = D.correr(D.Params().escenario())
    return d["s0"].astype(float), D.pesos_2023(), escanos_2026()


def test_simulador_cuadra_el_voto_pedido_y_reparte_350():
    s0, pesos, esc = _base()
    s, prov = M.simular(s0, pesos, esc, {"PP": 0.36, "VOX": 0.15})
    nac = M.nacional_de(s, pesos)
    assert abs(nac["PP"] - 0.36) < 1e-5 and abs(nac["VOX"] - 0.15) < 1e-5
    assert np.allclose(s.sum(axis=1), 1)
    assert prov.to_numpy().sum() == 350
    # un partido que no se presenta en una provincia sigue sin presentarse
    assert (s.loc[s0["ERC"] == 0, "ERC"] == 0).all()
    # sin tocar nada, la proyección no cambia
    s_igual, _ = M.simular(s0, pesos, esc, {})
    assert np.allclose(s_igual, s0)


def test_objetivos_reparte_lo_que_sobra_en_proporcion():
    nac = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    obj = M.objetivos(nac, {"A": 0.6})
    assert abs(obj["A"] - 0.6) < 1e-12 and abs(obj.sum() - 1) < 1e-12
    assert abs(obj["B"] / obj["C"] - 1.5) < 1e-12


def test_noche_mezcla_segun_lo_escrutado():
    s0, _, esc = _base()
    escr = E.simulacro(100.0)
    cuotas = E.cuotas(escr)
    # al 100 % escrutado (y con los escaños por provincia de 2023), la proyección es el recuento: los 350 de 2023
    _, proy = N.proyectar(s0, cuotas, escr.escrutado, cargar("2023-07").meta["diputados"])
    _, real = D.resultados_2023()
    for modelo, c23 in [("PP", "PP"), ("PSOE", "PSOE"), ("VOX", "VOX"), ("FRENTE_AMPLIO", "SUMAR"), ("BILDU", "EH BILDU")]:
        assert proy[modelo].sum() == real[c23].sum(), modelo
    # al 0 %, la predicción
    s, _ = N.proyectar(s0, cuotas, escr.escrutado * 0, esc)
    assert np.allclose(s, s0)


def test_escrutinio_lee_y_valida(tmp_path):
    ruta = tmp_path / "escrutinio.csv"
    assert E.leer(ruta) is None
    E.simulacro(30.0).to_csv(ruta)
    df = E.leer(ruta, provincias=list(escanos_2026().index))
    assert len(df) == 52 and df.escrutado.between(0, 100).all()
    pd.DataFrame({"provincia": ["Atlántida"], "escrutado": [10], "blancos": [1], "PP": [5]}).to_csv(ruta, index=False)
    try:
        E.leer(ruta, provincias=list(escanos_2026().index))
        raise AssertionError("debería rechazar una provincia desconocida")
    except ValueError:
        pass


def test_actualizador_lee_cabeceras_por_enlace_y_quita_escanos():
    html = ('<table class="wikitable"><tr><th>Polling firm/Commissioner</th><th>Fieldwork date</th>'
            '<th>Sample size</th><th>Turnout</th>'
            '<th><a href="https://en.wikipedia.org/wiki/People%27s_Party_(Spain)">x</a></th>'
            '<th><a href="/wiki/Broad_Front_(Spain)"><img alt="FA"></a></th><th>Lead</th></tr></table>')
    assert A.partidos_de_cabecera(html) == ["PP", "FA"]
    tsv = "year\ta\tb\tc\td\tPP\tFA\n2026\tX\t1 Oct\t1,000\t?\t31.4 133\t? 8"
    assert A.solo_porcentajes(tsv).splitlines()[1].split("\t")[5:] == ["31.4", "?"]
    try:
        A.partidos_de_cabecera(html.replace("Broad_Front_(Spain)", "Partido_Nuevo"))
        raise AssertionError("debería pararse ante una columna desconocida")
    except SystemExit as e:
        assert "Partido_Nuevo" in str(e)


def test_parsear_suma_fa_y_fv_como_sumar():
    from datos.encuestas.parsear import _filas
    cab = ["Polling firm/Commissioner", "Fieldwork date", "Sample size", "Turnout", "PP", "FA", "FV"]
    fila = _filas("", "2026", "España", cab, ["2026\tX/Y\t15–17 Oct\t1,000\t?\t31.8\t5.0\t1.3"], anio_col=True)[0]
    assert fila["SUMAR"] == 6.3 and fila["PP"] == 31.8


def test_pesos_2023_son_los_validos():
    assert D.pesos_2023().equals(cargar("2023-07").validos)
