"""Gráficas en SVG estático para los PDF. Los colores van por clases CSS (cada documento pone su paleta);
los partidos conservan sus colores de interfaz/estilo.py y todas las series llevan etiqueta."""

PARTIDOS = {"PP": "#2a8fd8", "PSOE": "#b81d33", "Vox": "#5fa83a", "Frente Amplio": "#874aa6", "ERC": "#e0a23a",
            "EH Bildu": "#3f9a6e", "Junts": "#22a39a", "PNV": "#2f6b3b", "Podemos": "#6b3a8f"}


def n(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


def svg(w, h, cuerpo, etiqueta):
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{etiqueta}" xmlns="http://www.w3.org/2000/svg">{cuerpo}</svg>'


def t(x, y, texto, cls="q", anchor="start", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}" {extra}>{texto}</text>'


def ln(x1, y1, x2, y2, cls="grid", extra=""):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}" {extra}/>'


def poli(pts, cls):
    d = "".join(f"{'L' if i else 'M'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
    return f'<path d="{d}" class="{cls}" fill="none"/>'


# ---------------------------------------------------------------- opinión
def escanos():
    filas = [("PP", 109, 129, 152), ("PSOE", 90, 109, 130), ("Vox", 47, 66, 85), ("Frente Amplio", 5, 12, 24),
             ("ERC", 8, 10, 12), ("EH Bildu", 6, 7, 7), ("Junts", 3, 4, 6), ("PNV", 3, 3, 4), ("Podemos", 0, 0, 2)]
    x0, w, mx, y0, paso = 120, 500, 170, 24, 30
    def X(v):
        return x0 + v / mx * w
    yfin = y0 + paso * (len(filas) - 1)
    c = []
    for v in (0, 25, 50, 75, 100, 125, 150):
        c += [ln(X(v), y0 - 14, X(v), yfin + 14), t(X(v), yfin + 32, v, "q", "middle")]
    c.append(ln(X(176 / 2), 0, X(176 / 2), 0, "none"))
    c.append(t(x0 + w + 40, yfin + 32, "escaños", "q", "end"))
    for i, (p, a, m, b) in enumerate(filas):
        y, col = y0 + i * paso, PARTIDOS[p]
        c.append(t(x0 - 14, y + 4, p, "k", "end"))
        c.append(f'<line x1="{X(a):.1f}" y1="{y}" x2="{X(b) + .01:.1f}" y2="{y}" stroke="{col}" stroke-opacity=".35" '
                 f'stroke-width="9" stroke-linecap="round"/>')
        c.append(f'<circle cx="{X(m):.1f}" cy="{y}" r="5.5" fill="{col}" stroke="#fff" stroke-width="1.5"/>')
        c.append(t(X(b) + 14, y + 4, m, "kb"))
    c.append(t(x0, yfin + 52, "Punto: mediana. Barra: 80 % central de las simulaciones.", "q"))
    return svg(680, yfin + 60, "".join(c), "Escaños en el Congreso por partido")


def participacion():
    hist = [(60, 97.3), (62, 95.7), (64, 93.2), (65, 91.8), (66, 89.7), (68, 84.2), (70, 77.1), (72, 69.6), (74, 60.1), (76, 49.8)]
    sim = [(60, 93.6), (62, 92.8), (64, 92.1), (65, 91.8), (66, 91.4), (68, 90.1), (70, 89.1), (72, 87.9), (74, 86.6), (76, 85.9)]
    def X(v):
        return 60 + (v - 60) / 16 * 470
    def Y(v):
        return 250 - (v - 40) / 60 * 220
    c = []
    for v in (40, 60, 80, 100):
        c += [ln(60, Y(v), X(76), Y(v)), t(50, Y(v) + 4, f"{v} %", "q", "end")]
    for v in range(60, 77, 2):
        c.append(t(X(v), 270, f"{v} %", "q", "middle"))
    c.append(t(X(76), 288, "participación sobre el censo", "q", "end"))
    c += [ln(X(65), 22, X(65), 250, "ref"), t(X(65) + 6, 20, "lo que suponen las encuestas: 65 %", "q")]
    c.append(poli([(X(a), Y(b)) for a, b in sim], "s2"))
    c.append(poli([(X(a), Y(b)) for a, b in hist], "s1"))
    for a, b in sim:
        c.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="3" class="f2"/>')
    for a, b in hist:
        c.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="3.5" class="f1"/>')
    c.append(t(X(76) + 10, Y(85.9) + 4, "Reparto simétrico: 86 %", "kb"))
    c.append(t(X(76) + 10, Y(49.8) + 4, "Como en 2015–2023: 50 %", "kb a1"))
    c.append(t(X(74) - 8, Y(60.1) + 18, "60 %", "kb", "end"))
    c.append(t(X(65) - 4, Y(91.8) + 20, "92 %", "kb", "end"))
    # participación real
    c.append(ln(60, 320, X(76), 320, "axis"))
    c.append(t(20, 324, "Real", "qb"))
    for _nombre, p in (("2015", 69.7), ("2016", 66.5), ("abr. 2019", 71.8), ("nov. 2019", 66.2), ("2023", 66.6)):
        c.append(ln(X(p), 313, X(p), 327, "k-line"))
    c.append(t(X(69.7), 344, "2015: 69,7 %", "k", "middle"))
    c.append(t(X(71.8), 362, "abr. 2019: 71,8 %", "k", "middle"))
    c.append(t(X(66.9), 344, "2016, nov. 2019 y 2023: 66–67 %", "k", "end"))
    return svg(720, 372, "".join(c), "Probabilidad de mayoría de PP y Vox según la participación")


def dispersion():
    filas = [("2015", 69.7, 2.6, "s"), ("2016", 66.5, -2.1, "s"), ("abril de 2019", 71.8, 3.0, "s"),
             ("noviembre de 2019", 66.2, 0.3, "w"), ("2023", 66.6, 1.0, "s")]
    def X(v):
        return 70 + (v - 65) / 8 * 520
    def Y(v):
        return 160 - v * 34
    c = []
    for v in range(-3, 5):
        c += [ln(70, Y(v), 590, Y(v), "axis" if v == 0 else "grid"),
              t(60, Y(v) + 4, f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v)}", "q", "end")]
    for v in (65, 67, 69, 71, 73):
        c.append(t(X(v), Y(-3) + 22, f"{v} %", "q", "middle"))
    c.append(t(590, Y(-3) + 40, "participación sobre el censo", "q", "end"))
    c.append(t(78, Y(4) + 14, "las encuestas daban más a la derecha de lo que sacó", "q"))
    c.append(t(78, Y(-3) - 8, "las encuestas daban menos a la derecha de lo que sacó", "q"))
    for nom, p, e, lado in filas:
        sg = f"{'+' if e > 0 else '−'}{n(abs(e))}"
        c.append(f'<circle cx="{X(p):.1f}" cy="{Y(e):.1f}" r="7" class="f1"/>')
        if lado == "s":
            c.append(t(X(p) + 12, Y(e) - 8, f"{nom}: {sg}", "kb"))
        else:
            c.append(t(X(p) - 12, Y(e) - 8, f"{nom}: {sg}", "kb", "end"))
    return svg(680, Y(-3) + 50, "".join(c), "Error de las encuestas con la derecha según la participación")


def retiradas():
    p65 = [17.2, 20.3, 23.4, 25.6, 27.4, 29.6, 31.8, 34.0, 36.6, 39.1, 41.1, 42.9, 44.8, 46.4, 48.0, 49.4, 50.6, 52.0,
           53.5, 54.9, 56.3, 58.0, 59.9, 61.7, 63.7, 65.7, 67.5, 69.5, 71.2, 72.8, 74.7, 76.9, 78.6, 80.2, 81.5, 82.9,
           84.0, 85.1, 85.9, 86.7, 87.0, 87.5, 87.8]
    p72 = [3.8, 4.7, 5.8, 6.5, 7.3, 7.9, 8.6, 9.5, 10.3, 11.1, 12.2, 13.0, 13.8, 14.6, 15.3, 16.2, 17.2, 18.4, 19.4,
           20.5, 21.8, 23.2, 24.6, 25.8, 27.0, 28.4, 29.8, 31.2, 32.7, 34.3, 35.9, 37.6, 39.6, 41.9, 44.4, 47.2, 50.1,
           53.7, 55.3, 56.9, 58.8, 59.3, 59.6]
    def X(k):
        return 60 + k / 42 * 480
    def Y(p):
        return 250 - p * 2.3
    c = []
    for v in (0, 25, 50, 75, 100):
        c += [ln(60, Y(v), 540, Y(v), "ref" if v == 50 else "grid"), t(50, Y(v) + 4, f"{v} %", "q", "end")]
    for k in (0, 10, 20, 30, 40):
        c.append(t(X(k), 270, k, "q", "middle"))
    c.append(t(540, 288, "provincias donde Vox no presenta lista (las más eficaces primero)", "q", "end"))
    c.append(poli([(X(k), Y(p)) for k, p in enumerate(p72)], "s2"))
    c.append(poli([(X(k), Y(p)) for k, p in enumerate(p65)], "s1"))
    c.append(t(X(42) + 8, Y(87.8) + 4, "Con un 65 %: techo 88 %", "kb a1"))
    c.append(t(X(42) + 8, Y(59.6) + 4, "Con un 72 %: techo 60 %", "kb"))
    for k, p, lado in ((16, 50.6, -1), (36, 50.1, 1)):
        c.append(f'<circle cx="{X(k):.1f}" cy="{Y(p):.1f}" r="6" fill="none" class="k-line" stroke-width="1.5"/>')
        c.append(t(X(k) + (-10 if lado < 0 else 10), Y(p) + (-12 if lado < 0 else 20),
                   f"{k} retiradas → {round(p)} %", "kb", "end" if lado < 0 else "start"))
    return svg(720, 296, "".join(c), "Tres quintos del Senado según las retiradas de Vox")


def constitucional():
    grupos = [("Congreso (3/5)", "mandato hasta nov. 2028", 20, 20, False,
               [("Inmaculada Montalbán", "progresista · vicepres.", True), ("Ramón Sáez", "progresista", True),
                ("Enrique Arnaldo", "conservador", False), ("Concepción Espejel", "conservadora", False)]),
              ("Senado (3/5)", "caducado: en funciones", 360, 20, True,
               [("C. Conde-Pumpido", "progresista · presidente", True), ("M.ª Luisa Balaguer", "progresista", True),
                ("Ricardo Enríquez", "conservador", False), ("José María Macías", "conservador", False)]),
              ("Gobierno", "mandato hasta ene. 2032", 20, 206, False,
               [("Juan Carlos Campo", "progresista", True), ("Laura Díez", "progresista", True)]),
              ("Poder Judicial (CGPJ)", "mandato hasta ene. 2032", 360, 206, False,
               [("M.ª Luisa Segoviano", "progresista", True), ("César Tolosa", "conservador", False)])]
    c = []
    for nombre, nota, x, y, clave, mags in grupos:
        alto = 170 if len(mags) == 4 else 110
        c.append(f'<rect x="{x}" y="{y}" width="320" height="{alto}" rx="6" class="{"grupo-clave" if clave else "grupo"}"/>')
        c.append(t(x + 14, y + 24, nombre, "kb"))
        c.append(t(x + 306, y + 24, nota, "qb a1" if clave else "q", "end"))
        for i, (m, perfil, prog) in enumerate(mags):
            bx, by = x + 14 + (i % 2) * 150, y + 38 + (i // 2) * 62
            c.append(f'<rect x="{bx}" y="{by}" width="142" height="52" rx="4" class="{"prog" if prog else "cons"}"/>')
            c.append(t(bx + 10, by + 21, m, "kb inv" if prog else "kb"))
            c.append(t(bx + 10, by + 39, perfil, "q inv" if prog else "q"))
    c.append('<rect x="20" y="340" width="14" height="14" rx="2" class="prog"/>')
    c.append(t(42, 352, "progresista (relleno)", "q"))
    c.append('<rect x="200" y="340" width="14" height="14" rx="2" class="cons"/>')
    c.append(t(222, 352, "conservador (contorno)", "q"))
    c.append(t(20, 384, "Hoy: 7 progresistas y 5 conservadores.", "kb"))
    c.append(t(20, 404, "Si PP y Vox eligen a los cuatro del Senado: 5 y 7, y cambia la presidencia.", "k"))
    return svg(700, 414, "".join(c), "Los doce magistrados del Constitucional")


def tres_quintos():
    filas = [("Vox se presenta en todas", 17, 3), ("No se presenta en las 15 publicadas", 33, 4),
             ("Se retira en 44–46 provincias", 87, 43)]
    x0, w = 250, 380
    def X(v):
        return x0 + v / 100 * w
    c = [f'<rect x="{x0}" y="4" width="12" height="12" rx="2" class="f1"/>', t(x0 + 18, 14, "participación del 65 %", "q"),
         f'<rect x="{x0 + 190}" y="4" width="12" height="12" rx="2" class="f2"/>', t(x0 + 208, 14, "participación del 74 %", "q")]
    y0, alto, hueco = 36, 26, 22
    yfin = y0 + len(filas) * (2 * alto + hueco) - hueco
    for v in (0, 25, 50, 75, 100):
        c += [ln(X(v), y0 - 4, X(v), yfin), t(X(v), yfin + 18, f"{v} %", "q", "middle")]
    for i, (nom, a, b) in enumerate(filas):
        y = y0 + i * (2 * alto + hueco)
        c.append(t(x0 - 14, y + alto + 4, nom, "k", "end"))
        for j, (v, cls) in enumerate(((a, "f1"), (b, "f2"))):
            yy = y + j * alto
            c.append(f'<rect x="{X(0)}" y="{yy + 3}" width="{max(X(v) - X(0), 2):.1f}" height="{alto - 6}" rx="2" class="{cls}"/>')
            c.append(t(X(v) + 8, yy + alto / 2 + 4, f"{v} %", "kb"))
    return svg(680, yfin + 26, "".join(c), "Tres quintos del Senado por escenario")


# ---------------------------------------------------------------- técnico
def flujo():
    def caja(x, y, w, titulo, sub, cls="caja"):
        return (f'<rect x="{x}" y="{y - 26}" width="{w}" height="52" rx="3" class="{cls}"/>'
                + t(x + 12, y - 4, titulo, "kb") + t(x + 12, y + 14, sub, "q"))
    c = ['<defs><marker id="fl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="flecha"/></marker></defs>']
    for d in ("M200 40H244", "M200 120H244", "M200 200H244", "M350 66V92", "M350 146V172", "M456 200H500",
              "M598 146V172", "M598 226V266", "M598 246H350V266"):
        c.append(f'<path d="{d}" class="conector" marker-end="url(#fl)"/>')
    c += [caja(10, 40, 190, "Encuestas nacionales", "todas las publicadas"),
          caja(10, 120, 190, "Encuestas autonómicas", "CEO, Sondaxe, GAD3…"),
          caja(10, 200, 190, "Resultados oficiales", "generales 2015–2023"),
          caja(246, 40, 210, "01  Media de encuestas", "corrige el sesgo de cada casa"),
          caja(246, 120, 210, "02  Capa autonómica", "ajusta el reparto por CCAA"),
          caja(246, 200, 210, "03  Provincias", "desde el resultado de 2023"),
          caja(500, 120, 196, "Tu escenario", "participación, voto útil…", "caja-alt"),
          caja(500, 200, 196, "04  Simulación", "10.000 elecciones con error", "caja-clave"),
          caja(246, 294, 210, "Congreso: 350 escaños", "D’Hondt y 3 % por provincia"),
          caja(500, 294, 196, "Senado: 208 + 58", "voto limitado y designados")]
    return svg(710, 330, "".join(c), "Flujo del modelo")


def error_dias():
    dias = [48, 40, 30, 21, 14, 7, 1]
    der = [3.96, 3.73, 3.42, 3.12, 2.86, 2.58, 2.31]
    izq = [3.96, 3.70, 3.34, 2.99, 2.68, 2.33, 1.98]
    def X(d):
        return 60 + (48 - d) / 47 * 480
    def Y(v):
        return 250 - v * 55
    c = []
    for v in range(5):
        c += [ln(60, Y(v), 540, Y(v)), t(50, Y(v) + 4, f"{v} pts", "q", "end")]
    for d in dias:
        c.append(t(X(d), 270, d, "q", "middle"))
    c.append(t(540, 288, "días que faltan para votar", "q", "end"))
    c += [ln(X(40), 14, X(40), 250, "ref"), t(X(40) + 6, 20, "hoy, 20 de octubre: faltan 40 días", "q")]
    c.append(poli([(X(d), Y(v)) for d, v in zip(dias, izq)], "s2"))
    c.append(poli([(X(d), Y(v)) for d, v in zip(dias, der)], "s1"))
    for d, v in zip(dias, izq):
        c.append(f'<rect x="{X(d) - 3.5:.1f}" y="{Y(v) - 3.5:.1f}" width="7" height="7" class="f2"/>')
    for d, v in zip(dias, der):
        c.append(f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="4" class="f1"/>')
    c.append(t(X(1) + 10, Y(2.31) + 0, "Derecha: 2,3", "kb a1"))
    c.append(t(X(1) + 10, Y(1.98) + 12, "Izquierda: 2,0", "kb"))
    c.append(t(X(40) - 8, Y(3.73) - 8, "3,7", "kb", "end"))
    c.append(t(X(40) - 8, Y(3.70) + 18, "3,7", "kb", "end"))
    c.append(t(60, 312, "Error típico del voto de cada bloque en la simulación (incluye el margen de prudencia del 10 %).", "q"))
    return svg(680, 320, "".join(c), "Error simulado según los días que faltan")


def calibracion():
    filas = [(10, 6), (20, 15), (30, 31), (40, 48), (50, 52), (60, 63), (70, 65), (80, 76), (90, 87)]
    s, x0, y0 = 3.0, 80, 330
    def X(v):
        return x0 + v * s
    def Y(v):
        return y0 - v * s
    c = []
    for v in range(0, 101, 20):
        c += [ln(X(0), Y(v), X(100), Y(v)), ln(X(v), Y(0), X(v), Y(100)),
              t(X(0) - 10, Y(v) + 4, f"{v} %", "q", "end"), t(X(v), Y(0) + 20, f"{v} %", "q", "middle")]
    c.append(t(X(100), Y(0) + 40, "lo que promete el rango", "q", "end"))
    c.append(t(X(0) - 60, Y(100) - 14, "veces que el resultado real cayó dentro", "q"))
    c.append(ln(X(0), Y(0), X(100), Y(100), "ref"))
    c.append(t(X(62), Y(66), "calibración perfecta", "q", "start", f'transform="rotate(-45 {X(62):.1f} {Y(66):.1f})"'))
    c.append(poli([(X(a), Y(b)) for a, b in filas], "s1"))
    for a, b in filas:
        c.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="4.5" class="f1"/>')
        if a != 80:
            c.append(t(X(a) + 8, Y(b) + 16, f"{b}", "q"))
    c.append(t(X(80) + 22, Y(76) + 4, "← rango del 80 %: acertó el 76 %", "kb a1"))
    c.append(t(420, 250, "Cada punto: de todos los rangos que", "q"))
    c.append(t(420, 268, "el modelo daba con esa confianza,", "q"))
    c.append(t(420, 286, "cuántos contuvieron el escaño real.", "q"))
    c.append(t(420, 304, "Partidos estatales, 2016–2023,", "q"))
    c.append(t(420, 322, "fuera de muestra.", "q"))
    return svg(640, 380, "".join(c), "Calibración de los rangos")
