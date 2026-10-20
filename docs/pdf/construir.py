"""Maqueta los dos documentos en HTML y los imprime en PDF con Edge (dos pasadas: la segunda pone las páginas del índice)."""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import markdown
from pypdf import PdfReader

import graficos as g

AQUI = Path(__file__).parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
AUTOR = "Alberto"
FECHA = "20 de octubre de 2026"


def md(texto):
    return markdown.markdown(texto, extensions=["tables"])


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def plano(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def figura(titulo, subtitulo, cuerpo, fuente):
    return (f'<figure><p class="fig-t">{titulo}</p><p class="fig-s">{subtitulo}</p>{cuerpo}'
            f'<figcaption>{fuente}</figcaption></figure>')


WEB = "modelo-29n.onrender.com"


def captura(nombre, ruta, titulo, pie):
    """Captura de la aplicación dentro de un marco de navegador con la dirección real."""
    return (f'<figure class="captura"><p class="fig-t">{titulo}</p><div class="navegador"><div class="barra">'
            f'<span class="pt"></span><span class="pt"></span><span class="pt"></span>'
            f'<span class="url">{WEB}{ruta}</span></div><img src="capturas/{nombre}.jpg" alt="{titulo}"></div>'
            f'<figcaption class="probar">{pie}</figcaption></figure>')


def comun(html):
    html = re.sub(r"<p><em>(.*?)</em></p>", r'<p class="nota">\1</p>', html, flags=re.S)
    html = html.replace("<table>", '<div class="tabla"><table>').replace("</table>", "</table></div>")
    return html


def secciones(html, numerar):
    """Da id a los h2 y devuelve la lista para el índice."""
    lista = []

    def pon(m):
        texto = m.group(1)
        i = len(lista) + 1
        lista.append((slug(texto), texto))
        num = f'<span class="num">{i:02d}</span>' if numerar else ""
        return f'<h2 id="{slug(texto)}">{num}{texto}</h2>'
    return re.sub(r"<h2>(.*?)</h2>", pon, html), lista


def indice(lista, paginas):
    filas = "".join(f'<li><a href="#{s}"><span class="i-n">{i:02d}</span><span class="i-t">{t}</span>'
                    f'<span class="i-p">{paginas.get(s, "")}</span></a></li>' for i, (s, t) in enumerate(lista, 1))
    return f'<nav class="indice"><p class="indice-t">Contenido</p><ol>{filas}</ol></nav>'


def paginas_de(pdf, lista):
    """Primera página (a partir de la 3) en la que aparece cada título de sección."""
    textos = [plano(p.extract_text() or "") for p in PdfReader(pdf).pages]
    out, desde = {}, 3
    for s, t in lista:
        clave = plano(t)[:28]
        for i in range(desde, len(textos) + 1):
            if clave in textos[i - 1]:
                out[s] = desde = i
                break
    return out


def imprimir(html_path, pdf_path):
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-margins",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
                    f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ================================================================ opinión
def opinion(paginas=None):
    texto = (AQUI / "opinion.md").read_text(encoding="utf-8")
    texto = texto.split("\n", 4)[4]                       # fuera título y firma: van en la portada
    texto = texto.replace("## Fuentes", "## Pruébalo tú\n\nCAPTURAS_OPINION\n\n## Fuentes")
    texto = re.sub(r"\[documento técnico\]\([^)]*\)", "documento técnico", texto)
    texto = (texto.replace("La línea azul supone", "La línea continua supone")
             .replace("; la gris, que", "; la discontinua, que").replace("la línea gris es", "la línea discontinua es"))
    html = comun(md(texto))
    figs = [
        figura("El PP queda primero con 129 escaños de mediana; el PSOE, con 109",
               "Escaños en el Congreso de cada partido en 10.000 simulaciones", g.escanos(),
               "Modelo 29-N · encuestas hasta el 17 de octubre · candidaturas registradas · participación del 65 %"),
        figura("Con un 74 % de participación, la mayoría de PP y Vox baja del 92 % al 60 %",
               "Simulaciones en que PP y Vox suman 176 o más, según la participación y cómo se reparten los votantes "
               "adicionales", g.participacion(),
               "Modelo 29-N · 3.000 simulaciones por punto · participación real: Ministerio del Interior"),
        figura("Cuanto más se votó, más sobrestimaron las encuestas a la derecha",
               "Error de la media de encuestas la víspera en el voto del bloque de derecha, en puntos",
               g.dispersion(), "Media de encuestas del modelo frente al resultado oficial · generales de 2015 a 2023"),
        figura("Con 16 retiradas bien elegidas, los tres quintos pasan del 17 % al 51 %",
               "Simulaciones en que PP y Vox suman 160 de los 266 senadores, según en cuántas provincias no se "
               "presenta Vox", g.retiradas(), "Modelo 29-N · encuestas hasta el 17 de octubre · 5.000 simulaciones"),
        figura("Los cuatro magistrados que elige el Senado deciden la mayoría del Constitucional",
               "Los 12 magistrados, quién los elige y su perfil, octubre de 2026", g.constitucional(),
               "Tribunal Constitucional y prensa (elDiario.es, Moncloa.com) · perfil según la clasificación habitual"),
        figura("Los tres quintos dependen de Vox y de la participación a la vez",
               "Simulaciones en que PP y Vox suman 160 de los 266 senadores", g.tres_quintos(),
               "Modelo 29-N · 5.000 simulaciones por escenario"),
    ]
    it = iter(figs)
    html = re.sub(r"<p>&#91;embedded content:.*?</p>", lambda m: next(it), html)
    citas = [("Así que la pregunta de verdad no es cuánta gente vota, sino quién.",
              "La pregunta de verdad no es cuánta gente vota, sino quién."),
             ("y ese supuesto es justo lo que la campaña está intentando cambiar.",
              "La mayoría que dan las encuestas es tan sólida como su supuesto de participación."),
             ("mueve dos senadores de golpe.", "Un punto de voto que cambie quién queda primero mueve dos senadores "
              "de golpe.")]
    for ancla, frase in citas:
        i = html.index(ancla)
        fin = html.index("</p>", i) + 4
        html = html[:fin] + f'<blockquote class="cita">{frase}</blockquote>' + html[fin:]
    html = html.replace("<p>CAPTURAS_OPINION</p>", PRUEBALO_OPINION)
    html, lista = secciones(html, numerar=False)
    html = html.replace('<h2 id="la-idea-en-pocas-palabras">La idea en pocas palabras</h2>\n<p>',
                        '<h2 id="la-idea-en-pocas-palabras">La idea en pocas palabras</h2>\n<p class="capitular">', 1)
    portada = f"""<section class="portada">
<div class="p-arriba">
  <p class="p-kicker">Análisis · Elecciones generales del 29 de noviembre de 2026</p>
  <h1>Una mayoría que depende de quién vote</h1>
  <p class="p-sub">El 29-N visto desde la participación, y un Senado que puede cambiarlo todo</p>
</div>
<div class="p-abajo">
  <div class="p-cifras">
    <div><span class="p-num">92 %</span><span class="p-lbl">participación del 65 %,<br>la que suponen las encuestas</span></div>
    <div class="p-flecha">→</div>
    <div><span class="p-num">60 %</span><span class="p-lbl">participación del 74 %,<br>con el reparto de 2015–2023</span></div>
  </div>
  <p class="p-que">Probabilidad de que PP y Vox sumen 176 escaños, según mi modelo</p>
  <p class="p-web">Todos los escenarios, en la aplicación que acompaña a este documento: <b>{WEB}</b></p>
  <p class="p-firma"><b>{AUTOR}</b> · {FECHA} · encuestas publicadas hasta el 17 de octubre</p>
</div></section>"""
    cuerpo = portada + GANCHO_OPINION + f'<main>{html}</main>'
    return pagina("Una mayoría que depende de quién vote", ESTILO_OPINION, FUENTES_OPINION, cuerpo), lista


# ================================================================ técnico
def tecnico(paginas=None):
    texto = (AQUI / "tecnico.md").read_text(encoding="utf-8")
    texto = texto.split("\n", 4)[4]
    texto = texto.replace("## Cómo funciona", "## La aplicación en imágenes\n\nCAPTURAS_TECNICO\n\n## Cómo funciona", 1)
    texto = re.sub(r"\[«Una mayoría que depende de quién vote»\]\([^)]*\)", "«Una mayoría que depende de quién vote»", texto)
    html = comun(md(texto))
    figs = [
        figura("De las encuestas a 350 diputados y 208 senadores en cuatro pasos",
               "Qué entra, qué se calcula y qué sale", g.flujo(), "Esquema del modelo"),
        figura("Cuantos más días faltan para votar, más grande es el error que se simula",
               "Error típico del voto de cada bloque, en puntos, medido en las generales de 2015 a 2023",
               g.error_dias(), "Calibración del modelo con las generales de 2015 a 2023"),
        figura("Los rangos aciertan casi tanto como prometen",
               "Escaños reales que cayeron dentro de cada rango del modelo", g.calibracion(),
               "Backtest fuera de muestra · generales de 2016, abril y noviembre de 2019 y 2023"),
    ]
    it = iter(figs)
    html = re.sub(r"<p>&#91;embedded content:.*?</p>", lambda m: next(it), html)

    def tarjeta(m):
        return f'<h3 class="dec"><span class="dec-n">{int(m.group(1)):02d}</span><span class="dec-t">{m.group(2)}</span></h3>'
    html = re.sub(r"<h3>(\d+)\. (.*?)</h3>", tarjeta, html)
    html = html.replace("<p>CAPTURAS_TECNICO</p>", CAPTURAS_TECNICO)
    html, lista = secciones(html, numerar=True)
    portada = f"""<section class="portada">
<div class="p-franja"></div>
<div class="p-cont">
  <p class="p-kicker">DOCUMENTO TÉCNICO · v1.1</p>
  <h1>Modelo 29-N</h1>
  <p class="p-sub">Cómo funciona la aplicación y por qué está hecha así: doce decisiones, cómo se tomaron y cómo se
  comprobaron</p>
  <div class="p-datos">
    <div><span class="d-num">350/350</span><span class="d-lbl">escaños reproducidos en cada general de 2015 a 2023</span></div>
    <div><span class="d-num">10.000</span><span class="d-lbl">elecciones simuladas por escenario, Congreso y Senado</span></div>
    <div><span class="d-num">8 <small>vs 22</small></span><span class="d-lbl">escaños de error por partido, frente a repetir la elección anterior</span></div>
    <div><span class="d-num">199/208</span><span class="d-lbl">senadores bien asignados con el voto real de 2023</span></div>
  </div>
  <p class="p-web">Pruébala: <b>{WEB}</b></p>
  <p class="p-firma"><b>{AUTOR}</b> · {FECHA}<br>Acompaña al documento de análisis «Una mayoría que depende de quién vote»</p>
</div></section>"""
    cuerpo = portada + indice(lista, paginas or {}) + f'<main>{html}</main>'
    return pagina("Modelo 29-N · documento técnico", ESTILO_TECNICO, FUENTES_TECNICO, cuerpo), lista


GANCHO_OPINION = f"""<section class="gancho">
<p class="g-kicker">En un minuto</p>
<h2 class="g-titulo">Cuatro cosas que la media de encuestas no está contando</h2>
<div class="g-lista">
 <div class="g-item"><span class="g-num">92 % → 60 %</span><p><b>La mayoría de PP y Vox depende de quién vaya a votar.</b>
 Con el 65 % de participación que suponen las encuestas sale en 92 de cada 100 simulaciones; si vota el 74 % y los
 nuevos votantes se comportan como entre 2015 y 2023, en 60.</p></div>
 <div class="g-item"><span class="g-num">+3 puntos</span><p><b>Ya ha pasado.</b> En las dos generales con más
 participación desde 2015 (2015 y abril de 2019), la media de encuestas sobrestimó a la derecha en casi 3 puntos.</p></div>
 <div class="g-item"><span class="g-num">17 % → 51 %</span><p><b>El Senado se decide en 16 provincias.</b> Si Vox no
 se presenta en las 16 que más pesan, PP y Vox pasan de tener los tres quintos (y con ellos el Constitucional) en el
 17 % de las simulaciones al 51 %. La lista de 15 que se ha publicado se queda en el 33 %.</p></div>
 <div class="g-item"><span class="g-num">52 %</span><p><b>El primer puesto está más abierto que la mayoría.</b> Con un 70 % de
 participación y algo de voto útil, el PSOE queda primero en la mitad de las simulaciones, aunque PP y
 Vox sigan sumando 176 en el 73 %.</p></div>
</div>
<div class="g-cta"><img src="capturas/participacion.jpg" alt="La aplicación">
<div><p class="g-cta-t">No hace falta creerme: compruébalo</p>
<p>Todo lo que cuento se puede reproducir en la aplicación que acompaña a este documento. Cambia la participación,
el voto útil o lo que hace Vox, y mira cómo cambian el Congreso y el Senado.</p>
<p class="g-url">{WEB}</p></div></div>
</section>"""

PRUEBALO_OPINION = (
    "<p>Las cifras de este documento salen de una aplicación que puedes usar tú mismo, sin instalar nada. Estas son "
    "tres cosas que merece la pena probar:</p>"
    + captura("participacion", "/participacion", "¿Y si vota más gente?",
              "<b>Prueba:</b> sube la participación al 74 % y cambia el reparto de los nuevos votantes de «histórico» a "
              "«simétrico». Es la discusión de este documento en dos clics.")
    + captura("senado", "/senado", "El Senado, con y sin Vox",
              "<b>Prueba:</b> cambia entre «Vox se presenta en todas», las 15 provincias publicadas y la retirada amplia, "
              "y mira cómo se mueven los tres quintos.")
    + captura("simulador", "/simulador", "¿Y si…? Mueve el voto de cualquier partido",
              "<b>Prueba:</b> pon tu propia estimación de voto y mira el hemiciclo al momento."))

CAPTURAS_TECNICO = (
    "<p>Antes de entrar en el detalle, así se ve. Las capturas son de la aplicación con el escenario "
    "base (encuestas hasta el 20 de octubre).</p>"
    + captura("resumen", "/", "Resumen: la respuesta en una frase",
              "Titular, hemiciclo y probabilidades. El botón «Cambiar escenario» recalcula todo el sitio.")
    + captura("provincias", "/provincias", "Congreso: las 52 circunscripciones",
              "Mapa del partido más votado, del voto de cada partido o de los cambios desde 2023, con el escaño en juego "
              "en cada provincia.")
    + captura("senado", "/senado", "Senado: 208 electos y 266 en el pleno",
              "Las tres hipótesis sobre Vox lado a lado, con la probabilidad de cada mayoría.")
    + captura("simulador", "/simulador", "¿Y si…?: el simulador sin Monte Carlo",
              "Mueve el voto de cualquier partido y el reparto de escaños se recalcula al instante."))


def pagina(titulo, estilo, fuentes, cuerpo):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{titulo}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fuentes}" rel="stylesheet"><style>{estilo}</style></head><body>{cuerpo}</body></html>"""


FUENTES_OPINION = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,800"
                   "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
                   "&family=Inter:wght@400;500;600&display=block")
FUENTES_TECNICO = ("https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700"
                   "&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500"
                   "&display=block")

ESTILO_OPINION = """
:root{--papel:#F6F1E7;--tinta:#1E1B16;--suave:#6B6358;--regla:#D9CFBE;--ocre:#A8741A;--ocre-c:#E9D9B8;--noche:#1F1C18;
--gris:#A39B8F}
@page{size:A4;margin:22mm 24mm 22mm 24mm;background:#F6F1E7;
 @bottom-center{content:counter(page);font:500 8.5pt Inter,sans-serif;color:#8A8174}
 @top-right{content:"Una mayoría que depende de quién vote";font:italic 8.5pt 'Source Serif 4',serif;color:#8A8174}}
@page:first{margin:0;@bottom-center{content:none}@top-right{content:none}}
@page indice{@top-right{content:none}}
html{background:var(--papel);-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font:10.6pt/1.58 'Source Serif 4',Georgia,serif;color:var(--tinta);font-optical-sizing:auto;
 hyphens:auto;-webkit-hyphens:auto;text-align:justify;font-variant-numeric:oldstyle-nums proportional-nums}
a{color:inherit;text-decoration:underline;text-decoration-color:var(--ocre);text-decoration-thickness:.6pt;text-underline-offset:2pt}
.portada{height:297mm;width:210mm;display:flex;flex-direction:column;break-after:page;text-align:left}
.p-arriba{flex:1;padding:30mm 24mm 12mm;display:flex;flex-direction:column;justify-content:flex-end;
 border-top:6mm solid var(--ocre)}
.p-kicker{font:600 8.5pt Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--ocre);margin:0 0 10mm}
.portada h1{font:800 54pt/0.98 Fraunces,serif;font-variation-settings:"opsz" 144;letter-spacing:-.02em;margin:0;
 color:var(--tinta);max-width:160mm;hyphens:none}
.p-sub{font:italic 15pt/1.35 'Source Serif 4',serif;color:var(--suave);margin:9mm 0 0;max-width:140mm}
.p-abajo{background:var(--noche);color:#F2EBDD;padding:16mm 24mm 18mm}
.p-cifras{display:flex;align-items:flex-end;gap:10mm}
.p-cifras>div{display:flex;flex-direction:column}
.p-num{font:800 68pt/1 Fraunces,serif;color:#E2B65C;font-variant-numeric:lining-nums;letter-spacing:-.02em}
.p-cifras>div:nth-child(3) .p-num{color:#F2EBDD}
.p-lbl{font:400 8.5pt/1.4 Inter,sans-serif;color:#BDB3A3;margin-top:3mm}
.p-flecha{font:400 40pt Fraunces,serif;color:#7C7366;padding-bottom:12mm}
.p-que{font:italic 12pt 'Source Serif 4',serif;margin:9mm 0 0;color:#F2EBDD}
.p-web{font:400 10pt Inter,sans-serif;color:#BDB3A3;margin:6mm 0 0}.p-web b{color:#E2B65C;font-weight:600}
.p-firma{font:400 8.5pt Inter,sans-serif;color:#BDB3A3;margin:7mm 0 0;border-top:.5pt solid #4A443B;padding-top:4mm}
.gancho{break-after:page;text-align:left;padding-top:4mm}
.g-kicker{font:600 8.5pt Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--ocre);margin:0 0 3mm}
.gancho .g-titulo{border:0;padding:0;margin:0 0 7mm;font:700 25pt/1.08 Fraunces,serif}
.g-lista{display:grid;grid-template-columns:1fr 1fr;gap:6mm 9mm}
.g-item{border-top:1.2pt solid var(--tinta);padding-top:3mm}
.g-num{display:block;font:800 25pt/1 Fraunces,serif;color:var(--ocre);font-variant-numeric:lining-nums;margin-bottom:2.5mm;letter-spacing:-.01em}
.g-item p{font-size:9.6pt;line-height:1.45;text-align:left;margin:0}
.g-cta{margin-top:9mm;background:var(--noche);color:#F2EBDD;display:grid;grid-template-columns:58% 1fr;gap:6mm;
 padding:6mm;align-items:center;border-radius:2mm}
.g-cta img{width:100%;border-radius:1.5mm;display:block}
.g-cta p{font:400 8.8pt/1.45 Inter,sans-serif;color:#CFC6B6;text-align:left;margin:0 0 3mm}
.g-cta .g-cta-t{font:700 14pt/1.15 Fraunces,serif;color:#F2EBDD}
.g-cta .g-url{font:600 10pt Inter,sans-serif;color:#E2B65C;margin:0}
.captura .navegador{width:80%;margin:0 auto;border:.6pt solid #CFC4B2;border-radius:2mm;overflow:hidden;background:#fff;box-shadow:0 1.5mm 4mm rgba(60,45,20,.12)}
.barra{display:flex;align-items:center;gap:1.4mm;background:#ECE5D8;padding:1.8mm 3mm;border-bottom:.6pt solid #D9CFBE}
.pt{width:2mm;height:2mm;border-radius:50%;background:#C9BFAF}
.url{margin-left:3mm;flex:1;background:#FBF8F2;border-radius:1mm;padding:.6mm 3mm;font:500 7.5pt Inter,sans-serif;color:#6B6358}
.captura img{width:100%;display:block}
figcaption.probar{font:400 8.6pt/1.45 Inter,sans-serif;color:var(--tinta);margin:3mm auto 0;width:80%}
.p-firma b{color:#F2EBDD;font-weight:600}
.indice{page:indice;break-after:page;padding-top:30mm}
.indice-t{font:600 8.5pt Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--ocre);margin:0 0 8mm}
.indice ol{list-style:none;margin:0;padding:0}
.indice li{border-top:.5pt solid var(--regla)}
.indice li:last-child{border-bottom:.5pt solid var(--regla)}
.indice a{display:flex;align-items:baseline;gap:6mm;padding:2.6mm 0;text-decoration:none}
.i-n{font:500 8.5pt Inter,sans-serif;color:var(--ocre);width:8mm}
.i-t{flex:1;font:400 13pt Fraunces,serif;text-align:left}
.i-p{font:500 9pt Inter,sans-serif;color:var(--suave);font-variant-numeric:tabular-nums}
main{orphans:3;widows:3}
h2{font:600 21pt/1.12 Fraunces,serif;font-variation-settings:"opsz" 72;letter-spacing:-.01em;margin:10mm 0 4mm;
 padding-top:4mm;border-top:1.2pt solid var(--tinta);text-align:left;break-after:avoid;hyphens:none}
main>h2:first-child{margin-top:0}
h3{font:600 13.5pt/1.2 Fraunces,serif;margin:8mm 0 2.5mm;color:var(--tinta);text-align:left;break-after:avoid}
h3::before{content:"";display:inline-block;width:7mm;height:1.6pt;background:var(--ocre);vertical-align:middle;margin-right:3mm}
p{margin:0 0 3.2mm}
.capitular::first-letter{float:left;font:800 46pt/0.8 Fraunces,serif;color:var(--ocre);padding:2.4mm 2.4mm 0 0}
.cita{margin:7mm 0 7mm;padding:0 0 0 7mm;border-left:2.5pt solid var(--ocre);font:400 italic 17pt/1.28 Fraunces,serif;
 color:var(--tinta);text-align:left;break-inside:avoid;hyphens:none}
ul{padding-left:5mm;margin:0 0 4mm}li{margin-bottom:1.6mm;text-align:left}
.nota{font:400 8pt/1.45 Inter,sans-serif;color:var(--suave);text-align:left;margin-top:-1mm}
.nota em{font-style:normal}
.tabla{break-inside:avoid;margin:5mm 0 3mm}
table{width:100%;border-collapse:collapse;font:400 8.6pt/1.35 Inter,sans-serif;font-variant-numeric:tabular-nums lining-nums}
th{text-align:left;font-weight:600;padding:2mm 2mm 2mm 0;border-bottom:1.2pt solid var(--tinta);vertical-align:bottom}
td{padding:2mm 2mm 2mm 0;border-bottom:.5pt solid var(--regla);text-align:left;vertical-align:top}
tbody tr:first-child td{background:transparent}
figure{margin:7mm 0 6mm;break-inside:avoid;padding:5mm 0 0;border-top:.5pt solid var(--regla)}
.fig-t{font:600 12.5pt/1.25 Fraunces,serif;margin:0 0 1mm;text-align:left;hyphens:none}
.fig-s{font:400 8.5pt/1.4 Inter,sans-serif;color:var(--suave);margin:0 0 3mm;text-align:left}
figure svg{width:100%;height:auto;display:block}
figcaption{font:400 7.5pt Inter,sans-serif;color:#8A8174;margin-top:2mm;text-align:left}
svg text{font-family:Inter,sans-serif;font-size:11.5px;font-variant-numeric:tabular-nums lining-nums}
svg .q{fill:#6B6358}svg .qb{fill:#6B6358;font-weight:600}svg .k{fill:#1E1B16}svg .kb{fill:#1E1B16;font-weight:600}
svg .a1{fill:#8A5A0E}svg .inv{fill:#FFF8EC}
svg .grid{stroke:#E2D8C7;stroke-width:1}svg .axis{stroke:#8A8174;stroke-width:1}svg .ref{stroke:#8A8174;stroke-dasharray:4 4}
svg .k-line{stroke:#1E1B16;stroke-width:2}
svg .s1{stroke:#A8741A;stroke-width:2.8}svg .s2{stroke:#A39B8F;stroke-width:2;stroke-dasharray:5 3}
svg .f1{fill:#A8741A}svg .f2{fill:#B9B1A4}
svg .grupo{fill:none;stroke:#BFB3A0}svg .grupo-clave{fill:#EFE3C9;stroke:#A8741A;stroke-width:2}
svg .prog{fill:#3D4F4C}svg .cons{fill:#FFFDF8;stroke:#3D4F4C;stroke-width:1.4}
"""

ESTILO_TECNICO = """
:root{--tinta:#14161A;--suave:#5C6370;--regla:#DADDE2;--naranja:#E8590C;--naranja-c:#FFE8D9;--fondo-c:#F5F6F8}
@page{size:A4;margin:24mm 22mm 22mm 24mm;
 @top-left{content:"MODELO 29-N";font:500 7.5pt 'IBM Plex Mono',monospace;letter-spacing:.12em;color:#8A909A}
 @top-right{content:"DOCUMENTO TÉCNICO";font:500 7.5pt 'IBM Plex Mono',monospace;letter-spacing:.12em;color:#8A909A}
 @bottom-left{content:counter(page, decimal-leading-zero);font:500 8pt 'IBM Plex Mono',monospace;color:#E8590C}}
@page:first{margin:0;@top-left{content:none}@top-right{content:none}@bottom-left{content:none}}
html{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font:9.8pt/1.55 'IBM Plex Sans',sans-serif;color:var(--tinta);hyphens:auto;-webkit-hyphens:auto}
a{color:inherit;text-decoration:underline;text-decoration-color:var(--naranja);text-decoration-thickness:.7pt;text-underline-offset:2pt}
.portada{height:297mm;width:210mm;display:flex;break-after:page}
.p-franja{width:14mm;background:var(--naranja)}
.p-cont{flex:1;padding:34mm 22mm 20mm 18mm;display:flex;flex-direction:column}
.p-kicker{font:500 8.5pt 'IBM Plex Mono',monospace;letter-spacing:.16em;color:var(--naranja);margin:0 0 8mm}
.portada h1{font:700 64pt/0.95 'Space Grotesk',sans-serif;letter-spacing:-.035em;margin:0}
.p-sub{font:400 14pt/1.4 'IBM Plex Sans',sans-serif;color:var(--suave);margin:8mm 0 0;max-width:135mm}
.p-datos{margin-top:auto;display:grid;grid-template-columns:1fr 1fr;border-top:1.5pt solid var(--tinta)}
.p-datos>div{padding:6mm 6mm 6mm 0;border-bottom:.6pt solid var(--regla);display:flex;flex-direction:column;gap:2mm}
.p-datos>div:nth-child(odd){border-right:.6pt solid var(--regla)}
.p-datos>div:nth-child(even){padding-left:6mm}
.d-num{font:700 26pt/1 'Space Grotesk',sans-serif;letter-spacing:-.02em}
.d-num small{font-size:13pt;color:var(--suave);font-weight:500}
.d-lbl{font:400 8.5pt/1.4 'IBM Plex Sans',sans-serif;color:var(--suave)}
.p-web{font:400 10pt 'IBM Plex Mono',monospace;color:var(--suave);margin:8mm 0 0}.p-web b{color:var(--naranja);font-weight:500}
.p-firma{font:400 8.5pt/1.6 'IBM Plex Mono',monospace;color:var(--suave);margin:4mm 0 0}
figure.captura{background:none;padding:0}
.captura .navegador{border:.7pt solid #C9CDD3;border-radius:1.5mm;overflow:hidden;background:#fff}
.barra{display:flex;align-items:center;gap:1.4mm;background:#EEF0F3;padding:1.8mm 3mm;border-bottom:.7pt solid #DADDE2}
.pt{width:2mm;height:2mm;border-radius:50%;background:#C4C8CF}
.url{margin-left:3mm;flex:1;background:#fff;border-radius:1mm;padding:.6mm 3mm;font:400 7.5pt 'IBM Plex Mono',monospace;color:#5C6370}
.captura img{width:100%;display:block}
figcaption.probar{font:400 8.4pt/1.45 'IBM Plex Sans',sans-serif;color:var(--suave);margin-top:2.5mm;letter-spacing:0}
.p-firma b{color:var(--tinta);font-weight:500}
.indice{break-after:page;padding-top:12mm}
.indice-t{font:500 8.5pt 'IBM Plex Mono',monospace;letter-spacing:.16em;text-transform:uppercase;color:var(--naranja);margin:0 0 8mm}
.indice ol{list-style:none;margin:0;padding:0}
.indice li{border-top:.6pt solid var(--regla)}.indice li:last-child{border-bottom:.6pt solid var(--regla)}
.indice a{display:flex;align-items:baseline;gap:6mm;padding:3mm 0;text-decoration:none}
.i-n{font:500 9pt 'IBM Plex Mono',monospace;color:var(--naranja);width:8mm}
.i-t{flex:1;font:500 12.5pt 'Space Grotesk',sans-serif}
.i-p{font:400 9pt 'IBM Plex Mono',monospace;color:var(--suave)}
main{orphans:3;widows:3}
h2{font:700 20pt/1.1 'Space Grotesk',sans-serif;letter-spacing:-.02em;margin:14mm 0 5mm;break-after:avoid;break-inside:avoid;
 position:relative;hyphens:none}
main>h2:first-child{margin-top:0}
h2 .num{display:block;font:500 8.5pt 'IBM Plex Mono',monospace;color:var(--naranja);letter-spacing:.12em;margin-bottom:2mm}
h2 .num::before{content:"SECCIÓN "}
h2::after{content:"";display:block;width:12mm;height:2.2pt;background:var(--naranja);margin-top:3mm}
h3{font:700 12pt/1.25 'Space Grotesk',sans-serif;margin:7mm 0 2.5mm;break-after:avoid}
h3.dec{display:flex;gap:4mm;align-items:baseline;margin:9mm 0 3mm;padding-top:3.5mm;border-top:.8pt solid var(--tinta)}
.dec-n{font:700 26pt/1 'Space Grotesk',sans-serif;color:var(--naranja);letter-spacing:-.03em;min-width:14mm}
.dec-t{font:700 13pt/1.2 'Space Grotesk',sans-serif}
p{margin:0 0 3mm}
ul,ol{padding-left:5mm;margin:0 0 4mm}li{margin-bottom:1.6mm}
main>ol{counter-reset:paso;list-style:none;padding-left:0}
main>ol>li{counter-increment:paso;position:relative;padding-left:10mm}
main>ol>li::before{content:counter(paso, decimal-leading-zero);position:absolute;left:0;top:.5pt;font:500 9pt 'IBM Plex Mono',monospace;color:var(--naranja)}
strong{font-weight:600}
.nota{font:400 8pt/1.45 'IBM Plex Sans',sans-serif;color:var(--suave)}
.tabla{break-inside:avoid;margin:4mm 0 5mm}
table{width:100%;border-collapse:collapse;font:400 8.6pt/1.4 'IBM Plex Sans',sans-serif}
th{text-align:left;font:500 7.5pt 'IBM Plex Mono',monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--suave);
 padding:2mm 3mm 2mm 0;border-bottom:1.2pt solid var(--tinta)}
td{padding:2mm 3mm 2mm 0;border-bottom:.5pt solid var(--regla);vertical-align:top}
td:last-child{font-variant-numeric:tabular-nums}
figure{margin:6mm 0 6mm;break-inside:avoid;background:var(--fondo-c);padding:5mm 5mm 4mm}
.fig-t{font:700 11pt/1.25 'Space Grotesk',sans-serif;margin:0 0 1mm}
.fig-s{font:400 8.3pt/1.4 'IBM Plex Sans',sans-serif;color:var(--suave);margin:0 0 3mm}
figure svg{width:100%;height:auto;display:block}
figcaption{font:400 7pt 'IBM Plex Mono',monospace;color:#8A909A;margin-top:2.5mm;letter-spacing:.02em}
svg text{font-family:'IBM Plex Sans',sans-serif;font-size:11.5px}
svg .q{fill:#5C6370}svg .qb{fill:#5C6370;font-weight:600}svg .k{fill:#14161A}svg .kb{fill:#14161A;font-weight:600}
svg .a1{fill:#C2470A}
svg .grid{stroke:#DADDE2}svg .axis{stroke:#8A909A}svg .ref{stroke:#8A909A;stroke-dasharray:4 4}
svg .s1{stroke:#E8590C;stroke-width:2.6}svg .s2{stroke:#14161A;stroke-width:1.8;stroke-dasharray:5 3}
svg .f1{fill:#E8590C}svg .f2{fill:#14161A}
svg .caja{fill:#fff;stroke:#9AA0AA;stroke-width:1}svg .caja-alt{fill:#fff;stroke:#9AA0AA;stroke-dasharray:4 3}
svg .caja-clave{fill:#FFE8D9;stroke:#E8590C;stroke-width:2}
svg .conector{fill:none;stroke:#8A909A;stroke-width:1.2}svg .flecha{fill:#8A909A}
"""


if __name__ == "__main__":
    for nombre, fn in (("opinion", opinion), ("tecnico", tecnico)):
        destino = AQUI / f"{nombre}.pdf"
        html, lista = fn()
        (AQUI / f"{nombre}.html").write_text(html, encoding="utf-8")
        imprimir(AQUI / f"{nombre}.html", destino)
        pags = paginas_de(destino, lista)
        html, _ = fn(pags)
        (AQUI / f"{nombre}.html").write_text(html, encoding="utf-8")
        imprimir(AQUI / f"{nombre}.html", destino)
        print(nombre, len(PdfReader(destino).pages), "páginas;", "índice:", pags, file=sys.stderr)
