import numpy as np
import pandas as pd

from datos.familias import CCAA
from motor import senado
from validacion.validar_senado import reparto_2023


def test_circunscripciones_y_pacto():
    c = senado.circunscripciones()
    assert len(c) == 59 and c.escanos.sum() == 208
    assert c.isla.sum() == 10
    assert set(c.loc[~c.pacto].provincia) == set(CCAA["Cataluña"] + CCAA["Canarias"])
    assert c.at["La Gomera", "pacto"] and not c.at["Tenerife", "pacto"]
    # 46 provincias con coalición, más La Gomera
    assert c[c.pacto & ~c.isla].provincia.nunique() + 1 == 46     # + Baleares, que va por islas
    assert c.loc[c.pacto, "escanos"].sum() == 43 * 4 + 5 + 2 * 2 + 1


def test_voto_limitado():
    v = np.array([[0.40, 0.35, 0.10, 0.0], [0.30, 0.45, 0.20, 0.05]])
    assert senado.repartir(v, 4).tolist() == [[3, 1, 0, 0], [1, 3, 0, 0]]
    assert senado.repartir(v, 3).tolist() == [[2, 1, 0, 0], [1, 2, 0, 0]]
    assert senado.repartir(v, 2).tolist() == [[2, 0, 0, 0], [0, 2, 0, 0]]
    assert senado.repartir(v, 1).tolist() == [[1, 0, 0, 0], [0, 1, 0, 0]]


def test_dos_mas_dos_solo_con_margen_estrecho():
    v = np.array([[0.400, 0.396, 0.1], [0.40, 0.36, 0.1]])
    e = senado.repartir(v, 4, umbral=np.array([0.02, 0.02]))
    assert e.tolist() == [[2, 2, 0], [3, 1, 0]]
    assert senado.repartir(v[:, :2], 3, umbral=np.array([0.02, 0.02])).tolist() == [[2, 1], [2, 1]]


def test_coalicion_suma_psoe_y_frente_amplio():
    partidos = ["PP", "PSOE", "FRENTE_AMPLIO", "PODEMOS", "OTROS", "BLANCO"]
    provs = list(senado.circunscripciones().provincia.unique())
    S = np.tile(np.array([0.36, 0.30, 0.10, 0.04, 0.19, 0.01]), (1, len(provs), 1))
    ajena = pd.Series(0.0, index=provs)
    V, L = senado.voto_senado(S, provs, partidos, ajena, coalicion=True)
    il = {p: i for i, p in enumerate(L)}
    madrid = list(senado.circunscripciones().index).index("Madrid")
    barcelona = list(senado.circunscripciones().index).index("Barcelona")
    assert V[0, madrid, il["PROGRESO"]] > V[0, madrid, il["PP"]] and V[0, madrid, il["PSOE"]] == 0
    assert V[0, barcelona, il["PROGRESO"]] == 0 and V[0, barcelona, il["PSOE"]] > 0


def test_valida_contra_2023():
    prev, real = reparto_2023()
    assert int(prev.to_numpy().sum()) == 208 and int(real.to_numpy().sum()) == 208
    assert int((prev - real).abs().to_numpy().sum() // 2) <= 9


def test_designados_actuales():
    d = senado.designados()
    assert len(d) == 58
    n = senado.designados_por_lista()
    assert (n["PP"], n["PSOE"], n["VOX"], n["JUNTS"], n["FRENTE_AMPLIO"]) == (23, 19, 5, 3, 2)
    sim = pd.DataFrame({"PP": [100, 110], "PSOE": [80, 70]})
    pl = senado.pleno(sim)
    assert (pl.sum(axis=1) == sim.sum(axis=1) + 58).all() and pl.at[0, "PP"] == 123


def test_retirada_de_vox():
    circ = senado.circunscripciones()
    provincias = set(circ.provincia)
    assert senado.retirada_vox(None) == frozenset()
    for grupo in (senado.PACTO_VOX_FUERA, senado.PACTO_PP_FUERA, senado.PACTO_VOX_UNO):
        assert set(grupo) <= provincias
    assert len(senado.retirada_vox("pacto")) == 6 and len(senado.PACTO_VOX_UNO) == 14
    assert senado.retirada_vox("amplia") == provincias - set(senado.VOX_CON_LISTA)
    # donde Vox no va, su voto desaparece y el PP recibe TRASVASE_VOX de él
    partidos = ["PP", "PSOE", "VOX"]
    provs = sorted(provincias)
    S = np.tile([0.4, 0.35, 0.25], (1, len(provs), 1))
    base, L = senado.voto_senado(S, provs, partidos, pd.Series(dtype=float), coalicion=False)
    sin, _ = senado.voto_senado(S, provs, partidos, pd.Series(dtype=float), coalicion=False,
                                sin_vox=frozenset(["Sevilla"]))
    c = list(circ.index).index("Sevilla")
    assert sin[0, c, L.index("VOX")] == 0
    assert np.isclose(sin[0, c, L.index("PP")], base[0, c, L.index("PP")] + senado.TRASVASE_VOX * 0.25)
    m = list(circ.index).index("Murcia")
    assert np.allclose(sin[0, m], base[0, m])


def test_vox_en_la_lista_del_pp_y_provincias_seguras():
    circ = senado.circunscripciones()
    provs = sorted(set(circ.provincia))
    partidos = ["PP", "PSOE", "VOX"]
    # PP muy por delante: gana 3 + 1 en todas las provincias de 4 senadores
    S = np.tile([0.50, 0.30, 0.20], (2, len(provs), 1))
    sin = frozenset(["Sevilla", "Cádiz"])
    base, por_circ = senado.simular(S, provs, partidos, pd.Series(dtype=float), coalicion=False)
    sim, por_circ_h = senado.simular(S, provs, partidos, pd.Series(dtype=float), coalicion=False,
                                     sin_vox=sin, vox_en_pp=frozenset(["Sevilla"]))
    assert list(por_circ_h["Sevilla"].loc[0, ["PP", "VOX"]]) == [2, 1]     # uno de los 3 del PP es de Vox
    assert list(por_circ_h["Cádiz"].loc[0, ["PP", "VOX"]]) == [3, 0]
    assert sim.sum(axis=1).eq(senado.TOTAL).all()
    # con el PP primero en todas partes, todas las provincias son seguras y la retirada amplia no toca ninguna
    seguras = senado.pp_seguro(por_circ)
    assert "Sevilla" in seguras
    assert senado.retirada_vox("amplia", seguras) <= frozenset(provs) - seguras
    # el independiente de Vox va en la lista del PP en todas las provincias de 4 senadores donde Vox no va
    s0 = pd.DataFrame({"PP": [0.40, 0.40], "VOX": [0.25, 0.15]}, index=["Sevilla", "Cádiz"])
    assert senado.nombres_vox(s0, sin) == sin
    assert senado.nombres_vox(s0, frozenset(["Sevilla", "Mallorca"])) == frozenset(["Sevilla"])


def test_reparto_nombre_a_nombre_coincide_con_repartir():
    """Con listas de tres nombres y el tercero con la caída habitual, elegir nombre a nombre da lo mismo que
    repartir() lista a lista."""
    rng = np.random.default_rng(1)
    votos = rng.dirichlet([5, 4, 1, 1], size=500)
    u = rng.choice(senado.umbrales_empate(), size=500)
    a = senado.repartir(votos, 4, u)
    b = senado.elegir(senado._resto(votos, ["A", "B", "C", "D"], u, ()), 4, 4)
    assert (a == b).all()


def test_acuerdo_pp_vox():
    circ = senado.circunscripciones()
    provs = sorted(set(circ.provincia))
    partidos = ["PP", "PSOE", "VOX"]
    vacia = pd.Series(dtype=float)
    # donde el PP no va, Vox recibe TRASVASE_PP de su voto
    S = np.tile([0.30, 0.45, 0.25], (1, len(provs), 1))
    base, L = senado.voto_senado(S, provs, partidos, vacia, coalicion=False)
    fuera, _ = senado.voto_senado(S, provs, partidos, vacia, coalicion=False, pp_fuera=frozenset(["Girona"]))
    g = list(circ.index).index("Girona")
    assert fuera[0, g, L.index("PP")] == 0
    assert np.isclose(fuera[0, g, L.index("VOX")], 0.25 + senado.TRASVASE_PP * 0.30)
    # Vox con un solo nombre: sus votantes suben a los dos primeros del PP, pero el tercero sólo tiene voto del
    # PP y se cuela el segundo del PSOE: de 1 + 3 a 2 + 2
    S = np.tile([0.36, 0.40, 0.18], (1, len(provs), 1))
    sep, pc_sep = senado.simular(S, provs, partidos, vacia, coalicion=False)
    uno, pc_uno = senado.simular(S, provs, partidos, vacia, coalicion=False, vox_uno=frozenset(["Sevilla"]))
    assert list(pc_sep["Sevilla"].loc[0, ["PP", "PSOE", "VOX"]]) == [1, 3, 0]
    assert list(pc_uno["Sevilla"].loc[0, ["PP", "PSOE", "VOX"]]) == [2, 2, 0]
    assert uno.sum(axis=1).eq(senado.TOTAL).all()
    # la hipótesis del pacto lleva las cuatro piezas
    s0 = pd.DataFrame({"PP": [0.4] * len(provs), "VOX": [0.1] * len(provs)}, index=provs)
    kw = senado.hipotesis_vox("pacto", s0)
    assert kw["vox_en_pp"] == frozenset(["Cádiz", "València/Valencia", "Castelló/Castellón"])
    assert kw["pp_fuera"] == frozenset(senado.PACTO_PP_FUERA) and len(kw["vox_uno"]) == 14
