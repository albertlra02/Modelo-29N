"""
Web del modelo electoral (Starlette + Jinja): una página por sección y el escenario en la URL,
de modo que cualquier vista se puede guardar o compartir tal cual.

Arranque:  python lanzar.py        (abre http://127.0.0.1:8029)

Las gráficas son las de interfaz/graficos.py (Plotly), serializadas y pintadas con plotly.js en
el navegador. La calculadora de mayorías corre en el navegador sobre las simulaciones del escenario.
Los escenarios que no están en la caché se calculan de uno en uno desde la propia página
(POST /api/calcular), que muestra el progreso y se recarga al terminar.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)                      # los módulos del modelo usan rutas relativas a la raíz
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402
from starlette.middleware import Middleware  # noqa: E402
from starlette.middleware.gzip import GZipMiddleware  # noqa: E402
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from interfaz import graficos as G  # noqa: E402
from interfaz.estilo import (BRONCE, FONDO, FUENTE, FUENTE_CIFRAS, GRIS_DATO, PANEL, RAMPA_CLARO, REGLA, TINTA, TINTA_2,  # noqa: E402
                             TINTA_3, color, mezcla, nombre, num, orden, pct)
from datos import escrutinio as E  # noqa: E402
from datos.cargar import escanos_2026  # noqa: E402
from motor import senado  # noqa: E402
from motor import noche as N  # noqa: E402
from motor import simulador as M  # noqa: E402
from web import datos as D  # noqa: E402
from web import acceso  # noqa: E402
from web.acceso import Acceso  # noqa: E402
from web.rapido import PaginasEnMemoria, precalentar  # noqa: E402

AQUI = Path(__file__).resolve().parent
ESTATICO = AQUI / "estatico"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

# Menú: seis secciones; las que tienen varias páginas muestran sus pestañas bajo la cabecera
SECCIONES = [
    ("Resumen", [("/", "Resumen")]),
    ("Congreso", [("/escanos", "Escaños y voto"), ("/mayorias", "Mayorías"), ("/provincias", "Provincias")]),
    ("Senado", [("/senado", "Senado")]),
    ("Escenarios", [("/participacion", "Participación"), ("/simulador", "¿Y si…?"), ("/comparar", "Comparar")]),
    ("Encuestas", [("/encuestas", "Encuestas"), ("/evolucion", "Evolución")]),
    ("Cómo funciona", [("/metodologia", "Cómo funciona")]),
]
NAV = [pag for _, pags in SECCIONES for pag in pags]          # todas las páginas del menú, en orden
# Fuera del menú: /noche, que entra sólo cuando hay un escrutinio cargado
OTRAS = ["/noche"]
DESDE = {"2025-01-01": "Enero de 2025", "2025-07-01": "Julio de 2025", "2026-01-01": "Enero de 2026",
         "2026-06-01": "Junio de 2026"}
TOKENS = {"tinta": TINTA, "tinta2": TINTA_2, "tinta3": TINTA_3, "regla": REGLA, "panel": PANEL,
          "bronce": BRONCE, "gris": GRIS_DATO, "fuente": FUENTE, "cifras": FUENTE_CIFRAS}
DEFECTOS = {url: getattr(D.Params(), k) for k, url in D.CLAVES_URL.items()}

entorno = Environment(loader=FileSystemLoader(AQUI / "plantillas"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
entorno.filters.update(pct=pct, num=num, miles=D.miles, nombre=nombre, color=color,
                       fecha_larga=D.fecha_larga, fecha_corta=D.fecha_corta)
entorno.globals.update(NAV=NAV, FECHAS=D.FECHAS, NOMBRES_CAND=D.NOMBRES_CAND, DETALLE_CAND=D.DETALLE_CAND,
                       NOMBRES_REPARTO=D.NOMBRES_REPARTO,
                       DETALLE_REPARTO=D.DETALLE_REPARTO, SIMULACIONES=D.SIMULACIONES,
                       PART_MIN=D.PARTICIPACION_MIN, PART_MAX=D.PARTICIPACION_MAX, PART_BASE=D.Params().participacion,
                       ULTIMA_ENCUESTA=D.ULTIMA_ENCUESTA, VERSION=D.VERSION, TOKENS=TOKENS, DEFECTOS=DEFECTOS,
                       NOMBRES_MOV=D.NOMBRES_MOV, DETALLE_MOV=D.DETALLE_MOV, NOMBRES_UTIL=D.NOMBRES_UTIL,
                       NOMBRES_DONDE=D.NOMBRES_DONDE, AMBITOS=D.AMBITOS, LIMITE_MOV=D.LIMITE_MOV,
                       LIMITE_UTIL=D.LIMITE_UTIL)


# ------------------------------------------------------------------ utilidades

_FONDO = re.compile(re.escape(FONDO), re.IGNORECASE)


def figura(fig) -> dict:
    """Figura de Plotly lista para incrustar. Las de interfaz/graficos.py están pensadas sobre el fondo
    gris de la página; aquí van sobre tarjetas blancas, así que su color de fondo pasa a ser el del panel."""
    js = _FONDO.sub(PANEL, fig.to_json()).replace("</", "<\\/")
    return {"json": js, "alto": int(fig.layout.height or 400)}


def _version_estaticos() -> str:
    return str(int(max(f.stat().st_mtime for f in ESTATICO.iterdir())))


def params(request) -> D.Params:
    return D.Params.de_query(request.query_params)


def pagina(request, plantilla: str, p: D.Params | None = None, estado: int = 200, **ctx) -> HTMLResponse:
    p = p or params(request)
    secciones = SECCIONES + ([("Noche electoral", [("/noche", "Noche electoral")])] if E.RUTA.exists() else [])
    ruta = request.url.path
    actual = next((pags for _, pags in secciones if any(r == ruta for r, _ in pags)), [])
    html = entorno.get_template(plantilla).render(
        ruta=ruta, p=p, q=p.query(), dias=D.dias_hasta(p.fecha), SECCIONES=secciones,
        PESTANAS=actual if len(actual) > 1 else [],
        dias_hoy=D.dias_hasta(pd.Timestamp.today().normalize()), DIAS_CALIBRADOS=D.DIAS_CALIBRADOS,
        v=_version_estaticos(), **ctx)
    return HTMLResponse(html, status_code=estado)


def esperar(request, p: D.Params, titulo: str, tarea: str = "escenario", auto: bool = True):
    """Si faltan escenarios por calcular, devuelve la página de progreso (si no, None)."""
    pend = D.pendientes(p, tarea)
    if not pend:
        return None
    total = len(D.escenarios_de(p, tarea))
    return pagina(request, "calculando.html", p, titulo=titulo, tarea=tarea, pendientes=len(pend), total=total,
                  auto=auto, texto=D.texto_tarea(pend[0], tarea), segundos=5 * len(pend))


def orden_voto(d: dict) -> list[str]:
    return list(d["tabla"].sort_values("voto_%", ascending=False).index)


# ------------------------------------------------------------------ páginas

def inicio(request):
    p = params(request)
    if r := esperar(request, p, "Resumen"):
        return r
    d = D.correr(p.escenario())
    sim, tabla, probs = d["sim"], d["tabla"], d["probs"]
    p_may = probs["P(PP + Vox ≥ 176)"]
    if p_may >= 0.5:
        titular = f"PP y Vox suman mayoría absoluta en el {pct(p_may)} de las simulaciones"
    else:
        titular = f"PP y Vox se quedan sin mayoría absoluta en el {pct(1 - p_may)} de las simulaciones"
    primero = "PP" if probs["P(PP primero)"] >= probs["P(PSOE primero)"] else "PSOE"
    segundo = "PSOE" if primero == "PP" else "PP"
    entradilla = (f"El {nombre(primero)} queda primero en el {pct(probs[f'P({primero} primero)'])} de las simulaciones, "
                  f"con una mediana de {tabla.at[primero, 'mediana']:.0f} escaños frente a "
                  f"{tabla.at[segundo, 'mediana']:.0f} del {nombre(segundo)}. Vox tendría {tabla.at['VOX', 'mediana']:.0f}.")
    filas = [
        ("El bloque de la investidura de 2023 llega a 176", pct(probs["P(bloque de investidura 2023 ≥ 176)"])),
        ("El PSOE queda primero", pct(probs["P(PSOE primero)"])),
        ("Ningún bloque llega a 176", pct(probs["P(ningún bloque llega)"])),
        ("Escaños de PP y Vox, mediana", f"{d['ppvox'].median():.0f}"),
    ]
    tarjetas = [{"clave": x, "mediana": tabla.at[x, "mediana"], "p10": tabla.at[x, "p10"], "p90": tabla.at[x, "p90"],
                 "voto": tabla.at[x, "voto_%"]}
                for x in tabla.sort_values(["mediana", "media"], ascending=False).index if tabla.at[x, "media"] >= 0.5]

    i = D.FECHAS.index(p.fecha)
    hace_un_mes = None
    if i >= 4 and D.calculado(p.escenario(fecha=D.FECHAS[i - 4])):
        antes = D.correr(p.escenario(fecha=D.FECHAS[i - 4]))["probs"]["P(PP + Vox ≥ 176)"]
        hace_un_mes = {"fecha": D.FECHAS[i - 4], "valor": antes, "cambio": round(100 * (p_may - antes))}
    return pagina(
        request, "inicio.html", p, titular=titular, entradilla=entradilla, p_may=p_may, filas=filas,
        hemiciclo=figura(G.hemiciclo(sim)), leyenda=G.leyenda_html(sim, tabla["voto_%"]), tarjetas=tarjetas,
        primero_prov=_primero_en_provincias(d), enc=D.resumen_encuestas(p.fecha),
        p_bloque=probs["P(bloque de investidura 2023 ≥ 176)"], hace_un_mes=hace_un_mes,
        senado_quintos=_derecha_pleno(_senado_de(d, "")["sim"])["p_quintos"])


def _primero_en_provincias(d: dict) -> dict:
    """Partido que es el más votado en más provincias, y en cuántas (para la portada)."""
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    cuenta = vp.idxmax(axis=1).value_counts()
    return {"partido": cuenta.index[0], "n": int(cuenta.iloc[0])}


def escanos(request):
    p = params(request)
    if r := esperar(request, p, "Voto y escaños"):
        return r
    d = D.correr(p.escenario())
    tabla, voto = d["tabla"], d["voto"]
    vis = D.visibles(d)
    filas = [{"clave": x, "voto": tabla.at[x, "voto_%"], "v10": voto.at[x, "p10"], "v90": voto.at[x, "p90"],
              "p10": tabla.at[x, "p10"], "mediana": tabla.at[x, "mediana"], "p90": tabla.at[x, "p90"],
              "media": tabla.at[x, "media"], "alguno": float((d["sim"][x] > 0).mean())}
             for x in orden_voto(d) if tabla.at[x, "media"] >= 0.05]
    return pagina(request, "escanos.html", p, filas=filas,
                  fig_voto=figura(G.rangos(voto, vis, eje="% de votos válidos", dec=1, sufijo=" %")),
                  fig_escanos=figura(G.rangos(tabla, vis)))


def mayorias(request):
    p = params(request)
    if r := esperar(request, p, "Mayorías"):
        return r
    d = D.correr(p.escenario())
    sim, probs = d["sim"], d["probs"]
    opciones = [x for x in sorted(sim.columns, key=orden) if sim[x].mean() >= 0.5]
    datos = {
        "partidos": [{"clave": x, "nombre": nombre(x), "color": color(x), "mediana": int(sim[x].median())}
                     for x in opciones],
        "sim": {x: sim[x].astype(int).tolist() for x in opciones},
        "atajos": {k: [x for x in v if x in opciones] for k, v in D.ATAJOS.items()},
        "tokens": TOKENS,
    }
    serie = probs.rename(D.ESCENARIOS).reindex(list(D.ESCENARIOS.values()))
    return pagina(request, "mayorias.html", p, datos=json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"),
                  fig_escenarios=figura(G.barras_prob(serie)))


# ------------------------------------------------------------------ simulador "¿y si…?"

MAYORIA = 176


def _partidos_simulador(d: dict) -> list[dict]:
    """Partidos con deslizador: los que tienen al menos un 0,8 % nacional en la proyección central."""
    nac = M.nacional_de(d["s0"].astype(float), D.pesos_2023())
    out = []
    for x in nac.sort_values(ascending=False).index:
        if x in M.NO_LISTAS or nac[x] < 0.008:
            continue
        v = 100 * float(nac[x])
        out.append({"clave": x, "base": round(v, 1), "max": float(min(60, max(10, round(2 * v + 10))))})
    return out


def _fijados(request, partidos: list[dict]) -> dict[str, float]:
    """Voto pedido en la URL (v_PP=34.5, en %), sólo para partidos con deslizador y si difiere del base."""
    out = {}
    for x in partidos:
        crudo = request.query_params.get("v_" + x["clave"])
        try:
            v = round(float(str(crudo).replace(",", ".")), 1)
        except ValueError:
            continue
        if 0 <= v <= x["max"] and abs(v - x["base"]) >= 0.05:
            out[x["clave"]] = v / 100
    return out


def _resultado_simulador(d: dict, fijados: dict[str, float]) -> dict:
    s0, pesos, esc = d["s0"].astype(float), D.pesos_2023(), escanos_2026()
    _, base = M.simular(s0, pesos, esc, {})
    s, prov = M.simular(s0, pesos, esc, fijados)
    total, total0 = prov.sum(), base.sum()
    nac = 100 * M.nacional_de(s, pesos)
    filas = [{"clave": x, "voto": float(nac[x]), "escanos": int(total[x]), "cambio": int(total[x] - total0[x]),
              "fijado": x in fijados}
             for x in sorted(total.index, key=lambda x: (-total[x], -nac[x])) if total[x] or total0[x]]
    sumas = [{"texto": k, "partidos": [x for x in v if x in total], "escanos": int(total.reindex(v).fillna(0).sum())}
             for k, v in D.ATAJOS.items()]
    sim = pd.DataFrame([total[total > 0]]).astype(int)
    vp = s.drop(columns=list(M.NO_LISTAS), errors="ignore")
    hover = pd.Series({x: f"<b>{x}</b> · {int(esc[x])} escaños<br>"
                          + " · ".join(f"{nombre(k)} {num(100 * v)} %" for k, v in vp.loc[x].nlargest(3).items())
                          + "<br>" + ", ".join(f"{nombre(k)} {int(v)}" for k, v in prov.loc[x][prov.loc[x] > 0]
                                              .sort_values(ascending=False).items())
                       for x in vp.index})
    dos = np.sort(vp.to_numpy(), axis=1)[:, -2:]
    mapa = G.mapa_ganador(vp.idxmax(axis=1), hover, pd.Series(100 * (dos[:, 1] - dos[:, 0]), index=vp.index))
    mapa.update_layout(height=460)
    return {"filas": filas, "sumas": sumas, "mayoria": MAYORIA, "hay_cambios": bool(fijados),
            "votos": {x: round(float(nac[x]), 1) for x in nac.index},
            "hemiciclo": figura(G.hemiciclo(sim)), "leyenda": G.leyenda_html(sim), "mapa": figura(mapa)}


def simulador_pagina(request):
    p = params(request)
    if r := esperar(request, p, "¿Y si…?"):
        return r
    d = D.correr(p.escenario())
    partidos = _partidos_simulador(d)
    fijados = _fijados(request, partidos)
    res = _resultado_simulador(d, fijados)
    for x in partidos:     # los no fijados ya llevan el reajuste proporcional
        x["valor"] = round(100 * fijados[x["clave"]], 1) if x["clave"] in fijados else res["votos"][x["clave"]]
    return pagina(request, "simulador.html", p, partidos=partidos, res=res)


def api_simulador(request):
    p = params(request)
    d = _exigir_calculado(p)
    res = _resultado_simulador(d, _fijados(request, _partidos_simulador(d)))
    html = entorno.get_template("_simulador.html").render(res=res)
    return JSONResponse({"html": html, "hemiciclo": res["hemiciclo"]["json"], "leyenda": res["leyenda"],
                         "mapa": res["mapa"]["json"], "votos": res["votos"]})


# ------------------------------------------------------------------ noche electoral

def noche(request):
    p = params(request)
    if r := esperar(request, p, "Noche electoral"):
        return r
    d = D.correr(p.escenario())
    esc2026 = escanos_2026()
    provs = list(esc2026.index)
    try:
        esc = E.leer(provincias=provs)
    except ValueError as e:
        return pagina(request, "noche.html", p, error=str(e), esc=None)
    if esc is None or not (esc.escrutado > 0).any():
        return pagina(request, "noche.html", p, esc=None, error=None, fichero=str(E.RUTA.relative_to(RAIZ)))
    s0 = d["s0"].astype(float)
    cuotas = E.cuotas(esc)
    s, proy = N.proyectar(s0, cuotas, esc.escrutado, esc2026)
    ahora = N.escanos_escrutados(list(s0.columns), cuotas, esc2026)
    pesos = D.pesos_2023().reindex(provs)
    avance = float((esc.escrutado * pesos).sum() / pesos.sum())
    votos = esc.drop(columns=["escrutado"]).rename(columns={"blancos": "BLANCO"}).sum()
    nac_esc = 100 * votos / votos.sum()
    nac_proy = 100 * M.nacional_de(s, D.pesos_2023())
    tot_proy, tot_ahora, med = proy.sum(), ahora.sum(), d["sim"].median()
    partidos = sorted({x for x in tot_proy.index if tot_proy[x] or tot_ahora[x]} | {x for x in med.index if med[x] >= 1},
                      key=lambda x: (-tot_proy.get(x, 0), -med.get(x, 0)))
    filas = [{"clave": x, "modelo": float(med.get(x, 0)), "ahora": int(tot_ahora.get(x, 0)),
              "proy": int(tot_proy.get(x, 0)), "dif": int(tot_proy.get(x, 0)) - round(float(med.get(x, 0))),
              "v_modelo": float(d["tabla"]["voto_%"].get(x, np.nan)), "v_esc": float(nac_esc.get(x, 0)),
              "v_proy": float(nac_proy.get(x, 0))} for x in partidos]
    sumas = [{"texto": k, "escanos": int(tot_proy.reindex(v).fillna(0).sum())} for k, v in D.ATAJOS.items()]
    # provincias: escrutado, quién va primero y dónde más se aparta lo contado de lo previsto
    c = N.alinear(cuotas, list(s0.columns))
    dev = 100 * (c - s0).drop(columns=list(M.NO_LISTAS), errors="ignore")
    prov_filas = []
    for x in provs:
        if esc.at[x, "escrutado"] <= 0:
            continue
        mayores = dev.loc[x].reindex(dev.loc[x].abs().sort_values(ascending=False).index[:3])
        prov_filas.append({"provincia": x, "escrutado": float(esc.at[x, "escrutado"]),
                           "primero": c.loc[x].drop(list(M.NO_LISTAS), errors="ignore").idxmax(),
                           "desvio": [(k, float(v)) for k, v in mayores.items() if abs(v) >= 0.5],
                           "max": float(dev.loc[x].abs().max()),
                           "reparto": ", ".join(f"{nombre(k)} {int(v)}" for k, v in
                                                proy.loc[x][proy.loc[x] > 0].sort_values(ascending=False).items())})
    prov_filas.sort(key=lambda f: -f["max"])
    vp = c.drop(columns=list(M.NO_LISTAS), errors="ignore")
    dos = np.sort(vp.to_numpy(), axis=1)[:, -2:]
    colores = pd.Series([G.tono_ventaja(vp.loc[x].idxmax(), 100 * (dos[i, 1] - dos[i, 0]))
                         if esc.at[x, "escrutado"] > 0 else SIN_CAMBIO for i, x in enumerate(provs)], index=provs)
    hover = pd.Series({x: f"<b>{x}</b> · {num(esc.at[x, 'escrutado'])} % escrutado<br>"
                          + " · ".join(f"{nombre(k)} {num(100 * v)} %" for k, v in vp.loc[x].nlargest(3).items())
                       for x in provs})
    sim = pd.DataFrame([tot_proy[tot_proy > 0]]).astype(int)
    return pagina(request, "noche.html", p, esc=esc, error=None, avance=avance, filas=filas, sumas=sumas,
                  provincias=prov_filas, mayoria=MAYORIA, simulacro=E.MARCA_SIMULACRO.exists(),
                  hemiciclo=figura(G.hemiciclo(sim)), leyenda=G.leyenda_html(sim),
                  mapa=figura(G.mapa_colores(colores, hover)), n_prov=len(prov_filas),
                  hora=pd.Timestamp.fromtimestamp(E.RUTA.stat().st_mtime).strftime("%H:%M"))


# ------------------------------------------------------------------ comparar dos escenarios

def _params_prefijo(request, prefijo: str, defecto: D.Params) -> D.Params:
    """Escenario leído de los parámetros con prefijo (a_fecha, b_part…); lo que falta, del escenario `defecto`."""
    q = {k[len(prefijo):]: v for k, v in request.query_params.items() if k.startswith(prefijo)}
    base = {url: getattr(defecto, k) for k, url in D.CLAVES_URL.items()}
    return D.Params.de_query(base | q)


def comparar(request):
    p = params(request)
    # sin nada elegido: el escenario actual frente al mismo sin palancas (si las hay) o con la otra opción de
    # candidaturas
    otra = "lista_unica" if p.candidaturas == "registradas" else "registradas"
    elegido = any(k.startswith(("a_", "b_")) for k in request.query_params)
    if p.escenario().palancas.activas:
        sin = {k: getattr(D.Params(), k) for k in list(D.NOMBRES_MOV) + list(D.NOMBRES_UTIL)}
        a, b_defecto = dataclasses.replace(p, **sin), p
    else:
        a, b_defecto = p, dataclasses.replace(p, candidaturas=otra)
    a = _params_prefijo(request, "a_", a if not elegido else p)
    b = _params_prefijo(request, "b_", b_defecto if not elegido else p)
    da, db = D.correr(a.escenario()), D.correr(b.escenario())       # lo ya calculado sale de la caché
    partidos = [x for x in dict.fromkeys(D.visibles(da) + D.visibles(db))]
    filas = []
    for x in partidos:
        ma = float(da["sim"][x].median()) if x in da["sim"] else None
        mb = float(db["sim"][x].median()) if x in db["sim"] else None
        va = float(da["tabla"].at[x, "voto_%"]) if x in da["tabla"].index else None
        vb = float(db["tabla"].at[x, "voto_%"]) if x in db["tabla"].index else None
        filas.append({"clave": x, "ma": ma, "mb": mb, "va": va, "vb": vb,
                      "dif": (mb or 0) - (ma or 0) if (ma is not None or mb is not None) else 0})
    filas.sort(key=lambda f: -max(f["ma"] or 0, f["mb"] or 0))
    probs = [{"texto": t, "a": float(da["probs"][k]), "b": float(db["probs"][k])}
             for k, t in D.ESCENARIOS.items() if k in da["probs"] and k in db["probs"]]
    sen = [{"texto": t, "a": float(da["senado"]["probs"][k]), "b": float(db["senado"]["probs"][k])}
           for k, t in list(D.ESCENARIOS_SENADO.items())[:3]]
    return pagina(request, "comparar.html", p, a=a, b=b, filas=filas, probs=probs, sen=sen,
                  senado_pp=(_derecha_pleno(da["senado"]["sim"])["mediana"],
                             _derecha_pleno(db["senado"]["sim"])["mediana"]))


def _mapa(d: dict, modo: str, partido: str | None) -> dict:
    prov = d["provincias"].set_index("Provincia")
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    hover = pd.Series({
        x: (f"<b>{x}</b> · {prov.at[x, 'Escaños']} escaños<br>"
            + " · ".join(f"{nombre(k)} {num(v)} %" for k, v in vp.loc[x].nlargest(3).items())
            + f"<br>Reparto más probable: {prov.at[x, 'Reparto']}")
        for x in prov.index})
    if modo == "partido":
        partido = partido if partido in partidos_mapa(d) else partidos_mapa(d)[0]
        fig = G.mapa_valor(vp[partido], hover, partido, f"Voto de {nombre(partido)}")
        return {"fig": figura(fig), "leyenda": [],
                "nota": f"Voto estimado de {nombre(partido)}. La escala cubre sólo su rango para que se vean las "
                        "diferencias."}
    if modo == "cambios":
        return _mapa_cambios(d, vp)
    ganador = vp.idxmax(axis=1)
    dos = np.sort(vp.to_numpy(dtype=float), axis=1)[:, -2:]
    ventaja = pd.Series(dos[:, 1] - dos[:, 0], index=vp.index)
    cuenta = ganador.value_counts()
    return {"fig": figura(G.mapa_ganador(ganador, hover, ventaja)),
            "leyenda": [{"nombre": nombre(x), "color": color(x), "n": int(n)} for x, n in cuenta.items()],
            "nota": "Partido con más voto estimado en cada provincia. Cuanto más claro, más ajustada su ventaja sobre el "
                    "segundo (menos de 5 puntos, de 5 a 15, más de 15)."}


SIN_CAMBIO = "#DCE2E8"      # provincias que no cambian de partido más votado (gris claro, sin significado de partido)
# En 2023 Frente Amplio y Podemos iban juntos en Sumar: para comparar escaños se suman
IZQ_2026, IZQ_2023 = ("FRENTE_AMPLIO", "PODEMOS", "SUMAR"), "SUMAR"


def _escanos_frente_2023(d: dict, prov: str) -> dict[str, int]:
    """Cambio de escaños (mediana simulada - 2023) por partido en una provincia; sólo los que cambian."""
    _, esc23 = D.resultados_2023()
    dist = d["detalle_prov"][prov]["dist"]
    ahora = {x: _cuantil(v, 0.5) for x, v in dist.items()}
    cambios = {}
    for x, c23 in D.EQUIVALENTES_2023.items():
        antes = int(esc23.at[prov, c23]) if c23 in esc23 else 0
        if x in ahora or antes:
            cambios[x] = ahora.get(x, 0) - antes
    izq = sum(ahora.get(x, 0) for x in IZQ_2026) - int(esc23.at[prov, IZQ_2023])
    if izq or any(x in ahora for x in IZQ_2026):
        cambios["IZQ"] = izq
    return {k: v for k, v in cambios.items() if v}


def _mapa_cambios(d: dict, vp: pd.DataFrame) -> dict:
    """Provincias donde cambia el partido más votado respecto a julio de 2023 (las demás, en gris)."""
    pct23, _ = D.resultados_2023()
    inverso = {v: k for k, v in D.EQUIVALENTES_2023.items()} | {IZQ_2023: IZQ_2023}
    g26, g23 = vp.idxmax(axis=1), pct23.idxmax(axis=1).map(inverso).reindex(vp.index)
    cambia = g26 != g23
    colores = pd.Series([color(a) if c else SIN_CAMBIO for a, c in zip(g26, cambia)], index=vp.index)
    hover = {}
    for x in vp.index:
        cam = _escanos_frente_2023(d, x)
        txt = " · ".join(f"{'Frente Amplio y Podemos' if k == 'IZQ' else nombre(k)} {v:+d}" for k, v in
                         sorted(cam.items(), key=lambda kv: -abs(kv[1]))).replace("-", "−")
        cabeza = (f"Pasa de {nombre(g23[x])} a {nombre(g26[x])}" if cambia[x] else f"Sigue ganando {nombre(g26[x])}")
        hover[x] = f"<b>{x}</b><br>{cabeza}<br>Escaños frente a 2023: {txt or 'los mismos'}"
    hover = pd.Series(hover)
    nuevos = g26[cambia].value_counts()
    leyenda = [{"nombre": f"Pasan a {nombre(x)}", "color": color(x), "n": int(n)} for x, n in nuevos.items()]
    leyenda.append({"nombre": "Sin cambio", "color": SIN_CAMBIO, "n": int((~cambia).sum())})
    return {"fig": figura(G.mapa_colores(colores, hover)), "leyenda": leyenda,
            "nota": "En color, las provincias que cambian de partido más votado respecto a 2023; en gris, las que siguen "
                    "igual. Pasa el ratón para ver los escaños que gana o pierde cada partido."}


def partidos_mapa(d: dict) -> list[str]:
    vp = d["voto_prov"]
    return [x for x in orden_voto(d) if x in vp.columns and x in RAMPA_CLARO]


def _cuantil(dist: dict[int, float], q: float) -> int:
    """Cuantil de una distribución discreta {escaños: % de simulaciones}."""
    acum = 0.0
    for k in sorted(dist):
        acum += dist[k]
        if acum >= 100 * q - 1e-9:
            return k
    return max(dist)


def _detalle_provincia(d: dict, prov: str) -> dict:
    """Todo lo que enseña el panel de una provincia: voto, escaños simulados, 2023 y repartos."""
    fila = d["provincias"].set_index("Provincia").loc[prov]
    det = d["detalle_prov"][prov]
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore").loc[prov]
    pct23, esc23 = D.resultados_2023()
    claves = set(det["dist"]) | set(vp[vp >= 1].index)
    partidos = []
    for x in claves:
        dist = det["dist"].get(x, {0: 100.0})
        visibles = {k: v for k, v in dist.items() if v >= 0.5}
        tope = max(visibles.values())
        c23 = D.EQUIVALENTES_2023.get(x)
        partidos.append({
            "clave": x, "voto": float(vp.get(x, 0.0)), "mediana": _cuantil(dist, 0.5),
            "p10": _cuantil(dist, 0.1), "p90": _cuantil(dist, 0.9),
            "barras": [{"k": k, "pct": v, "alto": round(100 * v / tope)} for k, v in sorted(visibles.items())],
            "voto23": float(pct23.at[prov, c23]) if c23 in pct23 else None,
            "esc23": int(esc23.at[prov, c23]) if c23 in esc23 else None,
        })
    partidos.sort(key=lambda r: (-r["mediana"], -r["voto"]))
    sumar = None
    if {"FRENTE_AMPLIO", "PODEMOS", "SUMAR"} & claves and pct23.at[prov, "SUMAR"] > 0:
        sumar = {"voto": float(pct23.at[prov, "SUMAR"]), "esc": int(esc23.at[prov, "SUMAR"])}
    return {"nombre": prov, "ccaa": fila["CCAA"], "escanos": int(fila["Escaños"]),
            "repartos": det["repartos"], "partidos": partidos, "sumar23": sumar,
            "escanos23": int(esc23.loc[prov].sum())}


def api_provincia(request):
    p = params(request)
    d = _exigir_calculado(p)
    prov = request.query_params.get("nombre", "")
    if prov not in d["detalle_prov"]:
        raise HTTPException(404, "Provincia desconocida")
    html = entorno.get_template("_provincia.html").render(prov=_detalle_provincia(d, prov))
    return JSONResponse({"html": html, "nombre": prov})


def provincias(request):
    p = params(request)
    if r := esperar(request, p, "Provincias"):
        return r
    d = D.correr(p.escenario())
    prov = d["provincias"].set_index("Provincia")
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    filas = [{"provincia": x, "ccaa": r_["CCAA"], "escanos": int(r_["Escaños"]), "reparto": r_["Reparto"],
              "frecuencia": int(r_["Reparto más probable"]),
              "primero": vp.loc[x].idxmax()}
             for x, r_ in prov.iterrows()]
    vpt = vp.loc[:, vp.max() >= 1]
    vpt = vpt[sorted(vpt.columns, key=lambda c: -vpt[c].sum())]
    return pagina(request, "provincias.html", p, mapa=_mapa(d, "ganador", None), partidos=partidos_mapa(d),
                  filas=filas, ccaa=sorted(prov.CCAA.unique()),
                  voto_cols=list(vpt.columns), voto_filas=list(vpt.sort_index().iterrows()))


# ------------------------------------------------------------------ Senado

SENADORES = 208
MITAD_SENADO = SENADORES // 2 + 1


def _por_provincia_senado(s: dict) -> pd.DataFrame:
    """Una fila por provincia: senadores del reparto más probable sumando sus circunscripciones,
    lista con más senadores y texto emergente."""
    circ, voto = s["circunscripciones"], s["voto"]
    filas = {}
    for prov, g in circ.groupby("Provincia", sort=False):
        suma = pd.Series(dtype=float)
        for m in g.moda:
            suma = suma.add(pd.Series(m, dtype=float), fill_value=0)
        votos = voto.loc[g["Circunscripción"]].sum()
        # empate de senadores (2 + 2): gana la lista con más voto estimado
        orden_ = sorted(suma.index, key=lambda x: (-suma[x], -votos.get(x, 0)))
        lineas = []
        for _, f in g.iterrows():
            pre = f"{f['Circunscripción']}: " if f["Isla"] else ""
            lineas.append(f"{pre}{f['Reparto']} ({f['Reparto más probable']} %)")
        total = int(g["Senadores"].sum())
        if g["Coalición"].all():
            pacto = "con coalición"
        elif not g["Coalición"].any():
            pacto = "sin coalición"
        else:
            pacto = "coalición sólo en La Gomera"
        principal = g.sort_values("Senadores", ascending=False).iloc[0]    # en las islas, la mayor
        filas[prov] = {"ganador": orden_[0], "senadores": total,
                       "p_ganadora": float(principal["P(ganadora)"]),
                       "derecha": int(sum(suma.get(x, 0) for x in DERECHA_SEN)),
                       "hover": f"<b>{prov}</b> · {total} senadores · {pacto}<br>Reparto más probable: "
                                + "<br>".join(lineas)}
    return pd.DataFrame.from_dict(filas, orient="index")


# Hipótesis de retirada de Vox del Senado (motor/senado.py): clave de la URL -> texto del selector
HIPOTESIS_VOX = {
    "": "Con el acuerdo PP-Vox del 26 de octubre",
    "sin": "Sin pacto: cada uno en todas",
    "amplia": "Vox se retira casi en todas",
}


def _hipotesis_vox(request) -> str:
    h = request.query_params.get("vox", "")
    return h if h in HIPOTESIS_VOX else ""


def _senado_de(d: dict, vox: str) -> dict:
    """Resumen del Senado con la hipótesis elegida ('' = el acuerdo PP-Vox, 'sin' = cada uno en todas)."""
    if vox == "sin":
        return d["senado"]
    return d["senado_vox"][vox or "pacto"]


DERECHA_SEN = ("PP", "VOX", "UPN")


def _derecha_pleno(sim: pd.DataFrame) -> dict:
    """Bloque de derechas (PP + Vox + UPN) en el Senado completo: senadores en cada simulación, umbrales y
    probabilidades de los tres quintos y de la mayoría absoluta."""
    pl = senado.pleno(sim)
    t = pl[[x for x in DERECHA_SEN if x in pl]].sum(axis=1)
    total = SENADORES + len(senado.designados())
    quintos, mayoria = -(-3 * total // 5), total // 2 + 1
    return {"t": t, "total": total, "quintos": quintos, "mayoria": mayoria,
            "p_quintos": float((t >= quintos).mean()), "p_mayoria": float((t >= mayoria).mean()),
            "mediana": float(t.median()), "p10": float(t.quantile(0.1)), "p90": float(t.quantile(0.9))}


def _comparar_vox(d: dict, q: str) -> list[dict]:
    """Una fila por hipótesis de Vox: lo principal del Senado en cada una, para compararlas."""
    filas = []
    for h, texto in HIPOTESIS_VOX.items():
        s = _senado_de(d, h)
        sim = s["sim"]
        enlace = q + ("&" if q else "?") + f"vox={h}" if h else (q or "?")
        filas.append({"clave": h, "texto": texto, "url": "/senado" + enlace,
                      "pp": sim["PP"].median(), "vox": sim["VOX"].median() if "VOX" in sim else 0,
                      "vox_en_pp": s["vox_en_pp_sim"].median() if "vox_en_pp_sim" in s else None,
                      **{k: v for k, v in _derecha_pleno(sim).items() if k != "t"},
                      "sin_vox": s.get("sin_vox", []), "nombres": s.get("vox_en_pp", [])})
    return filas


# Mapa del Senado: tramos de seguridad de la lista ganadora (probabilidad, aclarado como en el del Congreso)
TRAMOS_SEGURIDAD = [(70, 0.55), (90, 0.25)]             # por encima del 90 %, color pleno
# Bloque de derechas: tono según la parte de los senadores de la provincia que se lleva (neutro, no de partido)
TRAMOS_DERECHA = [(0.0, "Ninguno", 0.92), (0.25, "1 de cada 4", 0.72), (0.5, "2 de cada 4", 0.48),
                  (0.75, "3 de cada 4", 0.22), (1.0, "Todos", 0.0)]
# Qué hace el acuerdo PP-Vox en cada provincia (colores neutros: no son partidos)
ACUERDO = {"vox_fuera": ("Vox no se presenta", BRONCE),
           "vox_uno": ("Vox con un solo candidato", mezcla(BRONCE, PANEL, 0.5)),
           "pp_fuera": ("El PP no se presenta", "#4A5664"), "separados": ("Sin acuerdo", SIN_CAMBIO)}


def _mapa_senado(d: dict, vox: str, modo: str = "ganador") -> dict:
    s = _senado_de(d, vox)
    pp = _por_provincia_senado(s)
    if modo == "derecha":
        cuota = pp.derecha / pp.senadores
        tramo = cuota.map(lambda c: next(t for t in TRAMOS_DERECHA if c <= t[0] + 1e-9))
        colores = tramo.map(lambda t: mezcla(BRONCE, PANEL, t[2]))
        hover = pp.hover + "<br>PP, Vox y UPN: " + pp.derecha.astype(str) + " de " + pp.senadores.astype(str)
        cuenta = tramo.map(lambda t: t[1]).value_counts()
        return {"fig": figura(G.mapa_colores(colores, hover)),
                "leyenda": [{"nombre": t[1], "color": mezcla(BRONCE, PANEL, t[2]), "n": int(cuenta.get(t[1], 0))}
                            for t in TRAMOS_DERECHA if cuenta.get(t[1], 0)],
                "nota": "Parte de los senadores de cada provincia que se lleva el bloque de derechas (PP, Vox y UPN) en el "
                        "reparto más probable. Cuanto más oscuro, más senadores."}
    if modo == "acuerdo":
        con, sin = _por_provincia_senado(_senado_de(d, "")), _por_provincia_senado(d["senado"])
        tipo = pd.Series({p: ("vox_fuera" if p in senado.PACTO_VOX_FUERA else "pp_fuera" if p in senado.PACTO_PP_FUERA
                              else "vox_uno" if p in senado.PACTO_VOX_UNO else "separados") for p in con.index})
        dif = con.derecha - sin.derecha.reindex(con.index)
        hover = (con.hover + "<br><b>" + tipo.map(lambda t: ACUERDO[t][0]) + "</b>: PP, Vox y UPN "
                 + sin.derecha.reindex(con.index).astype(str) + " → " + con.derecha.astype(str) + " senadores")
        cuenta = tipo.value_counts()
        return {"fig": figura(G.mapa_colores(tipo.map(lambda t: ACUERDO[t][1]), hover)),
                "leyenda": [{"nombre": texto, "color": c, "n": int(cuenta.get(k, 0))} for k, (texto, c) in ACUERDO.items()],
                "nota": f"Qué hace el acuerdo PP-Vox del 26 de octubre en cada provincia. En el reparto más probable, el "
                        f"bloque de derechas gana {int(dif.clip(lower=0).sum())} senadores con el acuerdo y pierde "
                        f"{int(-dif.clip(upper=0).sum())}. Pasa el ratón para verlo provincia a provincia."}
    tono = pd.Series([mezcla(color(g), PANEL, next((t for tope, t in TRAMOS_SEGURIDAD if p < tope), 0.0))
                      for g, p in zip(pp.ganador, pp.p_ganadora)], index=pp.index)
    hover = pp.hover + "<br>" + pp.ganador.map(nombre) + " primera en el " + pp.p_ganadora.round().astype(int).astype(str) \
        + " % de las simulaciones"
    cuenta = pp.ganador.value_counts()
    return {"fig": figura(G.mapa_colores(tono, hover)),
            "leyenda": [{"nombre": nombre(x), "color": color(x), "n": int(n)} for x, n in cuenta.items()],
            "nota": "Lista con más senadores en el reparto más probable de cada provincia (en Baleares y Canarias, "
                    "sumando sus islas). Cuanto más claro, menos segura (gana en menos del 70 %, del 70 al 90 % o más "
                    "del 90 % de las simulaciones)."}


def _rango(sim: pd.DataFrame, x: str) -> dict | None:
    if x not in sim:
        return None
    return {"mediana": sim[x].median(), "p10": sim[x].quantile(0.1), "p90": sim[x].quantile(0.9)}


def senado_pagina(request):
    p = params(request)
    if r := esperar(request, p, "Senado"):
        return r
    d = D.correr(p.escenario())
    vox = _hipotesis_vox(request)
    s = _senado_de(d, vox)
    sim, sin, probs = s["sim"], s["sin_coalicion"], s["probs"]
    der, der_sin = _derecha_pleno(sim), _derecha_pleno(sin)
    falta = der["quintos"] - der["mediana"]
    titular = (f"El bloque de derechas llega a los tres quintos del Senado en el {pct(der['p_quintos'])} de las "
               f"simulaciones")
    entradilla = (f"PP, Vox y UPN necesitan {der['quintos']} de los {der['total']} senadores para los tres quintos, que "
                  f"permiten renovar el Constitucional sin pactar. Su mediana es de {der['mediana']:.0f}"
                  + (f", a {falta:.0f} de la cifra" if falta > 0 else "") + ". La mayoría absoluta "
                  f"({der['mayoria']}) la tienen en el {pct(der['p_mayoria'])} de las simulaciones.")
    if vox == "":
        entradilla = (f"Con el acuerdo PP-Vox: Vox no se presenta en {len(s['sin_vox'])} provincias, el PP no se "
                      f"presenta en {len(s.get('pp_fuera', []))} y en otras {len(s.get('vox_uno', []))} Vox lleva un "
                      "solo candidato y pide marcar dos del PP. " + entradilla)
    elif vox == "amplia":
        entradilla = (f"Hipótesis: Vox no presenta lista al Senado en {len(s['sin_vox'])} provincias, pide el voto "
                      f"para el PP y en {len(s['vox_en_pp'])} de ellas lleva un candidato en la lista del PP. "
                      + entradilla)
    filas_prob = [
        (f"Mayoría absoluta ({der['mayoria']})", pct(der["p_mayoria"])),
        ("Senadores del bloque, mediana", f"{der['mediana']:.0f}"),
        ("80 % de las simulaciones", f"{der['p10']:.0f}–{der['p90']:.0f}"),
        ("Tres quintos si no hubiera coalición de PSOE y FA", pct(der_sin["p_quintos"])),
    ]
    listas = [x for x in dict.fromkeys(list(sim.columns) + list(sin.columns))
              if (x in sim and sim[x].mean() >= 0.05) or (x in sin and sin[x].mean() >= 0.05)]
    listas.sort(key=lambda x: -(sim[x].mean() if x in sim else sin[x].mean()))
    tabla = [{"clave": x, "con": _rango(sim, x), "sin": _rango(sin, x)} for x in listas]
    circ = s["circunscripciones"].sort_values(["Senadores", "Circunscripción"], ascending=[False, True])
    filas = [{"circ": f["Circunscripción"], "ccaa": f["CCAA"], "isla": f["Isla"], "provincia": f["Provincia"],
              "senadores": int(f["Senadores"]), "reparto": f["Reparto"], "ganadora": f["Ganadora"],
              "p_ganadora": int(f["P(ganadora)"])}
             for _, f in circ.iterrows()]
    pl = senado.pleno(sim)
    return pagina(request, "senado.html", p, titular=titular, entradilla=entradilla, der=der, filas_prob=filas_prob,
                  hemiciclo=figura(G.hemiciclo(pl, der["total"], "senadores", f"tres quintos: {der['quintos']}",
                                               umbral=der["quintos"])),
                  leyenda=G.leyenda_html(pl, total=der["total"]), tabla=tabla, mapa=_mapa_senado(d, vox),
                  vox=vox, comparar_vox=_comparar_vox(d, p.query()), vox_con_lista=senado.VOX_CON_LISTA,
                  trasvase_vox=senado.TRASVASE_VOX, p_pp_seguro=senado.P_PP_SEGURO,
                  trasvase_pp=senado.TRASVASE_PP, marca_pp_vox=senado.MARCA_PP_VOX,
                  pacto_vox_fuera=senado.PACTO_VOX_FUERA, pacto_pp_fuera=senado.PACTO_PP_FUERA,
                  pacto_vox_uno=senado.PACTO_VOX_UNO,
                  filas=filas, ccaa=sorted(circ["CCAA"].unique()),
                  **_pleno_senado(sim, sin, probs))


def _pleno_senado(sim: pd.DataFrame, sin: pd.DataFrame, probs: pd.Series) -> dict:
    """El Senado completo: electos simulados + designados autonómicos actuales (fijos)."""
    des = senado.designados()
    por_lista = senado.designados_por_lista()
    pl = senado.pleno(sim)
    total = SENADORES + len(des)
    mayoria = total // 2 + 1
    listas = sorted([x for x in pl.columns if pl[x].mean() >= 0.05], key=lambda x: -pl[x].mean())
    tabla = [{"clave": x, "electos": sim[x].median() if x in sim else 0, "designados": int(por_lista.get(x, 0)),
              "total": pl[x].median(), "p10": pl[x].quantile(0.1), "p90": pl[x].quantile(0.9)} for x in listas]
    pp_pl, pp_sin = pl["PP"].median(), senado.pleno(sin)["PP"].median()
    por_ccaa = []
    for ccaa, g in des.groupby("comunidad"):
        cuenta = g.partido.value_counts()
        por_ccaa.append({"ccaa": ccaa, "n": len(g), "reparto": ", ".join(f"{k} {v}" for k, v in cuenta.items()),
                         "nombres": "; ".join(f"{r.nombre} ({r.partido})" for r in g.itertuples())})
    por_ccaa.sort(key=lambda f: (-f["n"], f["ccaa"]))
    return {
        "pleno_total": total, "pleno_mayoria": mayoria, "pleno_pp": pp_pl, "pleno_pp_sin": pp_sin,
        "pleno_designados": len(des), "pleno_tabla": tabla, "pleno_ccaa": por_ccaa,
        "pleno_filas": [
            ("PP, Vox y UPN: tres quintos (160)", pct(_derecha_pleno(sim)["p_quintos"])),
            ("PP, Vox y UPN: mayoría absoluta", pct(_derecha_pleno(sim)["p_mayoria"])),
            ("La izquierda: mayoría absoluta", pct(probs["P(izquierda mayoría absoluta)"])),
        ],
        "pleno_hemiciclo": figura(G.hemiciclo(pl, total, "senadores", f"mayoría absoluta: {mayoria}")),
        "pleno_leyenda": G.leyenda_html(pl, total=total),
    }


def _fig_encuestas(fecha: str, partidos: list[str], desde: str) -> dict:
    enc, series = D.encuestas(fecha)
    return figura(G.serie_encuestas({k: series[k] for k in partidos}, enc, desde))


def _fig_casas(fecha: str, partido: str) -> dict:
    _, series = D.encuestas(fecha)
    return figura(G.efectos_casa(series[partido].casas, partido))


def encuestas(request):
    p = params(request)
    if r := esperar(request, p, "Encuestas"):
        return r
    d = D.correr(p.escenario())
    enc, series = D.encuestas(p.fecha)
    hace_30 = pd.Timestamp(p.fecha) - pd.Timedelta(days=30)
    medias = []
    for x, r_ in series.items():
        s = r_.serie
        antes = s[s.fecha <= hace_30]
        media, sd = r_.final
        medias.append({"clave": x, "media": media, "sd": sd,
                       "cambio": media - float(antes.media.iloc[-1]) if len(antes) else None})
    ultimas = enc.sort_values("fin", ascending=False).head(20)
    ultimas = [{"fin": D.fecha_corta(e.fin), "casa": e.encuestadora,
                "medio": e.medio if isinstance(e.medio, str) else "", "n": e.n,
                "valores": [getattr(e, x) for x in D.PARTIDOS_ENCUESTAS]}
               for e in ultimas.itertuples()]
    diag = d["diag"].rename(columns={"ccaa": "Comunidad", "partido": "Partido", "swing_nacional": "Swing nacional (%)",
                                     "encuestas": "Encuestas", "media_encuestas": "Media de encuestas (%)",
                                     "objetivo": "Usado por el modelo (%)"})
    return pagina(request, "encuestas.html", p, n_enc=len(enc), n_casas=enc.casa.nunique(), medias=medias,
                  fig_serie=_fig_encuestas(p.fecha, ["PP", "PSOE", "VOX", "SUMAR"], "2026-01-01"),
                  fig_casas=_fig_casas(p.fecha, "PP"), partidos=D.PARTIDOS_ENCUESTAS, DESDE=DESDE,
                  ultimas=ultimas, diag_cols=list(diag.columns), diag=diag.to_dict("records"))


def evolucion(request):
    p = params(request)
    pend = D.pendientes(p, "evolucion")
    if r := esperar(request, p, "Evolución", "evolucion", auto=len(pend) <= 2):
        return r
    ev = D.evolucion(p)
    pr, fechas = ev["probs"], D.FECHAS
    titulos = {f: pct(pr.at[f, "P(PP + Vox ≥ 176)"]) for f in fechas}
    detalles = {f: f"PP y Vox llegan a 176 · {D.fecha_larga(f)}" for f in fechas}
    etiquetas = {f: D.fecha_corta(f) for f in fechas}
    idx = pd.to_datetime(pr.index)
    bloques = pd.DataFrame({"PP + Vox": 100 * pr["P(PP + Vox ≥ 176)"].to_numpy(),
                            "Bloque de 2023": 100 * pr["P(bloque de investidura 2023 ≥ 176)"].to_numpy()}, index=idx)
    med = ev["medianas"]
    principales = [x for x in ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "FRENTE_AMPLIO"] if x in med]
    esc = pd.DataFrame({nombre(x): med[x].to_numpy() for x in principales}, index=idx)
    filas = [{"fecha": f, "ppvox": pr.at[f, "P(PP + Vox ≥ 176)"],
              "bloque": pr.at[f, "P(bloque de investidura 2023 ≥ 176)"],
              "medianas": [med.at[f, x] for x in principales]} for f in reversed(fechas)]
    return pagina(
        request, "evolucion.html", p, principales=principales, filas=filas,
        fig_animado=figura(G.hemiciclo_animado(ev["reps"], titulos, detalles, etiquetas)),
        fig_bloques=figura(G.lineas_evolucion(bloques, {"PP + Vox": color("PP"), "Bloque de 2023": color("PSOE")},
                                              "% de simulaciones", sufijo=" %", rango_y=[0, 100], marca=p.fecha,
                                              umbral=50)),
        fig_escanos=figura(G.lineas_evolucion(esc, {nombre(x): color(x) for x in principales}, "Escaños",
                                              marca=p.fecha)))


def participacion(request):
    p = params(request)
    pend = D.pendientes(p, "barrido")
    if r := esperar(request, p, "Participación", "barrido", auto=len(pend) <= 2):
        return r
    df = D.barrido(p)
    filas = df.sort_values(["candidaturas", "participacion"]).to_dict("records")
    return pagina(request, "participacion.html", p, filas=filas, n_barrido=D.N_SIM_BARRIDO,
                  fig_mayoria=figura(G.barrido(df, "P(mayoría PP + Vox)", "Probabilidad")),
                  fig_psoe=figura(G.barrido(df, "P(PSOE primero)", "Probabilidad")))


def metodologia(request):
    return pagina(request, "metodologia.html", ELECCION=D.ELECCION)


# ------------------------------------------------------------------ API (fragmentos que cambian sin recargar)

def _exigir_calculado(p: D.Params) -> dict:
    if not D.calculado(p.escenario()):
        raise HTTPException(409, "Escenario sin calcular")
    return D.correr(p.escenario())


def api_mapa(request):
    p = params(request)
    m = _mapa(_exigir_calculado(p), request.query_params.get("modo", "ganador"), request.query_params.get("partido"))
    return JSONResponse({"fig": m["fig"]["json"], "leyenda": m["leyenda"], "nota": m["nota"]})


def api_mapa_senado(request):
    p = params(request)
    m = _mapa_senado(_exigir_calculado(p), _hipotesis_vox(request), request.query_params.get("modo", "ganador"))
    return JSONResponse({"fig": m["fig"]["json"], "leyenda": m["leyenda"], "nota": m["nota"]})


def api_encuestas(request):
    p = params(request)
    q = request.query_params
    partidos = [x for x in q.get("partidos", "").split(",") if x in D.PARTIDOS_ENCUESTAS] or ["PP"]
    desde = q.get("desde") if q.get("desde") in DESDE else "2026-01-01"
    return JSONResponse({"fig": _fig_encuestas(p.fecha, partidos, desde)["json"]})


def api_casas(request):
    p = params(request)
    partido = request.query_params.get("partido")
    partido = partido if partido in D.PARTIDOS_ENCUESTAS else "PP"
    return JSONResponse({"fig": _fig_casas(p.fecha, partido)["json"]})


def api_calcular(request):
    """Calcula el siguiente escenario pendiente de una tarea y dice cuántos quedan."""
    p = params(request)
    tarea = request.query_params.get("tarea")
    if tarea not in D.TAREAS:
        raise HTTPException(400, "Tarea desconocida")
    pend = D.pendientes(p, tarea)
    if pend:
        D.correr(pend[0])
        pend = pend[1:]
    return JSONResponse({"pendientes": len(pend), "total": len(D.escenarios_de(p, tarea)),
                         "texto": D.texto_tarea(pend[0], tarea) if pend else "Listo."})


def descargar(request):
    p = params(request)
    sim = _exigir_calculado(p)["sim"]
    nombre_fichero = f"simulaciones_{p.fecha}_{p.candidaturas}_{p.participacion}.csv"
    return Response(sim.to_csv(index=False), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre_fichero}"'})


def plotly_js(request):
    return FileResponse(PLOTLY_JS, media_type="text/javascript", headers={"Cache-Control": "public, max-age=604800"})


# ------------------------------------------------------------------ errores

async def no_encontrado(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    if exc.status_code != 404:
        return pagina(request, "error.html", estado=exc.status_code, titulo="Algo no ha ido bien", mensaje=exc.detail)
    return pagina(request, "error.html", estado=404, titulo="Esta página no existe",
                  mensaje="Puede que el enlace esté mal escrito. Vuelve al resumen o elige una sección arriba.")


async def fallo(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=500)
    return pagina(request, "error.html", estado=500, titulo="El modelo no ha podido calcular este escenario",
                  mensaje=str(exc))


def salud(request):
    """Comprobación de vida para el alojamiento (sin contraseña ni veda)."""
    return Response("ok", media_type="text/plain")


@contextlib.asynccontextmanager
async def arranque(app_):
    D.iniciar()
    clave = os.environ.get("CLAVE")
    precalentar(app, f"{acceso.COOKIE}={acceso.ficha(clave)}" if clave else None)
    yield


app = Starlette(
    routes=[
        Route("/", inicio), Route("/escanos", escanos), Route("/mayorias", mayorias),
        Route("/simulador", simulador_pagina), Route("/provincias", provincias), Route("/senado", senado_pagina),
        Route("/encuestas", encuestas), Route("/evolucion", evolucion), Route("/participacion", participacion),
        Route("/comparar", comparar), Route("/noche", noche), Route("/metodologia", metodologia),
        Route("/api/mapa", api_mapa), Route("/api/mapa_senado", api_mapa_senado), Route("/api/provincia", api_provincia),
        Route("/api/simulador", api_simulador),
        Route("/api/encuestas", api_encuestas), Route("/api/casas", api_casas),
        Route("/api/calcular", api_calcular, methods=["POST"]),
        Route("/descargar/simulaciones.csv", descargar),
        Route("/estatico/plotly.min.js", plotly_js),
        Route("/salud", salud),
        Mount("/estatico", StaticFiles(directory=ESTATICO), name="estatico"),
    ],
    # de fuera a dentro: contraseña y veda (web/acceso.py), páginas en memoria (web/rapido.py), compresión
    middleware=[Middleware(Acceso), Middleware(PaginasEnMemoria), Middleware(GZipMiddleware, minimum_size=1000,
                                                                             compresslevel=5)],
    exception_handlers={HTTPException: no_encontrado, Exception: fallo},
    lifespan=arranque,
)
