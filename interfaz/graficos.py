"""Gráficos Plotly de la aplicación. Todos usan los tokens de interfaz/estilo.py."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from interfaz.estilo import (BRONCE, FONDO, FUENTE, FUENTE_CIFRAS, GRIS_DATO, PANEL, REGLA, TINTA,
                             TINTA_2, TINTA_3, color, mezcla, nombre, orden, pct, rampa)

CONFIG = {"displayModeBar": False, "responsive": True}


def _base(fig: go.Figure, alto: int, margen=None) -> go.Figure:
    fig.update_layout(
        height=alto, paper_bgcolor=FONDO, plot_bgcolor=FONDO, separators=",.",   # coma decimal, punto de miles
        font=dict(family=FUENTE, color=TINTA_2, size=13),
        margin=margen or dict(l=10, r=20, t=10, b=10),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=REGLA, font=dict(family=FUENTE, color=TINTA, size=13)),
        showlegend=False, barcornerradius=4,
    )
    fig.update_xaxes(gridcolor=REGLA, zeroline=False, linecolor=REGLA, tickfont=dict(color=TINTA_3))
    fig.update_yaxes(gridcolor=REGLA, zeroline=False, linecolor=REGLA, tickfont=dict(color=TINTA_3))
    return fig


# ---------------------------------------------------------------- hemiciclo

def reparto_representativo(sim: pd.DataFrame, total: int = 350) -> pd.Series:
    """Escaños medios redondeados por resto mayor para que sumen exactamente `total`."""
    media = sim.mean()
    base = np.floor(media).astype(int)
    faltan = total - int(base.sum())
    resto = (media - base).sort_values(ascending=False)
    base[resto.index[:faltan]] += 1
    return base[base > 0]


def _posiciones(total: int = 350, filas: int = 11) -> np.ndarray:
    radios = np.linspace(0.42, 1.0, filas)
    por_fila = np.round(total * radios / radios.sum()).astype(int)
    por_fila[-1] += total - por_fila.sum()
    pts = []
    for r, n in zip(radios, por_fila):
        ang = np.linspace(np.pi, 0, n)
        pts += [(r * np.cos(a), r * np.sin(a), a) for a in ang]
    pts = np.array(pts)
    return pts[np.lexsort((-np.hypot(pts[:, 0], pts[:, 1]), -pts[:, 2]))]


def hemiciclo(sim: pd.DataFrame, total: int = 350, unidad: str = "escaños", rotulo: str | None = None,
              umbral: int | None = None) -> go.Figure:
    """Reparto medio en semicírculo. La línea central deja total/2 a cada lado (mayoría: total/2 + 1).
    Con `umbral`, la línea marca en cambio cuántos escaños hacen falta contando desde la derecha
    (p. ej. los tres quintos del Senado)."""
    rep = reparto_representativo(sim, total)
    rep = rep.sort_index(key=lambda idx: idx.map(orden))
    pos = _posiciones(int(rep.sum()))
    q = sim.quantile([0.1, 0.5, 0.9])
    fig = go.Figure()
    i = 0
    for p, n in rep.items():
        xy = pos[i:i + n]
        i += n
        if len(sim) == 1:          # un solo reparto (simulador): sin mediana ni rangos
            texto = f"<b>{nombre(p)}</b><br>{n} {unidad}<extra></extra>"
        else:
            texto = (f"<b>{nombre(p)}</b><br>Mediana {q.at[0.5, p]:.0f} {unidad}"
                     f"<br>80 % de las simulaciones: {q.at[0.1, p]:.0f}–{q.at[0.9, p]:.0f}<extra></extra>")
        fig.add_trace(go.Scatter(
            x=xy[:, 0], y=xy[:, 1], mode="markers", name=nombre(p),
            marker=dict(size=11, color=color(p), line=dict(width=1.5, color=FONDO)), hovertemplate=texto,
        ))
    # total/2 escaños a cada lado del eje: quien lo cruza desde la derecha o la izquierda tiene mayoría
    ang = np.pi / 2
    if umbral is not None and 0 < umbral < len(pos):
        k = len(pos) - umbral                  # los `umbral` escaños de más a la derecha empiezan aquí
        ang = (pos[k - 1, 2] + pos[k, 2]) / 2
    cx, cy = np.cos(ang), np.sin(ang)
    fig.add_shape(type="line", x0=0.37 * cx, x1=1.05 * cx, y0=0.37 * cy, y1=1.05 * cy,
                  line=dict(color=TINTA, width=1.5, dash="dot"), layer="below")
    fig.add_annotation(x=1.05 * cx, y=1.05 * cy, text=rotulo or f"mayoría: {total // 2 + 1}", showarrow=False,
                       yanchor="bottom", font=dict(size=12, color=TINTA_2))
    fig.add_annotation(x=0, y=0.06, text=str(total), showarrow=False,
                       font=dict(family=FUENTE_CIFRAS, size=34, color=TINTA))
    fig.add_annotation(x=0, y=-0.07, text=unidad, showarrow=False, font=dict(size=13, color=TINTA_3))
    fig = _base(fig, 380, dict(l=0, r=0, t=0, b=0))
    fig.update_xaxes(visible=False, range=[-1.06, 1.06])
    fig.update_yaxes(visible=False, range=[-0.14, 1.13], scaleanchor="x", scaleratio=1)
    return fig


def leyenda_html(sim: pd.DataFrame, voto: pd.Series | None = None, total: int = 350) -> str:
    """Leyenda del hemiciclo: escaños del reparto representativo y, si se da, % de voto nacional."""
    rep = reparto_representativo(sim, total).sort_index(key=lambda idx: idx.map(orden))
    def extra(p):
        if voto is None or pd.isna(voto.get(p)):
            return ""
        return f' <span class="voto">· {voto[p]:.1f} %</span>'.replace(".", ",")
    items = "".join(f'<div><i style="background:{color(p)}"></i>{nombre(p)} <b>{n}</b>{extra(p)}</div>'
                    for p, n in rep.items())
    return f'<div class="leyenda">{items}</div>'


# ---------------------------------------------------------------- rangos (escaños o voto)

def rangos(tabla: pd.DataFrame, partidos: list[str], eje: str = "Escaños", dec: int = 0, sufijo: str = "") -> go.Figure:
    """Mediana, 80 % y 95 % de las simulaciones por partido. `partidos` va de arriba abajo.
    tabla: columnas p2.5, p10, mediana, p90, p97.5 (en escaños o en % de voto)."""
    t = tabla.reindex(partidos[::-1])           # Plotly pinta las categorías de abajo arriba
    etiquetas = [nombre(p) for p in t.index]
    f = f"{{:.{dec}f}}"
    fmt = lambda v: f.format(v).replace(".", ",") + sufijo   # noqa: E731
    fig = go.Figure()
    fig.add_trace(go.Scatter(  # 95 %
        x=np.ravel(np.column_stack([t["p2.5"], t["p97.5"], np.full(len(t), np.nan)])),
        y=np.ravel(np.column_stack([etiquetas, etiquetas, etiquetas])),
        mode="lines", line=dict(color=TINTA_3, width=1.5), hoverinfo="skip"))
    fig.add_trace(go.Bar(  # 80 %
        x=t.p90 - t.p10, base=t.p10, y=etiquetas, orientation="h", width=0.42,
        marker=dict(color=[color(p) for p in t.index], line=dict(width=0)),
        customdata=np.column_stack([[fmt(v) for v in t[c]] for c in ["p10", "p90", "p2.5", "p97.5", "mediana"]]),
        hovertemplate=("<b>%{y}</b><br>Mediana %{customdata[4]}"
                       "<br>80 %: %{customdata[0]} – %{customdata[1]}<br>95 %: %{customdata[2]} – %{customdata[3]}"
                       "<extra></extra>")))
    fig.add_trace(go.Scatter(  # mediana
        x=t.mediana, y=etiquetas, mode="markers",
        marker=dict(size=11, color=PANEL, line=dict(color=TINTA, width=2)), hoverinfo="skip"))
    # cifra de la mediana a la derecha del rango del 95 % (o del círculo, si el rango es más estrecho);
    # anotaciones con desplazamiento en píxeles para que no pisen el círculo ni se recorten
    for y, x, v in zip(etiquetas, np.maximum(t["p97.5"], t.mediana), t.mediana):
        fig.add_annotation(x=x, y=y, text=fmt(v), showarrow=False, xanchor="left", xshift=9,
                           font=dict(family=FUENTE_CIFRAS, size=14, color=TINTA))
    fig = _base(fig, 60 + 38 * len(t), dict(l=10, r=70, t=10, b=10))
    fig.update_xaxes(title=dict(text=eje, font=dict(color=TINTA_3)), rangemode="tozero", ticksuffix=sufijo)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TINTA, size=13), ticksuffix="  ")
    return fig


# ---------------------------------------------------------------- distribución de una suma de escaños

def histograma_mayoria(serie: pd.Series, titulo_hover: str) -> go.Figure:
    frec = serie.value_counts(normalize=True).sort_index()
    x = frec.index.to_numpy()
    llega = x >= 176
    fig = go.Figure()
    for mask, col, nom in [(~llega, GRIS_DATO, "Por debajo de 176"), (llega, BRONCE, "176 o más")]:
        fig.add_trace(go.Bar(x=x[mask], y=100 * frec.to_numpy()[mask], marker=dict(color=col, line=dict(width=0)),
                             name=nom, hovertemplate=f"{titulo_hover}: %{{x}} escaños<br>%{{y:.1f}} % de las simulaciones<extra></extra>"))
    fig.add_vline(x=175.5, line=dict(color=TINTA, width=1.5, dash="dot"))
    fig.add_annotation(x=175.5, y=0.98, yref="paper", text="176", showarrow=False,
                       xanchor="right", yanchor="top", xshift=-6, font=dict(color=TINTA, size=12, family=FUENTE_CIFRAS))
    fig = _base(fig, 320, dict(l=10, r=20, t=40, b=10))
    fig.update_layout(bargap=0.08, showlegend=True,
                      legend=dict(orientation="h", y=1.12, x=0, font=dict(color=TINTA_2)))
    fig.update_xaxes(title=dict(text="Escaños", font=dict(color=TINTA_3)))
    fig.update_yaxes(title=dict(text="% de simulaciones", font=dict(color=TINTA_3)))
    return fig


# ---------------------------------------------------------------- encuestas

def serie_encuestas(series: dict, encuestas: pd.DataFrame, desde: str) -> go.Figure:
    fig = go.Figure()
    for p, r in series.items():
        s = r.serie[r.serie.fecha >= desde]
        e = encuestas[encuestas.t >= desde].dropna(subset=[p])
        fig.add_trace(go.Scatter(x=e.t, y=e[p], mode="markers", name=nombre(p),
                                 marker=dict(size=8, color=color(p), opacity=0.28, line=dict(width=0)),
                                 customdata=np.column_stack([e.casa]),
                                 hovertemplate=f"{nombre(p)}: %{{y:.1f}} %<br>%{{customdata[0]}}<br>%{{x|%d/%m/%Y}}<extra></extra>",
                                 showlegend=False))
        fig.add_trace(go.Scatter(x=s.fecha, y=s.media, mode="lines", name=nombre(p),
                                 line=dict(color=color(p), width=2.5),
                                 hovertemplate=f"<b>{nombre(p)}</b> %{{y:.1f}} % (media)<br>%{{x|%d/%m/%Y}}<extra></extra>"))
        ult = s.iloc[-1]
        fig.add_annotation(x=ult.fecha, y=ult.media, text=f"{nombre(p)} {ult.media:.1f}".replace(".", ","),
                           showarrow=False, xanchor="left", xshift=8, font=dict(color=TINTA, size=12))
    fig = _base(fig, 420, dict(l=10, r=110, t=10, b=10))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.12, x=0, font=dict(color=TINTA_2)),
                      hovermode="closest")
    fig.update_yaxes(title=dict(text="% del voto", font=dict(color=TINTA_3)))
    return fig


def efectos_casa(casas: pd.DataFrame, partido: str) -> go.Figure:
    c = casas[casas.n_encuestas >= 5].sort_values("efecto")
    fig = go.Figure(go.Bar(
        x=c.efecto, y=c.casa, orientation="h", marker=dict(color=color(partido), line=dict(width=0)),
        text=[f"{v:+.1f}".replace(".", ",") for v in c.efecto], textposition="outside",
        textfont=dict(color=TINTA, family=FUENTE_CIFRAS, size=12), cliponaxis=False,
        customdata=c.n_encuestas,
        hovertemplate="<b>%{y}</b><br>%{x:+.1f} puntos frente a la media<br>%{customdata} encuestas<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=TINTA_3, width=1))
    fig = _base(fig, 40 + 26 * len(c), dict(l=10, r=50, t=10, b=10))
    fig.update_xaxes(title=dict(text=f"Puntos de {nombre(partido)} por encima o por debajo de la media", font=dict(color=TINTA_3)))
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TINTA))
    return fig


# ---------------------------------------------------------------- barrido de participación

def barrido(df: pd.DataFrame, columna: str, titulo_y: str) -> go.Figure:
    fig = go.Figure()
    # trazo y marcador distintos además del color: las dos líneas se distinguen sin depender de él
    estilos = {"Candidaturas registradas": (dict(color=TINTA, dash="solid"), "circle"),
               "Hipótesis de lista única": (dict(color=color("FRENTE_AMPLIO"), dash="dash"), "diamond")}
    for cand, g in df.groupby("candidaturas", sort=False):
        g = g.sort_values("participacion")
        linea, simbolo = estilos.get(cand, ({}, "circle"))
        fig.add_trace(go.Scatter(
            x=100 * g.participacion, y=100 * g[columna], mode="lines+markers", name=cand,
            line=dict(width=2, **linea), marker=dict(size=8, symbol=simbolo),
            hovertemplate=f"{cand}<br>Participación %{{x:.0f}} %<br>{titulo_y}: %{{y:.0f}} %<extra></extra>"))
    fig.add_hline(y=50, line=dict(color=REGLA, width=1))
    fig = _base(fig, 340, dict(l=10, r=20, t=40, b=10))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0, font=dict(color=TINTA_2)))
    fig.update_xaxes(title=dict(text="Participación (%)", font=dict(color=TINTA_3)), dtick=2, range=[61.5, 75.5])
    fig.update_yaxes(title=dict(text=titulo_y + " (%)", font=dict(color=TINTA_3)), range=[0, 100])
    return fig


# ---------------------------------------------------------------- barras de probabilidad

def barras_prob(serie: pd.Series, alto_fila: int = 34) -> go.Figure:
    """Una sola serie: barras horizontales de un color, con la cifra al final de cada barra."""
    s = serie.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=100 * s.to_numpy(), y=list(s.index), orientation="h", width=0.6,
        marker=dict(color=TINTA_2, line=dict(width=0)),
        text=[pct(v) for v in s], textposition="outside", cliponaxis=False,
        textfont=dict(color=TINTA, family=FUENTE_CIFRAS, size=13),
        hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
    fig = _base(fig, 30 + alto_fila * len(s), dict(l=10, r=50, t=10, b=10))
    fig.update_xaxes(range=[0, 100], ticksuffix=" %", dtick=25, showgrid=True)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TINTA, size=13), ticksuffix="  ")
    return fig


# ---------------------------------------------------------------- mapa de provincias

RUTA_GEO = Path(__file__).resolve().parent.parent / "datos" / "geo" / "provincias.geojson"
SIN_SUPERFICIE = ["Ceuta", "Melilla"]          # demasiado pequeñas: se marcan con un punto rotulado
CANARIAS = ["Las Palmas", "Santa Cruz de Tenerife"]
# Canarias viene desplazada +6,5º lon/lat en el GeoJSON; aquí se mueve un poco más, al Atlántico al
# suroeste de Portugal, en un recuadro encajado en la esquina del marco (con Mercator, los lados salen rectos)
AJUSTE_CANARIAS = (-3.1, 0.5)
ENCUADRE = dict(lon=[-15.3, 4.6], lat=[34.15, 44.0])
RECUADRO_CANARIAS = dict(lon=[-15.3, -9.75], lat=[34.15, 36.8])     # comparte la esquina inferior izquierda
TIERRA_VECINA = "#E9EDF1"       # Portugal, Francia y el norte de África, sólo como contexto
TRAZO = 0.8                     # límites provinciales (color del fondo: separan sin pesar)
# Tramos de ventaja del primero sobre el segundo (puntos): de más clara a color pleno
TRAMOS_VENTAJA = [(5, 0.55), (15, 0.25)]            # por encima de 15 (o sin dato), color pleno


def _mover(coords, dlon: float, dlat: float):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0] + dlon, 4), round(coords[1] + dlat, 4)]
    return [_mover(c, dlon, dlat) for c in coords]


@lru_cache(maxsize=1)
def geo_provincias() -> dict:
    with open(RUTA_GEO, encoding="utf-8") as f:
        geo = json.load(f)
    for f in geo["features"]:
        if f["id"] in CANARIAS:
            f["geometry"]["coordinates"] = _mover(f["geometry"]["coordinates"], *AJUSTE_CANARIAS)
    return geo


@lru_cache(maxsize=1)
def _centros() -> pd.DataFrame:
    filas = {}
    for f in geo_provincias()["features"]:
        g = f["geometry"]
        anillos = [g["coordinates"][0]] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]
        pts = np.array([pt for a in anillos for pt in a])
        filas[f["id"]] = {"lon": pts[:, 0].mean(), "lat": pts[:, 1].mean()}
    return pd.DataFrame.from_dict(filas, orient="index")


def _mapa_base(fig: go.Figure, alto: int = 600) -> go.Figure:
    fig = _base(fig, alto, dict(l=2, r=2, t=2, b=2))     # unos píxeles para que el marco no quede recortado
    # Encuadre fijo (fitbounds se ajustaría a las provincias y cortaría la tierra vecina a ras de costa)
    fig.update_geos(visible=True, bgcolor=FONDO, projection_type="mercator",
                    showframe=True, framecolor=REGLA, framewidth=1,
                    lonaxis_range=ENCUADRE["lon"], lataxis_range=ENCUADRE["lat"], resolution=50,
                    showocean=False, showlakes=False, showrivers=False, showcoastlines=False,
                    showland=True, landcolor=TIERRA_VECINA, showcountries=True, countrycolor=FONDO, countrywidth=1)
    # lados superior y derecho del recuadro (los otros dos son el marco); con muchos puntos, para que
    # Plotly no los trace como arcos de círculo máximo
    lon, lat = RECUADRO_CANARIAS["lon"], RECUADRO_CANARIAS["lat"]
    arriba = np.linspace(lon[0], lon[1], 60)
    fig.add_trace(go.Scattergeo(lon=[*arriba, lon[1]], lat=[lat[1]] * len(arriba) + [lat[0]],
                                mode="lines", line=dict(color=REGLA, width=1), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scattergeo(lon=[lon[0] + 0.2], lat=[lat[1] - 0.15], mode="text", text=["Canarias"],
                                textposition="bottom right", textfont=dict(size=11, color=TINTA_3),
                                hoverinfo="skip", showlegend=False))
    return fig


def _coropletas(fig: go.Figure, locs: list[str], **kw) -> None:
    fig.add_trace(go.Choropleth(geojson=geo_provincias(), featureidkey="id", locations=locs,
                                marker=dict(line=dict(color=FONDO, width=TRAZO)),
                                hovertemplate="%{customdata}<extra></extra>", **kw))


def _puntos_pequenas(fig, provs, hover, **marker):
    """Ceuta y Melilla: un punto con el color que tendrían en el mapa y su nombre al lado."""
    c = _centros().reindex(provs)
    fig.add_trace(go.Scattergeo(lon=c.lon, lat=c.lat, mode="markers+text", showlegend=False, text=provs,
                                textposition=["middle left" if x == "Ceuta" else "middle right" for x in provs],
                                textfont=dict(size=11, color=TINTA_3),
                                marker=dict(size=11, line=dict(width=1.5, color=FONDO), **marker),
                                customdata=hover, hovertemplate="%{customdata}<extra></extra>"))


def tono_ventaja(p: str, ventaja: float) -> str:
    """Color del ganador aclarado según su ventaja (puntos) sobre el segundo."""
    t = next((t for tope, t in TRAMOS_VENTAJA if ventaja < tope), 0.0)
    return mezcla(color(p), PANEL, t)


def mapa_ganador(ganador: pd.Series, hover: pd.Series, ventaja: pd.Series | None = None) -> go.Figure:
    """Partido más votado en cada provincia. ganador/hover/ventaja: índice = provincia.
    Con `ventaja` (puntos sobre el segundo), el color se aclara donde la victoria es más ajustada."""
    ventaja = ventaja.reindex(ganador.index) if ventaja is not None else pd.Series(np.nan, index=ganador.index)
    colores = pd.Series([tono_ventaja(p, v) for p, v in zip(ganador, ventaja)], index=ganador.index)
    return mapa_colores(colores, hover)


def mapa_colores(colores: pd.Series, hover: pd.Series) -> go.Figure:
    """Mapa con un color ya decidido para cada provincia (índice = provincia)."""
    fig = go.Figure()
    for c in colores.unique():
        provs = [x for x in colores.index if colores[x] == c]
        if provs:
            _coropletas(fig, provs, z=np.ones(len(provs)), colorscale=[[0, c], [1, c]], showscale=False,
                        customdata=hover.reindex(provs).to_numpy())
    pequenas = [x for x in SIN_SUPERFICIE if x in colores.index]
    _puntos_pequenas(fig, pequenas, hover.reindex(pequenas), color=list(colores.reindex(pequenas)))
    return _mapa_base(fig)


def mapa_valor(valor: pd.Series, hover: pd.Series, escala: str, titulo: str, desde_cero: bool = False) -> go.Figure:
    """Mapa de un valor en % (p. ej. el voto de un partido) con una rampa de un solo tono.
    La escala cubre el rango observado (redondeado a 5) para que se distingan las provincias."""
    zmax = float(np.ceil(valor.max() / 5) * 5) or 5.0
    zmin = 0.0 if desde_cero else float(np.floor(valor.min() / 5) * 5)
    cs = rampa(escala)
    provs = list(valor.index)
    fig = go.Figure()
    _coropletas(fig, provs, z=valor.reindex(provs).to_numpy(), zmin=zmin, zmax=zmax, colorscale=cs,
                # horizontal, sobre el Atlántico (arriba a la izquierda), que siempre queda vacío
                colorbar=dict(title=dict(text=titulo, side="top", font=dict(color=TINTA_2, size=12)),
                              orientation="h", ticksuffix=" %", thickness=10, len=0.24, outlinewidth=0,
                              x=0.1, xanchor="left", y=0.93, yanchor="top", tickfont=dict(color=TINTA_3)),
                customdata=hover.reindex(provs).to_numpy())
    pequenas = [x for x in SIN_SUPERFICIE if x in valor.index]
    _puntos_pequenas(fig, pequenas, hover.reindex(pequenas), color=valor.reindex(pequenas),
                     colorscale=cs, cmin=zmin, cmax=zmax)
    return _mapa_base(fig)


# ---------------------------------------------------------------- evolución (animación)

def _trazas_hemiciclo(rep: pd.Series, partidos: list[str], pos: np.ndarray) -> list[go.Scatter]:
    """Una traza por partido (aunque tenga 0 escaños): las animaciones necesitan las mismas trazas en cada fotograma."""
    trazas, i = [], 0
    for p in partidos:
        n = int(rep.get(p, 0))
        xy = pos[i:i + n]
        i += n
        trazas.append(go.Scatter(
            x=xy[:, 0], y=xy[:, 1], mode="markers", name=nombre(p),
            marker=dict(size=11, color=color(p), line=dict(width=1.5, color=FONDO)),
            hovertemplate=f"<b>{nombre(p)}</b>: {n} escaños<extra></extra>"))
    return trazas


def _anotaciones_hemiciclo(titulo: str, detalle: str) -> list[dict]:
    return [
        dict(x=0, y=1.05, text="mayoría: 176", showarrow=False, yanchor="bottom", font=dict(size=12, color=TINTA_2)),
        dict(x=0, y=0.08, text=titulo, showarrow=False, font=dict(family=FUENTE_CIFRAS, size=26, color=TINTA)),
        dict(x=0, y=-0.06, text=detalle, showarrow=False, font=dict(size=13, color=TINTA_2)),
    ]


def hemiciclo_animado(reps: dict[str, pd.Series], titulos: dict[str, str], detalles: dict[str, str],
                      etiquetas: dict[str, str]) -> go.Figure:
    """Hemiciclo que recorre las fechas (claves de `reps`, en orden) con botón de reproducir.
    Se abre en el último fotograma; ▶ reproduce la serie entera desde el principio."""
    fechas = list(reps)
    partidos = sorted({p for r in reps.values() for p in r.index}, key=orden)
    pos = _posiciones(350)
    ultimo = fechas[-1]
    fig = go.Figure(
        data=_trazas_hemiciclo(reps[ultimo], partidos, pos),
        frames=[go.Frame(name=f, data=_trazas_hemiciclo(reps[f], partidos, pos),
                         layout=dict(annotations=_anotaciones_hemiciclo(titulos[f], detalles[f])))
                for f in fechas])
    fig.add_shape(type="line", x0=0, x1=0, y0=0.37, y1=1.05, line=dict(color=TINTA, width=1.5, dash="dot"),
                  layer="below")
    fig.update_layout(annotations=_anotaciones_hemiciclo(titulos[ultimo], detalles[ultimo]))
    paso = dict(frame=dict(duration=650, redraw=False), transition=dict(duration=450, easing="cubic-in-out"))
    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="left", x=0, y=-0.08, xanchor="left", yanchor="top", showactive=False,
            pad=dict(r=8, t=0), bgcolor=PANEL, bordercolor=REGLA, font=dict(color=TINTA, size=13),
            buttons=[dict(label="▶ Reproducir", method="animate", args=[fechas, dict(mode="immediate", **paso)]),
                     dict(label="❚❚", method="animate",
                          args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])])],
        sliders=[dict(
            active=len(fechas) - 1, x=0.2, y=-0.04, len=0.8, xanchor="left", yanchor="top", pad=dict(t=0),
            currentvalue=dict(visible=False), bgcolor=REGLA, activebgcolor=BRONCE, bordercolor=REGLA,
            tickcolor=REGLA, font=dict(color=TINTA_3, size=11),
            steps=[dict(method="animate", label=etiquetas[f],
                        args=[[f], dict(mode="immediate", frame=dict(duration=0, redraw=False),
                                        transition=dict(duration=350, easing="cubic-in-out"))])
                   for f in fechas])])
    fig = _base(fig, 470, dict(l=0, r=0, t=0, b=70))
    fig.update_xaxes(visible=False, range=[-1.06, 1.06])
    fig.update_yaxes(visible=False, range=[-0.14, 1.13], scaleanchor="x", scaleratio=1)
    return fig


def lineas_evolucion(df: pd.DataFrame, colores: dict[str, str], titulo_y: str, sufijo: str = "",
                     dec: int = 0, rango_y: list | None = None, marca: str | None = None,
                     umbral: float | None = None) -> go.Figure:
    """Una línea por columna de `df` (índice: fechas), con la cifra final rotulada a la derecha.
    `marca` señala la fecha elegida en el panel; `umbral` dibuja una referencia horizontal."""
    fig = go.Figure()
    f = f"{{:.{dec}f}}"
    fmt = lambda v: f.format(v).replace(".", ",") + sufijo   # noqa: E731
    for col in df.columns:
        s = df[col].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.to_numpy(), mode="lines+markers", name=col,
            line=dict(color=colores[col], width=2), marker=dict(size=6, color=colores[col]),
            customdata=[fmt(v) for v in s], hovertemplate=f"{col}: %{{customdata}}<br>%{{x|%d/%m}}<extra></extra>"))
        fig.add_annotation(x=s.index[-1], y=s.iloc[-1], text=f"{col} {fmt(s.iloc[-1])}", showarrow=False,
                           xanchor="left", xshift=10, font=dict(color=TINTA, size=12))
    if umbral is not None:
        fig.add_hline(y=umbral, line=dict(color=TINTA_3, width=1, dash="dot"))
    if marca is not None:
        fig.add_vline(x=pd.Timestamp(marca).timestamp() * 1000, line=dict(color=BRONCE, width=1.5))
    fig = _base(fig, 340, dict(l=10, r=150, t=10, b=10))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.15, x=0, font=dict(color=TINTA_2)),
                      hovermode="x unified")
    margen = pd.Timedelta(days=3)
    fig.update_xaxes(tickformat="%d/%m", range=[df.index.min() - margen, df.index.max() + margen])
    fig.update_yaxes(title=dict(text=titulo_y, font=dict(color=TINTA_3)), ticksuffix=sufijo, range=rango_y)
    return fig


__all__ = ["CONFIG", "hemiciclo", "leyenda_html", "rangos", "histograma_mayoria", "serie_encuestas",
           "efectos_casa", "barrido", "reparto_representativo", "pct", "barras_prob", "mapa_ganador", "mapa_colores",
           "mapa_valor", "geo_provincias", "hemiciclo_animado", "lineas_evolucion"]
