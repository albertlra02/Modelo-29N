"""
Senado: los 208 senadores de elección directa (LOREG arts. 161, 165 y 166).

Circunscripciones: cada provincia elige 4; Mallorca, Gran Canaria y Tenerife, 3; Menorca,
Eivissa-Formentera, Lanzarote, Fuerteventura, La Palma, La Gomera y El Hierro, 1; Ceuta y
Melilla, 2. Voto limitado: cada elector marca como mucho 3 nombres en las provincias, 2 en las
islas de 3 senadores y en Ceuta y Melilla, y 1 en las islas de un senador.

Supuestos del modelo (validados contra 2023 con validacion/validar_senado.py):
  - Voto de partido: cada lista saca en el Senado el voto que su partido saca en el Congreso en la
    misma circunscripción. Con voto limitado eso da el reparto clásico: 3 + 1 en las provincias,
    2 + 1 en las islas grandes, 2 + 0 en Ceuta y Melilla.
  - Salvo cuando las dos primeras listas de una provincia quedan muy cerca: el tercer candidato de
    la ganadora saca algo menos que el primero (hay quien no marca los tres nombres) y el segundo de
    la otra puede superarlo, y el reparto queda 2 + 2. En cada simulación y provincia se sortea esa
    caída de entre las 47 provincias de 2023 (pasó en Badajoz, Cáceres, Huelva y Valencia, con
    márgenes del 1 al 2 %; con márgenes del 3,5 % o más, nunca).
  - Islas: el voto provincial simulado se reparte entre islas con el patrón del Congreso de 2023
    (cociente entre la cuota de cada partido en la isla y en el conjunto de la provincia).
  - Listas insulares que no van al Congreso (ASG en La Gomera, AHI en El Hierro): se fijan en su
    cuota del Senado de 2023 y el resto de listas se escala para dejarles hueco.
  - Coalición "Senado de Progreso" (PSOE + Frente Amplio: IU, Sumar, Más Madrid, Compromís, CHA,
    Batzarre y Més; acuerdo del 17/10/2026): suma íntegra de sus votos en todas las provincias salvo
    Cataluña y Canarias, más La Gomera. Podemos no está en el pacto: donde comparte lista con el
    Frente Amplio en el Congreso (C. Valenciana y Canarias) su parte va al Senado por su cuenta.
  - Acuerdo PP-Vox para el Senado (26/10/2026, comunicado de Vox recogido por Moncloa.com, Demócrata y
    Vozpópuli; no es una coalición: cada partido mantiene su papeleta). Tres piezas:
      * Vox no presenta lista en PACTO_VOX_FUERA (6 provincias). El TRASVASE_VOX de su voto va a la lista del
        PP y el resto se pierde (blanco, abstención o sin marcar). En las de 4 senadores, uno de los tres
        nombres del PP es un independiente propuesto por Vox: si la lista gana sus 3 escaños, uno es suyo.
      * El PP no presenta lista en PACTO_PP_FUERA (Gipuzkoa, Girona, Tarragona): el TRASVASE_PP de su voto va
        a Vox.
      * Vox presenta un solo candidato en PACTO_VOX_UNO (14 provincias) y pide a sus votantes marcar a ese
        candidato y a dos del PP. Ahí el reparto se hace candidato a candidato (repartir_candidatos): cada
        nombre del PP suma CUMPLE_VOX_UNO x 2/3 del voto de Vox (dos marcas de tres nombres, repartidas), y
        se eligen los cuatro nombres más votados de todas las listas.
    TRASVASE_VOX (80 %), TRASVASE_PP (60 %) y CUMPLE_VOX_UNO (80 %) son supuestos sin calibrar: no hay
    precedente de un acuerdo así. Lo más parecido medido en España es Unidos Podemos en 2016, que conservó el
    83 % de los votos que Podemos e IU habían sacado por separado.
  - Hipótesis "amplia" (contrafactual): Vox no se presenta en ninguna provincia salvo Murcia, Almería y Ceuta y
    las provincias donde el PP queda primero de todos modos (en al menos P_PP_SEGURO de las simulaciones con
    Vox presente). Donde Vox tiene al menos CUOTA_NOMBRE_VOX del voto de PP + Vox, uno de los tres nombres de
    la lista del PP es suyo.

Senadores designados por los parlamentos autonómicos (58): no dependen del 29-N sino de cada parlamento
autonómico, así que se suman fijos tal como están hoy (datos/senado_designados.csv, transcrito de la web
del Senado el 17/10/2026, grupo parlamentario -> partido). El pleno tiene 208 + 58 = 266; mayoría, 134.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from datos.familias import CCAA

RAIZ = Path(__file__).resolve().parent.parent
RUTA_SENADO = RAIZ / "datos" / "raw" / "senado_2023-07.csv"
RUTA_ISLAS = RAIZ / "datos" / "raw" / "congreso_2023-07_islas.csv"
RUTA_DESIGNADOS = RAIZ / "datos" / "senado_designados.csv"

TOTAL = 208
# Partido de cada designado -> lista del modelo (Compromís y Más Madrid están en el Frente Amplio)
LISTA_DESIGNADO = {"PP": "PP", "PSOE": "PSOE", "Vox": "VOX", "Junts": "JUNTS", "ERC": "ERC", "BNG": "BNG",
                   "PNV": "PNV", "EH Bildu": "BILDU", "Coalición Canaria": "CC", "Compromís": "FRENTE_AMPLIO",
                   "Más Madrid": "FRENTE_AMPLIO", "Geroa Bai": "GBAI"}
VOTOS_ELECTOR = {4: 3, 3: 2, 2: 2, 1: 1}         # escaños de la circunscripción -> nombres por elector
PROGRESO = "PROGRESO"
NO_LISTAS = ("OTROS", "BLANCO")
# Provincias fuera del pacto (y la isla que sí entra aunque su provincia no)
SIN_PACTO = CCAA["Cataluña"] + CCAA["Canarias"]
ISLAS_CON_PACTO = ("La Gomera",)
# Listas insulares sin candidatura al Congreso: clave del modelo -> siglas en el Senado de 2023
LOCALES_ISLA = {"La Gomera": ("ASG", "ASG"), "El Hierro": ("AHI", "A.H.I.")}
# Columna del Congreso 2023 con la que se mide el patrón insular de cada partido del modelo
PATRON_2023 = {"PP": "PP", "PSOE": "PSOE", "VOX": "VOX", "SUMAR": "SUMAR", "PODEMOS": "SUMAR",
               "FRENTE_AMPLIO": "SUMAR", "CC": "CC", "NC": "NC"}
COCIENTE_MIN, COCIENTE_MAX = 0.25, 4.0
# Acuerdo PP-Vox del 26/10/2026 (ver cabecera)
PACTO_VOX_FUERA = ("Las Palmas", "Santa Cruz de Tenerife", "Cádiz", "València/Valencia", "Castelló/Castellón",
                   "Illes Balears")
PACTO_PP_FUERA = ("Gipuzkoa", "Girona", "Tarragona")
PACTO_VOX_UNO = ("Sevilla", "Huelva", "Asturias", "Badajoz", "Araba/Álava", "Navarra", "Cáceres", "Huesca",
                 "Zaragoza", "Alacant/Alicante", "Granada", "Cuenca", "Pontevedra", "Jaén")
# Hipótesis "amplia": provincias donde Vox mantendría lista de todos modos
VOX_CON_LISTA = ("Murcia", "Almería", "Ceuta")
HIPOTESIS_VOX = ("pacto", "amplia")
TRASVASE_VOX = 0.8          # parte del voto de Vox que va a la lista del PP donde Vox no se presenta
TRASVASE_PP = 0.6           # parte del voto del PP que va a Vox donde el PP no se presenta
CUMPLE_VOX_UNO = 0.8        # votantes de Vox que marcan dos nombres del PP donde Vox lleva un solo candidato
P_PP_SEGURO = 0.95          # con esta probabilidad de quedar primero, el PP no necesita la retirada de Vox
CUOTA_NOMBRE_VOX = 1 / 3    # voto de Vox / (PP + Vox) a partir del cual uno de los 3 nombres del PP es de Vox


def retirada_vox(hipotesis: str | None, seguras: frozenset[str] = frozenset()) -> frozenset[str]:
    """Provincias sin lista de Vox al Senado en cada hipótesis (None: se presenta en todas).
    `seguras`: provincias donde el PP queda primero de todos modos (ver pp_seguro); en la amplia, Vox va."""
    if hipotesis is None:
        return frozenset()
    if hipotesis == "pacto":
        return frozenset(PACTO_VOX_FUERA)
    if hipotesis == "amplia":
        return frozenset(circunscripciones().provincia) - set(VOX_CON_LISTA) - seguras
    raise ValueError(f"hipótesis de Vox desconocida: {hipotesis!r} (válidas: {HIPOTESIS_VOX})")


def pp_seguro(por_circ: dict[str, pd.DataFrame]) -> frozenset[str]:
    """Provincias donde la lista del PP saca más senadores que cualquier otra, en todas sus
    circunscripciones, en al menos P_PP_SEGURO de las simulaciones."""
    circ = circunscripciones()
    out = set()
    for prov, cs in circ.groupby("provincia").groups.items():
        primero = None
        for c in cs:
            df = por_circ[c]
            if "PP" not in df:
                primero = None
                break
            p = df["PP"].to_numpy() > df.drop(columns="PP").max(axis=1).to_numpy()
            primero = p if primero is None else primero & p
        if primero is not None and primero.mean() >= P_PP_SEGURO:
            out.add(prov)
    return frozenset(out)


def hipotesis_vox(hipotesis: str, s0: pd.DataFrame, seguras: frozenset[str] = frozenset()) -> dict:
    """Argumentos de simular() para cada hipótesis: sin_vox, vox_en_pp, pp_fuera y vox_uno."""
    sv = retirada_vox(hipotesis, seguras)
    if hipotesis == "pacto":
        cuatro = set(circunscripciones().query("escanos == 4").index)
        return {"sin_vox": sv, "vox_en_pp": frozenset(p for p in sv if p in cuatro),
                "pp_fuera": frozenset(PACTO_PP_FUERA), "vox_uno": frozenset(PACTO_VOX_UNO)}
    return {"sin_vox": sv, "vox_en_pp": nombres_vox(s0, sv), "pp_fuera": frozenset(), "vox_uno": frozenset()}


def nombres_vox(s0: pd.DataFrame, sin_vox: frozenset[str]) -> frozenset[str]:
    """Provincias sin lista de Vox donde uno de los nombres de la lista del PP es de Vox (sólo las de 4
    senadores: en las islas cada lista lleva 1 o 2 nombres)."""
    cuota = s0["VOX"] / (s0["PP"] + s0["VOX"])
    cuatro = set(circunscripciones().query("escanos == 4").index)
    return frozenset(p for p in sin_vox if p in cuatro and cuota.get(p, 0) >= CUOTA_NOMBRE_VOX)


@lru_cache(maxsize=1)
def senado_2023() -> pd.DataFrame:
    """Listas del Senado de 2023 por circunscripción (datos/oficiales.py)."""
    return pd.read_csv(RUTA_SENADO, dtype={"circ": str})


@lru_cache(maxsize=1)
def designados() -> pd.DataFrame:
    """Los senadores de designación autonómica, con su lista en el modelo (columna `lista`)."""
    d = pd.read_csv(RUTA_DESIGNADOS)
    d["lista"] = d.partido.map(LISTA_DESIGNADO)
    assert d.lista.notna().all(), d[d.lista.isna()]
    return d


def designados_por_lista() -> pd.Series:
    return designados().lista.value_counts()


def pleno(sim: pd.DataFrame) -> pd.DataFrame:
    """Senado completo en cada simulación: electos simulados + designados fijos."""
    d = designados_por_lista()
    cols = list(dict.fromkeys(list(sim.columns) + list(d.index)))
    return sim.reindex(columns=cols, fill_value=0).add(d.reindex(cols, fill_value=0), axis=1).astype(sim.dtypes.iloc[0])


@lru_cache(maxsize=1)
def circunscripciones() -> pd.DataFrame:
    """Índice: nombre de la circunscripción (la provincia del modelo, o la isla). Columnas: provincia,
    escanos, isla (bool), pacto (bool: hay lista del Senado de Progreso)."""
    s = senado_2023().drop_duplicates("circ")
    isla = s.circ.str[2] != "9"
    nombre = np.where(isla, s.circunscripcion, s.provincia)
    c = pd.DataFrame({"provincia": s.provincia.to_numpy(), "escanos": s.escanos.to_numpy(), "isla": isla.to_numpy()},
                     index=pd.Index(nombre, name="circunscripcion"))
    c["pacto"] = ~c.provincia.isin(SIN_PACTO) | c.index.isin(ISLAS_CON_PACTO)
    assert c.escanos.sum() == TOTAL, c.escanos.sum()
    return c


@lru_cache(maxsize=1)
def cocientes_islas() -> pd.DataFrame:
    """isla x columna del Congreso 2023: cuota en la isla / cuota en el conjunto de islas de su provincia."""
    v = pd.read_csv(RUTA_ISLAS, index_col="isla")
    prov = v.pop("provincia")
    cuota_isla = v.div(v.sum(axis=1), axis=0)
    tot = v.groupby(prov).sum()
    cuota_prov = tot.div(tot.sum(axis=1), axis=0).reindex(prov.to_numpy())
    cuota_prov.index = v.index
    q = (cuota_isla / cuota_prov).where(cuota_prov > 0)
    return q.clip(COCIENTE_MIN, COCIENTE_MAX).fillna(1.0)


@lru_cache(maxsize=1)
def cuotas_locales() -> dict[str, float]:
    """Cuota del Senado 2023 de cada lista insular (voto de su mejor candidato / suma de listas)."""
    s = senado_2023()
    out = {}
    for isla, (_, siglas) in LOCALES_ISLA.items():
        d = s[s.circunscripcion == isla]
        out[isla] = float(d.loc[d.siglas == siglas, "votos"].sum() / d.votos.sum())
    return out


@lru_cache(maxsize=1)
def umbrales_empate() -> np.ndarray:
    """Margen relativo entre las dos primeras listas por debajo del cual una provincia de 4 senadores
    queda 2 + 2, medido en cada provincia de 2023: 1 - (3.º de la primera / su 1.º) / (2.º de la
    segunda / su 1.º). Media 0,7 %; negativo cuando la segunda pierde más votos entre candidatos."""
    s = senado_2023()
    s = s[(s.escanos == 4)].sort_values(["circ", "votos"], ascending=[True, False])
    u = []
    for _, g in s.groupby("circ"):
        a, b = g.iloc[0], g.iloc[1]
        u.append(1 - (a.votos_3 / a.votos) / (b.votos_2 / b.votos))
    return np.array(u)


def repartir(votos: np.ndarray, escanos: int, umbral: np.ndarray | None = None) -> np.ndarray:
    """Voto limitado con voto de partido. votos: (n, listas). Devuelve enteros (n, listas).

    Cada lista presenta tantos candidatos como nombres puede marcar el elector: la más votada se
    lleva esos escaños, la siguiente los que queden, etc. Con `umbral` (n,), en las circunscripciones
    de 4 senadores el reparto pasa a 2 + 2 cuando la segunda lista queda a menos de ese margen
    relativo de la primera (ver umbrales_empate).
    """
    votos = np.atleast_2d(np.asarray(votos, dtype=float))
    k = VOTOS_ELECTOR[escanos]
    n, L = votos.shape
    orden = np.argsort(-votos, axis=1, kind="stable")
    por_puesto = np.zeros(L, dtype=int)
    quedan = escanos
    for j in range(L):
        por_puesto[j] = min(k, quedan)
        quedan -= por_puesto[j]
    out = np.zeros((n, L), dtype=int)
    np.put_along_axis(out, orden, np.broadcast_to(por_puesto, (n, L)), axis=1)
    if umbral is not None and escanos == 4 and L > 1:
        filas = np.arange(n)
        v1, v2 = votos[filas, orden[:, 0]], votos[filas, orden[:, 1]]
        dos = (v2 > 0) & (v1 - v2 < umbral * v1)
        out[filas[dos], orden[dos, 0]] = 2
        out[filas[dos], orden[dos, 1]] = 2
    return np.where(votos > 0, out, 0)


def repartir_candidatos(votos: np.ndarray, nombres: np.ndarray, escanos: int,
                        umbral: np.ndarray | None = None) -> np.ndarray:
    """Voto limitado candidato a candidato. votos: (n, listas), lo que saca cada nombre de la lista;
    nombres: (listas,), candidatos de cada lista. Salen los `escanos` nombres más votados.

    Con `umbral` (n,), el tercer nombre de cada lista saca votos x (1 - umbral), como en repartir(): con dos
    listas de 3 nombres da exactamente el mismo 3 + 1 o 2 + 2."""
    votos = np.atleast_2d(np.asarray(votos, dtype=float))
    n, L = votos.shape
    u = np.zeros(n) if umbral is None else np.asarray(umbral, dtype=float)
    cols, lista = [], []
    for j in range(L):
        for k in range(int(nombres[j])):
            cols.append(votos[:, j] * (1 - u) if k == 2 else votos[:, j])
            lista.append(j)
    cand = np.stack(cols, axis=1)
    elegidos = np.asarray(lista)[np.argsort(-cand, axis=1, kind="stable")[:, :escanos]]
    out = np.stack([(elegidos == j).sum(axis=1) for j in range(L)], axis=1)
    return np.where(votos > 0, out, 0)


def listas(partidos: list[str]) -> list[str]:
    """Listas posibles al Senado: las del Congreso, la coalición y las insulares."""
    return [p for p in partidos if p not in NO_LISTAS] + [PROGRESO] + [k for k, _ in LOCALES_ISLA.values()]


def voto_senado(S: np.ndarray, provincias: list[str], partidos: list[str], ajena: pd.Series,
                coalicion: bool = True, sin_vox: frozenset[str] = frozenset(),
                pp_fuera: frozenset[str] = frozenset()) -> tuple[np.ndarray, list[str]]:
    """Voto de cada lista al Senado en cada circunscripción.

    S:        voto simulado al Congreso (n, provincia, partido), filas que suman 1
    ajena:    por provincia, fracción de la lista FRENTE_AMPLIO que no entra en el pacto (Podemos, NC)
    sin_vox:  provincias donde Vox no presenta lista (su voto pasa en parte al PP: TRASVASE_VOX)
    pp_fuera: provincias donde el PP no presenta lista (su voto pasa en parte a Vox: TRASVASE_PP)
    Devuelve (array (n, circunscripción, lista) en el orden de circunscripciones(), nombres de las listas).
    """
    circ = circunscripciones()
    L = listas(partidos)
    il = {p: i for i, p in enumerate(L)}
    ip = {p: i for i, p in enumerate(partidos)}
    ir = {p: i for i, p in enumerate(provincias)}
    coc = cocientes_islas()
    loc = cuotas_locales()
    n = S.shape[0]
    out = np.zeros((n, len(circ), len(L)))
    for c, (nombre, fila) in enumerate(circ.iterrows()):
        s = S[:, ir[fila.provincia], :].copy()
        if fila.isla:
            f = np.array([coc.at[nombre, PATRON_2023[p]] if p in PATRON_2023 else 1.0 for p in partidos])
            s *= f
        for p in NO_LISTAS:
            if p in ip:
                s[:, ip[p]] = 0.0
        s /= s.sum(axis=1, keepdims=True)
        v = np.zeros((n, len(L)))
        for p in partidos:
            if p not in NO_LISTAS:
                v[:, il[p]] = s[:, ip[p]]
        if nombre in LOCALES_ISLA:
            v *= 1 - loc[nombre]
            v[:, il[LOCALES_ISLA[nombre][0]]] = loc[nombre]
        if fila.provincia in sin_vox and "VOX" in il:
            v[:, il["PP"]] += TRASVASE_VOX * v[:, il["VOX"]]
            v[:, il["VOX"]] = 0.0
        if fila.provincia in pp_fuera and "VOX" in il:
            v[:, il["VOX"]] += TRASVASE_PP * v[:, il["PP"]]
            v[:, il["PP"]] = 0.0
        if coalicion and fila.pacto and "PSOE" in il:
            aj = float(ajena.get(fila.provincia, 0.0))
            fa = v[:, il["FRENTE_AMPLIO"]].copy() if "FRENTE_AMPLIO" in il else 0.0
            v[:, il[PROGRESO]] = v[:, il["PSOE"]] + fa * (1 - aj)
            v[:, il["PSOE"]] = 0.0
            if "FRENTE_AMPLIO" in il:
                v[:, il["FRENTE_AMPLIO"]] = 0.0
                if "PODEMOS" in il:
                    v[:, il["PODEMOS"]] += fa * aj
        out[:, c, :] = v
    return out, L


def simular(S: np.ndarray, provincias: list[str], partidos: list[str], ajena: pd.Series,
            coalicion: bool = True, semilla: int = 2026, sin_vox: frozenset[str] = frozenset(),
            vox_en_pp: frozenset[str] = frozenset(), pp_fuera: frozenset[str] = frozenset(),
            vox_uno: frozenset[str] = frozenset()) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Senadores por lista en cada simulación (n x lista) y por circunscripción.
    `vox_en_pp`: provincias donde la lista del PP lleva un nombre de Vox (ver nombres_vox).
    `pp_fuera`:  provincias donde el PP no presenta lista.
    `vox_uno`:   provincias de 4 senadores donde Vox lleva un solo nombre y sus votantes marcan dos del PP."""
    V, L = voto_senado(S, provincias, partidos, ajena, coalicion, sin_vox, pp_fuera)
    circ = circunscripciones()
    rng = np.random.default_rng(semilla)
    u = rng.choice(umbrales_empate(), size=(V.shape[0], len(circ)))
    total = np.zeros((V.shape[0], len(L)), dtype=int)
    por_circ = {}
    for c, (nombre, fila) in enumerate(circ.iterrows()):
        if nombre in vox_uno and fila.escanos == 4 and "VOX" in L:
            pp, vx = L.index("PP"), L.index("VOX")
            v = V[:, c, :].copy()
            v[:, pp] += CUMPLE_VOX_UNO * 2 / 3 * v[:, vx]
            nombres = np.full(len(L), VOTOS_ELECTOR[4])
            nombres[vx] = 1
            e = repartir_candidatos(v, nombres, 4, u[:, c])
        else:
            e = repartir(V[:, c, :], int(fila.escanos), u[:, c])
        if nombre in vox_en_pp and "VOX" in L:
            pp, vx = L.index("PP"), L.index("VOX")
            tres = e[:, pp] == 3                 # la lista gana sus 3: entra también el nombre de Vox
            e[tres, pp] -= 1
            e[tres, vx] += 1
        total += e
        por_circ[nombre] = e
    usadas = [i for i, _ in enumerate(L) if total[:, i].any() or V[:, :, i].any()]
    cols = [L[i] for i in usadas]
    return (pd.DataFrame(total[:, usadas], columns=cols),
            {k: pd.DataFrame(e[:, usadas].astype("int8"), columns=cols) for k, e in por_circ.items()})


def central(s0: pd.DataFrame, ajena: pd.Series, coalicion: bool = True,
            sin_vox: frozenset[str] = frozenset(), pp_fuera: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Voto central (sin simular) de cada lista al Senado por circunscripción, en %."""
    V, L = voto_senado(s0.to_numpy()[None, :, :], list(s0.index), list(s0.columns), ajena, coalicion, sin_vox,
                       pp_fuera)
    df = pd.DataFrame(100 * V[0], index=circunscripciones().index, columns=L)
    return df.loc[:, df.max() > 0]
