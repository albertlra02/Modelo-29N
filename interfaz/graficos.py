"""Gráficos Plotly de la aplicación. Todos usan los tokens de interfaz/estilo.py."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from interfaz.estilo import (BRONCE, FONDO, FUENTE, FUENTE_CIFRAS, GRIS_DATO, PANEL, REGLA, TINTA,
                             TINTA_2, TINTA_3, color, nombre, orden, pct, rampa)

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
    """Escaños medios redondeados por resto mayor para que sumen exactamente 350."""
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


def hemiciclo(sim: pd.DataFrame) -> go.Figure:
    rep = reparto_representativo(sim)
    rep = rep.sort_index(key=lambda idx: idx.map(orden))
    pos = _posiciones(int(rep.sum()))
    q = sim.quantile([0.1, 0.5, 0.9])
    fig = go.Figure()
    i = 0
    for p, n in rep.items():
        xy = pos[i:i + n]
        i += n
        fig.add_trace(go.Scatter(
            x=xy[:, 0], y=xy[:, 1], mode="markers", name=nombre(p),
            marker=dict(size=11, color=color(p), line=dict(width=1.5, color=FONDO)),
            hovertemplate=(f"<b>{nombre(p)}</b><br>Mediana {q.at[0.5, p]:.0f} escaños"
                           f"<br>80 % de las simulaciones: {q.at[0.1, p]:.0f}–{q.at[0.9, p]:.0f}<extra></extra>"),
        ))
    # 175 escaños a cada lado del eje: quien lo cruza desde la derecha o la izquierda llega a 176
    fig.add_shape(type="line", x0=0, x1=0, y0=0.37, y1=1.05, line=dict(color=TINTA, width=1.5, dash="dot"), layer="below")
    fig.add_annotation(x=0, y=1.05, text="mayoría: 176", showarrow=False, yanchor="bottom",
                       font=dict(size=12, color=TINTA_2))
    fig.add_annotation(x=0, y=0.06, text="350", showarrow=False,
                       font=dict(family=FUENTE_CIFRAS, size=34, color=TINTA))
    fig.add_annotation(x=0, y=-0.07, text="escaños", showarrow=False, font=dict(size=13, color=TINTA_3))
    fig = _base(fig, 380, dict(l=0, r=0, t=0, b=0))
    fig.update_xaxes(visible=False, range=[-1.06, 1.06])
    fig.update_yaxes(visible=False, range=[-0.14, 1.13], scaleanchor="x", scaleratio=1)
    return fig


def leyenda_html(sim: pd.DataFrame, voto: pd.Series | None = None) -> str:
    """Leyenda del hemiciclo: escaños del reparto representativo y, si se da, % de voto nacional."""
    rep = reparto_representativo(sim).sort_index(key=lambda idx: idx.map(orden))
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
    estilos = {"Sumar y Podemos por separado": (dict(color=TINTA, dash="solid"), "circle"),
               "Frente Amplio": (dict(color=color("FRENTE_AMPLIO"), dash="dash"), "diamond")}
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
SIN_SUPERFICIE = ["Ceuta", "Melilla"]          # demasiado pequeñas: se marcan con un punto
# Canarias viene desplazada +6,5º en el GeoJSON para acercarla a la península (sin recuadro:
# con la proyección cónica un rectángulo lon/lat sale torcido)


@lru_cache(maxsize=1)
def geo_provincias() -> dict:
    with open(RUTA_GEO, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _centros() -> pd.DataFrame:
    filas = {}
    for f in geo_provincias()["features"]:
        g = f["geometry"]
        anillos = [g["coordinates"][0]] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]
        pts = np.array([pt for a in anillos for pt in a])
        filas[f["id"]] = {"lon": pts[:, 0].mean(), "lat": pts[:, 1].mean()}
    return pd.DataFrame.from_dict(filas, orient="index")


def _mapa_base(fig: go.Figure, alto: int = 540) -> go.Figure:
    fig = _base(fig, alto, dict(l=0, r=0, t=0, b=0))
    # Encuadre fijo: fitbounds="locations" no encuadra bien con la proyección cónica
    fig.update_geos(visible=False, bgcolor=FONDO, lonaxis_range=[-12.2, 4.6], lataxis_range=[33.8, 44.0],
                    projection=dict(type="conic conformal", parallels=[36, 43], rotation=dict(lon=-4)))
    return fig


def _puntos_pequenas(fig, provs, colores, hover):
    """Ceuta y Melilla: un punto del mismo color que tendrían en el mapa."""
    c = _centros().reindex(provs)
    fig.add_trace(go.Scattergeo(lon=c.lon, lat=c.lat, mode="markers", showlegend=False,
                                marker=dict(size=10, color=colores, line=dict(width=2, color=FONDO)),
                                customdata=hover, hovertemplate="%{customdata}<extra></extra>"))


def mapa_ganador(ganador: pd.Series, hover: pd.Series) -> go.Figure:
    """Partido más votado en cada provincia. ganador/hover: índice = provincia."""
    geo = geo_provincias()
    fig = go.Figure()
    for p in ganador.value_counts().index:
        provs = ganador.index[ganador == p]
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="id", locations=list(provs), z=np.ones(len(provs)),
            colorscale=[[0, color(p)], [1, color(p)]], showscale=False, name=nombre(p),
            marker=dict(line=dict(color=FONDO, width=1.2)),
            customdata=hover.reindex(provs), hovertemplate="%{customdata}<extra></extra>"))
    pequenas = [x for x in SIN_SUPERFICIE if x in ganador.index]
    _puntos_pequenas(fig, pequenas, [color(ganador[x]) for x in pequenas], hover.reindex(pequenas))
    return _mapa_base(fig)


def mapa_valor(valor: pd.Series, hover: pd.Series, escala: str, titulo: str, desde_cero: bool = False) -> go.Figure:
    """Mapa de un valor en % (voto de un partido, escaño en juego) con una rampa de un solo tono.
    La escala cubre el rango observado (redondeado a 5) para que se distingan las provincias."""
    geo = geo_provincias()
    zmax = float(np.ceil(valor.max() / 5) * 5) or 5.0
    zmin = 0.0 if desde_cero else float(np.floor(valor.min() / 5) * 5)
    cs = rampa(escala)
    fig = go.Figure(go.Choropleth(
        geojson=geo, featureidkey="id", locations=list(valor.index), z=valor.to_numpy(), zmin=zmin, zmax=zmax,
        colorscale=cs, marker=dict(line=dict(color=FONDO, width=1.2)),
        colorbar=dict(title=dict(text=titulo, font=dict(color=TINTA_2, size=12)), ticksuffix=" %", thickness=10,
                      len=0.55, outlinewidth=0, x=0.98, tickfont=dict(color=TINTA_3)),
        customdata=hover.reindex(valor.index), hovertemplate="%{customdata}<extra></extra>"))
    pequenas = [x for x in SIN_SUPERFICIE if x in valor.index]
    c = _centros().reindex(pequenas)
    fig.add_trace(go.Scattergeo(lon=c.lon, lat=c.lat, mode="markers", showlegend=False,
                                marker=dict(size=10, color=valor.reindex(pequenas), colorscale=cs, cmin=zmin, cmax=zmax,
                                            line=dict(width=2, color=FONDO)),
                                customdata=hover.reindex(pequenas), hovertemplate="%{customdata}<extra></extra>"))
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
           "efectos_casa", "barrido", "reparto_representativo", "pct", "barras_prob", "mapa_ganador",
           "mapa_valor", "geo_provincias", "hemiciclo_animado", "lineas_evolucion"]
