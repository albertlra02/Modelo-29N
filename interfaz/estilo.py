"""
Tokens visuales de la aplicación: colores, tipografía y metadatos de partidos.

Los colores de los cinco partidos estatales principales se validaron con el
validador de paletas (separación para daltonismo y visión normal, todos los pares).
Vox queda por debajo de 3:1 de contraste sobre blanco: por eso todas las gráficas
llevan etiquetas o tabla, nunca solo color.

El mapa por provincias usa PP, PSOE y EH Bildu juntos (todos los pares, como en
cualquier mapa): EH Bildu pasó de #4f8a74 a #3f9a6e para superar el mínimo de croma
y separarse de PP y PSOE con daltonismo. Las rampas de los mapas de valor van de un
extremo claro (mezcla con el fondo, validado a >= 2:1 sobre FONDO) al color del
partido y a dos pasos oscuros; ERC, BNG o CC no tienen rampa válida y no se ofrecen.
Frente Amplio pasó de #b9468a a #874aa6: el rosa quedaba a ΔE 12 del PSOE (mínimo 15)
incluso con visión normal; el morado pasa con PP, PSOE y Vox en todos los pares.
"""

TINTA = "#15202B"
TINTA_2 = "#4A5664"
TINTA_3 = "#7A8592"
REGLA = "#D8DEE4"
FONDO = "#F3F5F7"
PANEL = "#FFFFFF"
BRONCE = "#7A5F14"      # acento de interfaz (botón, umbral de mayoría)
GRIS_DATO = "#B7C0C9"   # marcas "por debajo del umbral"

FUENTE = "IBM Plex Sans, Segoe UI, Helvetica, Arial, sans-serif"
FUENTE_CIFRAS = "IBM Plex Sans Condensed, IBM Plex Sans, Segoe UI, Arial Narrow, sans-serif"

PARTIDOS = {
    # clave: (nombre visible, color, posición izquierda -> derecha en el hemiciclo)
    "PODEMOS": ("Podemos", "#6b3a8f", 0),
    "FRENTE_AMPLIO": ("Frente Amplio", "#874aa6", 1),
    "SUMAR": ("Sumar", "#d9649f", 2),
    "BILDU": ("EH Bildu", "#3f9a6e", 3),
    "ERC": ("ERC", "#e0a23a", 4),
    "BNG": ("BNG", "#7fb4d6", 5),
    "ADELANTE": ("Adelante Andalucía", "#1f8a5a", 6),
    "PSOE": ("PSOE", "#b81d33", 7),
    "PNV": ("PNV", "#2f6b3b", 8),
    "CC": ("Coalición Canaria", "#e7c94a", 9),
    "JUNTS": ("Junts", "#22a39a", 10),
    "TERUEL": ("Teruel Existe", "#8d6e4f", 11),
    "SORIA_YA": ("Soria ¡Ya!", "#a85d3c", 12),
    "UPL": ("UPL", "#8a3d5d", 13),
    "UPN": ("UPN", "#24406e", 14),
    "PP": ("PP", "#2a8fd8", 15),
    "VOX": ("Vox", "#5fa83a", 16),
    "SALF": ("Se Acabó La Fiesta", "#3c4652", 17),
}
PRINCIPALES = ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "FRENTE_AMPLIO"]

# Mezcla con el fondo del extremo claro de cada rampa secuencial (validada, ver arriba)
RAMPA_CLARO = {"PP": 0.35, "PSOE": 0.45, "VOX": 0.25, "SUMAR": 0.35, "PODEMOS": 0.45,
               "FRENTE_AMPLIO": 0.45, "BILDU": 0.35, "JUNTS": 0.25, "PNV": 0.45, "BRONCE": 0.45}


def nombre(p: str) -> str:
    return PARTIDOS.get(p, (p.title(), TINTA_3, 99))[0]


def color(p: str) -> str:
    return PARTIDOS.get(p, (p, TINTA_3, 99))[1]


def orden(p: str) -> int:
    return PARTIDOS.get(p, (p, TINTA_3, 99))[2]


def pct(x: float, dec: int = 0) -> str:
    """Porcentaje en formato español: 85 %, 12,5 %."""
    v = f"{100 * x:.{dec}f}".replace(".", ",")
    return f"{v} %"


def mezcla(a: str, b: str, t: float) -> str:
    """Color a mitad de camino entre a (t=0) y b (t=1)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def rampa(p: str) -> list[list]:
    """Escala secuencial validada (claro -> color -> oscuro) para un partido o 'BRONCE'."""
    c = BRONCE if p == "BRONCE" else color(p)
    return [[0, mezcla(c, FONDO, RAMPA_CLARO[p])], [0.45, c], [0.75, mezcla(c, TINTA, 0.35)], [1, mezcla(c, TINTA, 0.65)]]


def num(x: float, dec: int = 1) -> str:
    """Número con coma decimal: 12,5."""
    return f"{x:.{dec}f}".replace(".", ",")


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, button, input, label {{
  font-family: {FUENTE};
  font-feature-settings: "tnum" 1;
}}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }}
h1, h2, h3 {{ font-family: {FUENTE_CIFRAS}; color: {TINTA}; letter-spacing: -0.01em; }}

.cabecera h1 {{ font-size: 2.1rem; font-weight: 700; margin: 0 0 .25rem 0; }}
.cabecera p  {{ color: {TINTA_2}; font-size: .98rem; margin: 0; max-width: 72ch; }}

.cifra-principal {{
  font-family: {FUENTE_CIFRAS}; font-weight: 700; color: {TINTA};
  font-size: clamp(4.2rem, 8vw, 6.5rem); line-height: .9; margin: .4rem 0 .5rem 0;
}}
.cifra-texto {{ color: {TINTA_2}; font-size: 1rem; line-height: 1.45; max-width: 30ch; margin-bottom: 1.4rem; }}
.fila-prob {{
  display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
  border-top: 1px solid {REGLA}; padding: .7rem 0;
}}
.fila-prob span:first-child {{ color: {TINTA_2}; font-size: .95rem; flex: 1; }}
.fila-prob span:last-child {{ font-family: {FUENTE_CIFRAS}; font-weight: 600; font-size: 1.45rem; color: {TINTA}; white-space: nowrap; }}

.leyenda {{ display: flex; flex-wrap: wrap; gap: .35rem 1.1rem; margin: -.4rem 0 .4rem 0; }}
.leyenda div {{ display: flex; align-items: center; gap: .4rem; font-size: .88rem; color: {TINTA}; }}
.leyenda i {{ width: .7rem; height: .7rem; border-radius: 50%; display: inline-block; }}
.leyenda b {{ font-family: {FUENTE_CIFRAS}; font-weight: 600; }}
.leyenda .voto {{ color: {TINTA_3}; }}

.nota {{ color: {TINTA_3}; font-size: .85rem; line-height: 1.45; max-width: 90ch; }}

[data-testid="stSidebar"] {{ border-right: 1px solid {REGLA}; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.15rem; margin-bottom: .2rem; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {REGLA}; }}
.stTabs [data-baseweb="tab"] {{ padding: .6rem 0; font-weight: 500; }}
div[data-testid="stFormSubmitButton"] button {{
  background: {BRONCE}; color: #fff; border: 0; font-weight: 600;
}}
div[data-testid="stFormSubmitButton"] button:hover {{ background: #5f4a10; color: #fff; }}
div[data-testid="stFormSubmitButton"] button:focus-visible {{ outline: 2px solid {TINTA}; outline-offset: 2px; }}

/* Entrada suave de cifras y gráficos al aparecer (se desactiva si el sistema pide menos movimiento) */
@keyframes aparecer {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
.cifra-principal, .fila-prob, .leyenda, [data-testid="stPlotlyChart"] {{ animation: aparecer .45s ease-out both; }}
@media (prefers-reduced-motion: reduce) {{
  .cifra-principal, .fila-prob, .leyenda, [data-testid="stPlotlyChart"] {{ animation: none; }}
}}
</style>
"""
