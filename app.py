"""
Aplicación del modelo electoral (Streamlit).

Arranque:  python lanzar.py      (o F5 en VS Code)
       o:  streamlit run app.py

Los escenarios se guardan en disco al calcularse (interfaz/calculo.py); `python -m scripts.precalcular`
calcula de antemano la rejilla habitual para que moverse por los controles sea instantáneo.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)                      # los módulos del modelo usan rutas relativas a la raíz
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from interfaz import graficos as G  # noqa: E402
from interfaz.calculo import (BARRIDO, N_SIM, N_SIM_BARRIDO, SEMILLA, en_disco, escenario,  # noqa: E402
                              fechas_semanales, huella_modelo, limpiar_cache)
from interfaz.estilo import CSS, RAMPA_CLARO, color, nombre, num, orden, pct  # noqa: E402
from motor.agregador import agregar, preparar  # noqa: E402
from motor.pipeline import (DERECHA, ELECCION, PART_BASE, REPARTOS, SOCIOS_2023, Escenario,  # noqa: E402
                            piezas_centrales)
from motor.proyeccion import FECHA  # noqa: E402

st.set_page_config(page_title="Congreso 29-N", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
ULTIMA_ENCUESTA = date.fromisoformat(FECHA)
FECHAS = fechas_semanales()
DIAS_CALIBRADOS = 48   # los errores del Monte Carlo están medidos hasta 48 días antes de votar
NOMBRES_REPARTO = {
    "historico": "Como en 2015–2023",
    "simetrico": "Simétrico, como el 10N",
    "muy_asimetrico": "Muy asimétrico",
}
DETALLE_REPARTO = {
    "historico": "57 a la izquierda, 18 a la derecha y 25 al resto",
    "simetrico": "49 a la izquierda, 45 a la derecha y 6 al resto",
    "muy_asimetrico": "80 a la izquierda, 5 a la derecha y 15 al resto",
}
NOMBRES_CAND = {"separados": "Sumar y Podemos por separado", "frente_amplio": "Frente Amplio"}
ATAJOS = {
    "PP + Vox": ["PP", "VOX"],
    "Toda la derecha": DERECHA,
    "Bloque de 2023": SOCIOS_2023 + ["FRENTE_AMPLIO"],
    "PSOE y su izquierda": ["PSOE", "SUMAR", "PODEMOS", "FRENTE_AMPLIO"],
}
ESCENARIOS = {   # clave de Resultado.probs -> texto de la gráfica
    "P(PP + Vox ≥ 176)": "PP y Vox suman 176",
    "P(PP + Vox + UPN + SALF ≥ 176)": "PP, Vox, UPN y SALF suman 176",
    "P(PP solo ≥ 176)": "El PP solo llega a 176",
    "P(bloque de investidura 2023 ≥ 176)": "El bloque de 2023 suma 176",
    "P(ningún bloque llega)": "Ningún bloque llega a 176",
    "P(PP primero)": "El PP queda primero",
    "P(PSOE primero)": "El PSOE queda primero",
}


def fecha_larga(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} de {MESES[d.month - 1]}"


def fecha_corta(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {MESES[d.month - 1][:3]}"


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------ cálculo (memoria + disco)

VERSION = huella_modelo()


@st.cache_resource
def _limpiar_cache_vieja(version: str) -> None:
    limpiar_cache(version)


_limpiar_cache_vieja(VERSION)


@st.cache_data(show_spinner=False, max_entries=24)
def centrales(fecha: str, participacion: float, reparto: str, version: str) -> dict:
    return piezas_centrales(fecha, participacion, reparto)


@st.cache_data(show_spinner=False, max_entries=64)
def correr(fecha: str, candidaturas: str, participacion: float, reparto: str, n_sim: int, semilla: int,
           version: str) -> dict:
    esc = Escenario(fecha=fecha, candidaturas=candidaturas, participacion=participacion,
                    reparto=reparto, n_sim=n_sim, semilla=semilla)
    return escenario(esc, version, centrales=lambda f, pa, re: centrales(f, pa, re, version))


@st.cache_data(show_spinner=False, max_entries=6)
def agregador(fecha: str, version: str) -> tuple[pd.DataFrame, dict]:
    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    enc = preparar(nac[nac.ciclo == "2026"], fecha)
    series = {p: agregar(enc, p, fecha) for p in ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "SALF"]}
    return enc, series


@st.cache_data(show_spinner=False, max_entries=6)
def barrido_participacion(fecha: str, reparto: str, semilla: int, version: str) -> pd.DataFrame:
    filas = []
    for part in BARRIDO:
        for cand in ["separados", "frente_amplio"]:
            d = correr(fecha, cand, part, reparto, N_SIM_BARRIDO, semilla, version)
            filas.append({"participacion": part, "candidaturas": NOMBRES_CAND[cand],
                          "P(mayoría PP + Vox)": d["probs"]["P(PP + Vox ≥ 176)"],
                          "P(investidura tipo 2023)": d["probs"]["P(bloque de investidura 2023 ≥ 176)"],
                          "P(PSOE primero)": d["probs"]["P(PSOE primero)"],
                          "PP + Vox (mediana)": float(d["ppvox"].median())})
    return pd.DataFrame(filas)


@st.cache_data(show_spinner=False, max_entries=8)
def evolucion(candidaturas: str, participacion: float, reparto: str, n_sim: int, semilla: int,
              version: str) -> dict:
    reps, probs, medianas = {}, {}, {}
    for f in FECHAS:
        d = correr(f, candidaturas, participacion, reparto, n_sim, semilla, version)
        reps[f] = G.reparto_representativo(d["sim"])
        probs[f] = d["probs"]
        medianas[f] = d["sim"].median()
    return {"reps": reps, "probs": pd.DataFrame(probs).T, "medianas": pd.DataFrame(medianas).T}


# ------------------------------------------------------------------ panel lateral (se aplica al momento)

with st.sidebar:
    st.markdown("## Escenario")
    fecha = st.select_slider("Encuestas hasta", FECHAS, value=FECHAS[-1], format_func=fecha_corta,
                             help="Corte semanal: el modelo solo usa encuestas con trabajo de campo terminado ese "
                                  "día o antes.")
    candidaturas = st.radio("Candidaturas", list(NOMBRES_CAND), format_func=NOMBRES_CAND.get,
                            help="Las listas se cierran el 26 de octubre.")
    participacion = st.slider("Participación", 60, 76, round(100 * PART_BASE), format="%d %%",
                              help="Las encuestas suponen de media un 65 %. Por encima, se suman votantes con el "
                                   "reparto elegido.")
    reparto = st.selectbox("Reparto de los votantes adicionales", list(REPARTOS), format_func=NOMBRES_REPARTO.get,
                           disabled=participacion == round(100 * PART_BASE),
                           help="De cada 100 votos extra (no influye con la participación del 65 %). " + " | ".join(
                               f"{NOMBRES_REPARTO[k]}: {v}" for k, v in DETALLE_REPARTO.items()))
    with st.expander("Simulación"):
        n_sim = st.select_slider("Simulaciones", [2000, 5000, 10000], value=N_SIM, format_func=miles)
        semilla = st.number_input("Semilla", value=SEMILLA, min_value=0, step=1,
                                  help="Misma semilla y mismo escenario dan exactamente el mismo resultado.")
    st.markdown('<p class="nota">Los cambios se aplican al momento. Los escenarios ya calculados se abren al '
                'instante; los nuevos tardan unos segundos la primera vez.</p>'
                '<p class="nota">Modelo propio con encuestas publicadas, resultados oficiales 2015–2023 '
                'y encuestas autonómicas. Uso personal.</p>', unsafe_allow_html=True)

p = dict(fecha=fecha, candidaturas=candidaturas, participacion=participacion / 100, reparto=reparto,
         n_sim=int(n_sim), semilla=int(semilla))
esc_actual = Escenario(**p)
try:
    if en_disco(esc_actual, VERSION):
        d = correr(**p, version=VERSION)
    else:
        with st.spinner(f"Simulando {miles(p['n_sim'])} elecciones por primera vez…"):
            d = correr(**p, version=VERSION)
except Exception as exc:  # noqa: BLE001
    st.error(f"El modelo no ha podido calcular este escenario: {exc}")
    st.stop()

sim, tabla, probs = d["sim"], d["tabla"], d["probs"]
nac_orden = list(tabla.sort_values("voto_%", ascending=False).index)   # partidos por voto nacional

# ------------------------------------------------------------------ cabecera y resultado principal

partes = [f"Encuestas hasta el {fecha_larga(p['fecha'])}, a {d['dias']} días de votar",
          NOMBRES_CAND[p["candidaturas"]],
          f"participación del {round(100 * p['participacion'])} %",
          f"{miles(p['n_sim'])} simulaciones"]
st.markdown(f'<div class="cabecera"><h1>Congreso, 29 de noviembre</h1><p>{", ".join(partes)}.</p></div>',
            unsafe_allow_html=True)
if d["dias"] > DIAS_CALIBRADOS:
    st.warning(f"A {d['dias']} días de votar el error de las encuestas se extrapola: sólo está medido hasta "
               f"{DIAS_CALIBRADOS} días antes. Los rangos de este escenario son orientativos.")

izq, der = st.columns([1.65, 1], gap="large")
with izq:
    st.plotly_chart(G.hemiciclo(sim), config=G.CONFIG, width="stretch")
    st.markdown(G.leyenda_html(sim, tabla["voto_%"]), unsafe_allow_html=True)
    st.markdown('<p class="nota">Escaños: reparto medio de las simulaciones, redondeado a 350; detrás, el % de voto '
                'nacional estimado. La línea de puntos deja 175 '
                'escaños a cada lado: el bloque que la cruza tiene mayoría. Pasa el ratón por los escaños para ver la '
                'mediana y el rango de cada partido.</p>',
                unsafe_allow_html=True)
with der:
    p_may = probs["P(PP + Vox ≥ 176)"]
    st.markdown(f'<div class="cifra-principal">{pct(p_may)}</div>'
                f'<div class="cifra-texto">de las simulaciones dan al menos 176 escaños a PP y Vox</div>',
                unsafe_allow_html=True)
    filas = [
        ("El bloque de la investidura de 2023 llega a 176", pct(probs["P(bloque de investidura 2023 ≥ 176)"])),
        ("El PSOE queda primero", pct(probs["P(PSOE primero)"])),
        ("Ningún bloque llega a 176", pct(probs["P(ningún bloque llega)"])),
        ("Escaños de PP y Vox, mediana", f"{d['ppvox'].median():.0f}"),
    ]
    st.markdown("".join(f'<div class="fila-prob"><span>{a}</span><span>{b}</span></div>' for a, b in filas),
                unsafe_allow_html=True)


# ------------------------------------------------------------------ secciones que se recargan solas
# (st.fragment: tocar un control de estas secciones no vuelve a dibujar el resto de la página)

@st.fragment
def seccion_calculadora(sim: pd.DataFrame, probs: pd.Series) -> None:
    st.markdown("#### Calculadora de mayorías")
    opciones = [x for x in sorted(sim.columns, key=orden) if sim[x].mean() >= 0.5]
    if "pacto" not in st.session_state:
        st.session_state.pacto = ["PP", "VOX"]
    # Al cambiar de candidaturas, Sumar + Podemos <-> Frente Amplio sin perder la coalición elegida
    traduccion = {"SUMAR": ["FRENTE_AMPLIO"], "PODEMOS": ["FRENTE_AMPLIO"], "FRENTE_AMPLIO": ["SUMAR", "PODEMOS"]}
    pacto = [y for x in st.session_state.pacto for y in ([x] if x in opciones else traduccion.get(x, []))]
    st.session_state.pacto = [x for x in dict.fromkeys(pacto) if x in opciones]

    def _aplicar_atajo():
        if st.session_state.atajo:
            st.session_state.pacto = [x for x in ATAJOS[st.session_state.atajo] if x in opciones]

    def _soltar_atajo():
        st.session_state.atajo = None

    st.segmented_control("Atajos", list(ATAJOS), key="atajo", on_change=_aplicar_atajo)
    elegidos = st.pills("Partidos que suman", opciones, selection_mode="multi", format_func=nombre, key="pacto",
                        on_change=_soltar_atajo)
    if elegidos:
        suma = sim[elegidos].sum(axis=1)
        p_pacto = float((suma >= 176).mean())
        a, b = st.columns([1, 1.6], gap="large")
        with a:
            nombres = [nombre(x) for x in elegidos]
            quienes = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
            st.markdown(f'<div class="cifra-principal">{pct(p_pacto)}</div>'
                        f'<div class="cifra-texto">de las simulaciones dan 176 escaños o más a {quienes}</div>',
                        unsafe_allow_html=True)
            filas = [("Escaños, mediana", f"{suma.median():.0f}"),
                     ("80 % de las simulaciones", f"{suma.quantile(0.1):.0f}–{suma.quantile(0.9):.0f}"),
                     ("Les faltan para 176 (mediana)", f"{max(176 - suma.median(), 0):.0f}")]
            st.markdown("".join(f'<div class="fila-prob"><span>{x}</span><span>{y}</span></div>' for x, y in filas),
                        unsafe_allow_html=True)
        with b:
            st.plotly_chart(G.histograma_mayoria(suma, "Coalición"), config=G.CONFIG, width="stretch")
    else:
        st.info("Elige al menos un partido.")

    st.markdown("#### Escenarios")
    st.plotly_chart(G.barras_prob(probs.rename(ESCENARIOS).reindex(list(ESCENARIOS.values()))), config=G.CONFIG,
                    width="stretch")
    st.markdown('<p class="nota">Las frecuencias son condicionales a los supuestos del modelo; no son una '
                'probabilidad electoral calibrada con una serie histórica larga. El bloque de 2023 suma PSOE, '
                'Sumar, Podemos (o Frente Amplio), ERC, Junts, '
                'EH Bildu, PNV, BNG, Coalición Canaria y Adelante. Que llegue a 176 no garantiza la investidura: '
                'harían falta todos los votos, Junts incluido.</p>', unsafe_allow_html=True)


@st.fragment
def seccion_mapa(prov: pd.DataFrame, vp: pd.DataFrame, nac_orden: list[str]) -> None:
    hover = pd.Series({
        x: (f"<b>{x}</b> · {prov.at[x, 'Escaños']} escaños<br>"
            + " · ".join(f"{nombre(k)} {num(v)} %" for k, v in vp.loc[x].nlargest(3).items())
            + f"<br>Reparto más probable: {prov.at[x, 'Reparto']} ({prov.at[x, 'Reparto más probable']} %)"
            + f"<br>Escaño en juego: {prov.at[x, 'Cambia el bloque']} %")
        for x in prov.index})
    modos = ["Partido más votado", "Escaño en juego", "Voto de un partido"]
    modo = st.segmented_control("Qué mostrar", modos, default=modos[0], key="modo_mapa") or modos[0]
    if modo == "Partido más votado":
        ganador = vp.idxmax(axis=1)
        st.plotly_chart(G.mapa_ganador(ganador, hover), config=G.CONFIG, width="stretch")
        cuenta = ganador.value_counts()
        st.markdown('<div class="leyenda">' + "".join(
            f'<div><i style="background:{color(x)}"></i>{nombre(x)} <b>{n}</b> provincias</div>'
            for x, n in cuenta.items()) + "</div>", unsafe_allow_html=True)
        st.markdown('<p class="nota">Partido con más voto estimado en cada provincia, según la proyección central '
                    '(sin simular). Ceuta y Melilla aparecen como puntos.</p>', unsafe_allow_html=True)
    elif modo == "Escaño en juego":
        st.plotly_chart(G.mapa_valor(prov["Cambia el bloque"].astype(float), hover, "BRONCE", "En juego",
                                     desde_cero=True), config=G.CONFIG, width="stretch")
        st.markdown('<p class="nota">Porcentaje de simulaciones en que PP + Vox + UPN + SALF sacan en la provincia un '
                    'número de escaños distinto del más habitual: cuanto más oscuro, más baila el último escaño '
                    'entre bloques.</p>', unsafe_allow_html=True)
    else:
        estatales = [x for x in nac_orden if x in vp.columns and x in RAMPA_CLARO]
        partido = st.pills("Partido", estatales, default=estatales[0], format_func=nombre,
                           key="partido_mapa") or estatales[0]
        st.plotly_chart(G.mapa_valor(vp[partido], hover, partido, f"Voto de {nombre(partido)}"), config=G.CONFIG,
                        width="stretch")
        st.markdown(f'<p class="nota">Voto estimado de {nombre(partido)} en cada provincia (proyección central). '
                    'La escala cubre sólo el rango de este partido para que se vean las diferencias.</p>',
                    unsafe_allow_html=True)


@st.fragment
def seccion_encuestas(fecha: str, diag: pd.DataFrame) -> None:
    with st.spinner("Calculando la media de encuestas…"):
        enc, series = agregador(fecha, VERSION)
    elegidos = st.multiselect("Partidos", list(series), default=["PP", "PSOE", "VOX", "SUMAR"], format_func=nombre)
    desde = st.select_slider("Desde", ["2025-01-01", "2025-07-01", "2026-01-01", "2026-06-01"], value="2026-01-01",
                             format_func=lambda s: f"{MESES[int(s[5:7]) - 1]} de {s[:4]}")
    if elegidos:
        st.plotly_chart(G.serie_encuestas({k: series[k] for k in elegidos}, enc, desde), config=G.CONFIG,
                        width="stretch")
    st.markdown(f'<p class="nota">{len(enc)} encuestas de {enc.casa.nunique()} casas. La línea es la media del '
                'modelo, ya corregida por el sesgo de cada casa; los puntos, las encuestas tal como se publicaron. '
                'No incluye encuestas encargadas por partidos.</p>', unsafe_allow_html=True)
    st.markdown("#### Sesgo de cada casa")
    pt = st.selectbox("Partido", list(series), format_func=nombre, key="casa_partido")
    st.plotly_chart(G.efectos_casa(series[pt].casas, pt), config=G.CONFIG, width="stretch")
    st.markdown('<p class="nota">Diferencia media de cada casa frente al conjunto de encuestadoras (casas con 5 o más '
                'encuestas). Es un sesgo relativo, no un error frente al resultado real.</p>', unsafe_allow_html=True)
    with st.expander("Encuestas autonómicas usadas"):
        decimales = ["Swing nacional (%)", "Media de encuestas (%)", "Usado por el modelo (%)"]
        st.dataframe(diag.rename(columns={
            "ccaa": "Comunidad", "partido": "Partido", "swing_nacional": "Swing nacional (%)",
            "encuestas": "Encuestas", "media_encuestas": "Media de encuestas (%)", "objetivo": "Usado por el modelo (%)"})
            .style.format(num, subset=decimales), hide_index=True, width="stretch")


def seccion_evolucion(p: dict) -> None:
    pendientes = [f for f in FECHAS if not en_disco(Escenario(**{**p, "fecha": f}), VERSION)]
    clave = f"evolucion_{p['candidaturas']}_{p['participacion']}_{p['reparto']}_{p['n_sim']}_{p['semilla']}"
    if pendientes and not st.session_state.get(clave):
        st.markdown(f"Con este escenario faltan por calcular {len(pendientes)} de las {len(FECHAS)} semanas "
                    f"(unos {5 * len(pendientes)} segundos). Con los valores por defecto ya están calculadas "
                    "(`python -m scripts.precalcular`).")
        if st.button("Calcular la evolución"):
            st.session_state[clave] = True
            st.rerun()
        return
    if pendientes:
        barra = st.progress(0.0, text="Calculando semanas…")
        for i, f in enumerate(pendientes):
            barra.progress(i / len(pendientes), text=f"Calculando el {fecha_larga(f)}…")
            correr(**{**p, "fecha": f}, version=VERSION)
        barra.empty()
    ev = evolucion(p["candidaturas"], p["participacion"], p["reparto"], p["n_sim"], p["semilla"], VERSION)
    pr = ev["probs"]
    titulos = {f: pct(pr.at[f, "P(PP + Vox ≥ 176)"]) for f in FECHAS}
    detalles = {f: f"PP y Vox llegan a 176 · {fecha_larga(f)}" for f in FECHAS}
    etiquetas = {f: fecha_corta(f) for f in FECHAS}
    st.plotly_chart(G.hemiciclo_animado(ev["reps"], titulos, detalles, etiquetas), config=G.CONFIG,
                    width="stretch")
    st.markdown('<p class="nota">Pulsa ▶ para ver cómo ha cambiado el reparto semana a semana, o arrastra el '
                'deslizador. En el centro, el porcentaje de simulaciones en que PP y Vox suman mayoría.</p>',
                unsafe_allow_html=True)

    a, b = st.columns(2, gap="large")
    idx = pd.to_datetime(pr.index)
    with a:
        st.markdown("#### Probabilidad de mayoría")
        bloques = pd.DataFrame({"PP + Vox": 100 * pr["P(PP + Vox ≥ 176)"].to_numpy(),
                                "Bloque de 2023": 100 * pr["P(bloque de investidura 2023 ≥ 176)"].to_numpy()},
                               index=idx)
        st.plotly_chart(G.lineas_evolucion(bloques, {"PP + Vox": color("PP"), "Bloque de 2023": color("PSOE")},
                                           "% de simulaciones", sufijo=" %", rango_y=[0, 100], marca=p["fecha"],
                                           umbral=50), config=G.CONFIG, width="stretch")
    with b:
        st.markdown("#### Escaños, mediana")
        med = ev["medianas"]
        principales = [x for x in ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "FRENTE_AMPLIO"] if x in med]
        esc = pd.DataFrame({nombre(x): med[x].to_numpy() for x in principales}, index=idx)
        st.plotly_chart(G.lineas_evolucion(esc, {nombre(x): color(x) for x in principales}, "Escaños",
                                           marca=p["fecha"]), config=G.CONFIG, width="stretch")
    st.markdown('<p class="nota">Cada punto es el modelo completo corrido con las encuestas disponibles ese día. '
                'La línea vertical marca la fecha elegida en el panel. Antes de 48 días de la elección el error '
                'de las encuestas se extrapola, así que los rangos de esas semanas son más inciertos.</p>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------ pestañas

t_esc, t_evo, t_may, t_prov, t_enc, t_part, t_met = st.tabs(
    ["Voto y escaños", "Evolución", "Mayorías", "Provincias", "Encuestas", "Participación", "Cómo funciona"])

with t_esc:
    voto = d["voto"]
    # mismos partidos y mismo orden (por voto) en las dos gráficas, para leerlas fila a fila
    visibles = [x for x in nac_orden if tabla.at[x, "media"] >= 0.5 or voto.at[x, "mediana"] >= 1]
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("#### Voto nacional")
        st.plotly_chart(G.rangos(voto, visibles, eje="% de votos válidos", dec=1, sufijo=" %"), config=G.CONFIG,
                        width="stretch")
    with b:
        st.markdown("#### Escaños")
        st.plotly_chart(G.rangos(tabla, visibles), config=G.CONFIG, width="stretch")
    st.markdown('<p class="nota">Barra: el 80 % central de las simulaciones. Línea fina: el 95 %. '
                'Círculo y cifra: la mediana. El voto incluye el error de las encuestas medido en 2015–2023, '
                'por eso el rango es mucho más ancho que la diferencia entre encuestas.</p>', unsafe_allow_html=True)
    with st.expander("Ver los datos"):
        vis = tabla[tabla.media >= 0.05].rename(index=nombre)[["voto_%", "p10", "mediana", "p90", "media"]]
        vis.columns = ["Voto estimado (%)", "Escaños, percentil 10", "Mediana", "Percentil 90", "Media"]
        st.dataframe(vis.style.format(num, subset=["Voto estimado (%)", "Media"], na_rep="")
                     .format("{:.0f}", subset=["Escaños, percentil 10", "Mediana", "Percentil 90"]),
                     width="stretch")
    st.download_button("Descargar las simulaciones (CSV)", sim.to_csv(index=False).encode("utf-8"),
                       file_name=f"simulaciones_{p['fecha']}_{p['candidaturas']}.csv", mime="text/csv")

with t_evo:
    seccion_evolucion(p)

with t_may:
    seccion_calculadora(sim, probs)

with t_prov:
    prov = d["provincias"].set_index("Provincia")
    vp = d["voto_prov"].drop(columns=["BLANCO", "OTROS"], errors="ignore")
    seccion_mapa(prov, vp, nac_orden)

    st.markdown("#### Dónde se decide el último escaño")
    top = prov["Cambia el bloque"].nlargest(12) / 100
    top.index = [f"{x} ({prov.at[x, 'Escaños']})" for x in top.index]
    st.plotly_chart(G.barras_prob(top, alto_fila=30), config=G.CONFIG, width="stretch")
    st.markdown('<p class="nota">Las doce provincias donde más cambia el reparto entre bloques. Entre paréntesis, '
                'los escaños que reparte: las que reparten muchos cambian más a menudo, porque cualquier '
                'movimiento pequeño mueve alguno de sus escaños.</p>', unsafe_allow_html=True)
    with st.expander("Ver la tabla de provincias"):
        ccaa = st.selectbox("Comunidad", ["Todas"] + sorted(prov.CCAA.unique()))
        vista = prov if ccaa == "Todas" else prov[prov.CCAA == ccaa]
        st.dataframe(
            vista.drop(columns="CCAA").sort_values("Escaños", ascending=False), width="stretch",
            column_config={
                "Reparto": st.column_config.TextColumn("Reparto más probable", width="large"),
                "Reparto más probable": st.column_config.ProgressColumn(
                    "Frecuencia de ese reparto", min_value=0, max_value=100, format="%d %%"),
                "Cambia el bloque": st.column_config.ProgressColumn(
                    "Escaño en juego", min_value=0, max_value=100, format="%d %%"),
            })
        vpt = vp.loc[:, vp.max() >= 1].rename(columns=nombre)
        vpt = vpt[sorted(vpt.columns, key=lambda c: -vpt[c].sum())]
        st.markdown("Voto estimado por provincia (%)")
        st.dataframe(vpt.style.format(num), width="stretch")

with t_enc:
    seccion_encuestas(p["fecha"], d["diag"])

with t_part:
    st.markdown("Recalcula el escenario para participaciones del 62 % al 75 %, con el reparto de votantes "
                f"adicionales elegido en el panel ({NOMBRES_REPARTO[p['reparto']].lower()}: de cada 100 votos extra, "
                f"{DETALLE_REPARTO[p['reparto']]}). "
                f"Usa {miles(N_SIM_BARRIDO)} simulaciones por punto.")
    listos = all(en_disco(Escenario(p["fecha"], c, x, p["reparto"], N_SIM_BARRIDO, p["semilla"]), VERSION)
                 for x in BARRIDO for c in NOMBRES_CAND)
    clave = f"barrido_{p['fecha']}_{p['reparto']}_{p['semilla']}_{VERSION}"
    if listos or clave in st.session_state or st.button("Calcular el barrido de participación"):
        with st.spinner("Calculando 14 escenarios…"):
            df = barrido_participacion(p["fecha"], p["reparto"], p["semilla"], VERSION)
        st.session_state[clave] = True
        a, b = st.columns(2, gap="large")
        with a:
            st.markdown("#### Mayoría de PP + Vox")
            st.plotly_chart(G.barrido(df, "P(mayoría PP + Vox)", "Probabilidad"), config=G.CONFIG,
                            width="stretch")
        with b:
            st.markdown("#### El PSOE queda primero")
            st.plotly_chart(G.barrido(df, "P(PSOE primero)", "Probabilidad"), config=G.CONFIG,
                            width="stretch")
        with st.expander("Ver los datos"):
            tb = df.copy()
            tb["participacion"] = (100 * tb.participacion).round().astype(int).astype(str) + " %"
            st.dataframe(tb.rename(columns={"participacion": "Participación", "candidaturas": "Candidaturas"})
                         .style.format(lambda v: pct(v), subset=["P(mayoría PP + Vox)", "P(investidura tipo 2023)",
                                                                 "P(PSOE primero)"])
                         .format("{:.0f}", subset=["PP + Vox (mediana)"]),
                         hide_index=True, width="stretch")

with t_met:
    st.markdown(f"""
#### Qué hace el modelo

1. **Media de encuestas.** Junta todas las encuestas nacionales publicadas, corrige el sesgo propio de cada
   casa y sigue la tendencia día a día. Excluye las encuestas encargadas por partidos.
2. **Comunidades autónomas.** Donde hay encuestas autonómicas recientes (CEO, Sondaxe, GAD3…), corrige el
   reparto territorial sin cambiar el total nacional.
3. **Provincias.** Lleva el voto a cada provincia a partir del resultado de 2023, con un ajuste logístico.
4. **Simulación.** Repite la elección miles de veces con los errores medidos en cinco elecciones de 2015 a 2023:
   error de bloque (izquierda contra derecha), trasvases dentro de cada bloque, desviaciones por comunidad
   y por provincia. Cada simulación reparte los 350 escaños con D'Hondt y el umbral del 3 %.

#### Cuánto se equivoca

- Según la elección, la media de encuestas falló entre 0,75 y 2,02 puntos por partido la víspera. Al dejar fuera
  una elección cada vez durante la calibración, el error medio en la elección no vista fue 1,92 puntos.
- Con el resultado por CCAA perfecto y las candidaturas reales conocidas, el paso a provincias coloca mal unos
  7 escaños por elección; con solo el resultado nacional perfecto, unos 18.
- Probado fuera de muestra en 2016, abril y noviembre de 2019 y 2023 (cada elección con los errores calibrados
  sin ella, a 30, 14 y 1 días): el escaño real de los partidos estatales cayó dentro del intervalo del 80 % en el
  76 % de los casos y dentro del del 95 % en el 93 %. El error medio fue de 8 escaños por partido, frente a 22 si
  se repite la elección anterior.
- Fallos más claros: la subida de Vox en noviembre de 2019 (52 escaños; el modelo daba 24–32 a un mes y a dos
  semanas), y la sobreestimación sistemática del espacio de Podemos (unos 7 escaños de media).
- A 30 días del 23J el modelo daba un 78 % de mayoría a PP, Vox y UPN, que no se produjo (sacaron 171).

#### Límites

- La calibración nacional usa cinco elecciones: es una mejora grande, pero aún es una serie histórica corta.
- El backtest cubre cuatro elecciones (2015 no tiene elección base): las frecuencias siguen siendo escenarios
  condicionados al modelo, no probabilidades validadas en una serie larga.
- Las candidaturas que no se presentaron en la elección anterior (Teruel Existe, el PRC o Navarra Suma en 2019)
  quedaron fuera de sus intervalos en el backtest: el modelo no sabe proyectarlas. En 2026 afecta a SALF y Adelante.
- El error de las encuestas está medido hasta {DIAS_CALIBRADOS} días antes de votar; con fechas anteriores se
  extrapola y los rangos son sólo orientativos.
- Los partidos de una sola comunidad (ERC, Junts, PNV, EH Bildu, BNG, CC) no tienen error de campaña propio: su
  incertidumbre es la autonómica y la provincial, que no crece con los días que faltan. Probablemente se queda corta.
- La participación se modela como un supuesto, no se estima: las encuestas ya incluyen la suya.
- El escenario de Frente Amplio supone que la lista conjunta conserva todos los votos de Sumar y Podemos.
- El voto residual «Otros» ayuda a calcular el umbral, pero no puede obtener escaños: una candidatura nueva
  con voto territorial concentrado debe incorporarse expresamente al modelo.
- Elección: {fecha_larga(ELECCION)} de 2026. Último dato de encuestas: {fecha_larga(ULTIMA_ENCUESTA)}.
""")
