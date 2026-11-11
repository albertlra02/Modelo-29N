import pandas as pd

from datos.cargar import escanos_2026
from interfaz import graficos as G


def test_mapa_cubre_las_52_circunscripciones():
    ids = {f["id"] for f in G.geo_provincias()["features"]}
    assert ids == set(escanos_2026().index)


def test_mapas_se_construyen_con_todas_las_provincias():
    provs = list(escanos_2026().index)
    hover = pd.Series(provs, index=provs)
    ganador = pd.Series(["PP"] * 50 + ["PSOE"] * 2, index=provs)
    fig = G.mapa_ganador(ganador, hover)
    assert sum(len(t.locations) for t in fig.data if t.type == "choropleth") == 52
    fig = G.mapa_valor(pd.Series(range(52), index=provs, dtype=float), hover, "PP", "Voto")
    assert fig.data[0].zmax >= 51
