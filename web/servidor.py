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
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)                      # los módulos del modelo usan rutas relativas a la raíz
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
import plotly  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from interfaz import graficos as G  # noqa: E402
from interfaz.estilo import (BRONCE, FONDO, FUENTE, FUENTE_CIFRAS, GRIS_DATO, PANEL, RAMPA_CLARO, REGLA, TINTA, TINTA_2,  # noqa: E402
                             TINTA_3, color, nombre, num, orden, pct)
from web import datos as D  # noqa: E402

AQUI = Path(__file__).resolve().parent
ESTATICO = AQUI / "estatico"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

NAV = [("/", "Resumen"), ("/escanos", "Escaños"), ("/mayorias", "Mayorías"), ("/provincias", "Provincias"),
       ("/encuestas", "Encuestas"), ("/evolucion", "Evolución"), ("/participacion", "Participación"),
       ("/metodologia", "Metodología")]
DESDE = {"2025-01-01": "Enero de 2025", "2025-07-01": "Julio de 2025", "2026-01-01": "Enero de 2026",
         "2026-06-01": "Junio de 2026"}
TOKENS = {"tinta": TINTA, "tinta2": TINTA_2, "tinta3": TINTA_3, "regla": REGLA, "panel": PANEL,
          "bronce": BRONCE, "gris": GRIS_DATO, "fuente": FUENTE, "cifras": FUENTE_CIFRAS}
DEFECTOS = {url: getattr(D.Params(), k) for k, url in D.CLAVES_URL.items()}

entorno = Environment(loader=FileSystemLoader(AQUI / "plantillas"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
entorno.filters.update(pct=pct, num=num, miles=D.miles, nombre=nombre, color=color,
                       fecha_larga=D.fecha_larga, fecha_corta=D.fecha_corta)
entorno.globals.update(NAV=NAV, FECHAS=D.FECHAS, NOMBRES_CAND=D.NOMBRES_CAND, NOMBRES_REPARTO=D.NOMBRES_REPARTO,
                       DETALLE_REPARTO=D.DETALLE_REPARTO, SIMULACIONES=D.SIMULACIONES,
                       PART_MIN=D.PARTICIPACION_MIN, PART_MAX=D.PARTICIPACION_MAX, PART_BASE=D.Params().participacion,
                       ULTIMA_ENCUESTA=D.ULTIMA_ENCUESTA, VERSION=D.VERSION, TOKENS=TOKENS, DEFECTOS=DEFECTOS)


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
    html = entorno.get_template(plantilla).render(
        ruta=request.url.path, p=p, q=p.query(), dias=D.dias_hasta(p.fecha),
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
        en_juego=int((d["provincias"]["Cambia el bloque"] >= 30).sum()), enc=D.resumen_encuestas(p.fecha),
        p_bloque=probs["P(bloque de investidura 2023 ≥ 176)"], hace_un_mes=hace_un_mes)


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


def _mapa(d: dict, modo: str, partido: str | None) -> dict:
    prov = d["provincias"].set_index("Provincia")
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    hover = pd.Series({
        x: (f"<b>{x}</b> · {prov.at[x, 'Escaños']} escaños<br>"
            + " · ".join(f"{nombre(k)} {num(v)} %" for k, v in vp.loc[x].nlargest(3).items())
            + f"<br>Reparto más probable: {prov.at[x, 'Reparto']} ({prov.at[x, 'Reparto más probable']} %)"
            + f"<br>Escaño en juego: {prov.at[x, 'Cambia el bloque']} %")
        for x in prov.index})
    if modo == "juego":
        fig = G.mapa_valor(prov["Cambia el bloque"].astype(float), hover, "BRONCE", "En juego", desde_cero=True)
        return {"fig": figura(fig), "leyenda": [],
                "nota": "Porcentaje de simulaciones en que PP + Vox + UPN + SALF sacan en la provincia un número de "
                        "escaños distinto del más habitual: cuanto más oscuro, más baila el último escaño entre bloques."}
    if modo == "partido":
        partido = partido if partido in partidos_mapa(d) else partidos_mapa(d)[0]
        fig = G.mapa_valor(vp[partido], hover, partido, f"Voto de {nombre(partido)}")
        return {"fig": figura(fig), "leyenda": [],
                "nota": f"Voto estimado de {nombre(partido)} en cada provincia (proyección central). La escala cubre "
                        "sólo el rango de este partido para que se vean las diferencias."}
    ganador = vp.idxmax(axis=1)
    cuenta = ganador.value_counts()
    return {"fig": figura(G.mapa_ganador(ganador, hover)),
            "leyenda": [{"nombre": nombre(x), "color": color(x), "n": int(n)} for x, n in cuenta.items()],
            "nota": "Partido con más voto estimado en cada provincia, según la proyección central (sin simular). "
                    "Ceuta y Melilla aparecen como puntos."}


def partidos_mapa(d: dict) -> list[str]:
    vp = d["voto_prov"]
    return [x for x in orden_voto(d) if x in vp.columns and x in RAMPA_CLARO]


def provincias(request):
    p = params(request)
    if r := esperar(request, p, "Provincias"):
        return r
    d = D.correr(p.escenario())
    prov = d["provincias"].set_index("Provincia")
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    top = prov["Cambia el bloque"].nlargest(12) / 100
    top.index = [f"{x} ({prov.at[x, 'Escaños']})" for x in top.index]
    filas = [{"provincia": x, "ccaa": r_["CCAA"], "escanos": int(r_["Escaños"]), "reparto": r_["Reparto"],
              "frecuencia": int(r_["Reparto más probable"]), "juego": int(r_["Cambia el bloque"]),
              "primero": vp.loc[x].idxmax()}
             for x, r_ in prov.iterrows()]
    vpt = vp.loc[:, vp.max() >= 1]
    vpt = vpt[sorted(vpt.columns, key=lambda c: -vpt[c].sum())]
    return pagina(request, "provincias.html", p, mapa=_mapa(d, "ganador", None), partidos=partidos_mapa(d),
                  fig_top=figura(G.barras_prob(top, alto_fila=30)), filas=filas, ccaa=sorted(prov.CCAA.unique()),
                  voto_cols=list(vpt.columns), voto_filas=list(vpt.sort_index().iterrows()))


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
    return FileResponse(PLOTLY_JS, media_type="text/javascript", headers={"Cache-Control": "max-age=86400"})


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


@contextlib.asynccontextmanager
async def arranque(app):
    D.iniciar()
    yield


app = Starlette(
    routes=[
        Route("/", inicio), Route("/escanos", escanos), Route("/mayorias", mayorias),
        Route("/provincias", provincias), Route("/encuestas", encuestas), Route("/evolucion", evolucion),
        Route("/participacion", participacion), Route("/metodologia", metodologia),
        Route("/api/mapa", api_mapa), Route("/api/encuestas", api_encuestas), Route("/api/casas", api_casas),
        Route("/api/calcular", api_calcular, methods=["POST"]),
        Route("/descargar/simulaciones.csv", descargar),
        Route("/estatico/plotly.min.js", plotly_js),
        Mount("/estatico", StaticFiles(directory=ESTATICO), name="estatico"),
    ],
    exception_handlers={HTTPException: no_encontrado, Exception: fallo},
    lifespan=arranque,
)
