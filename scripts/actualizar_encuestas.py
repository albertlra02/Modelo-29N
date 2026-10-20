"""
Pone al día las encuestas del ciclo 2026 desde Wikipedia y, si hay nuevas, recalcula la app.

    python -m scripts.actualizar_encuestas --comprobar   # sólo dice qué hay de nuevo; no cambia nada
    python -m scripts.actualizar_encuestas               # actualiza datos, corte y caché (tarda unos minutos)
    python -m scripts.actualizar_encuestas --programar   # lo deja programado cada día a las 9:00 (Windows)

Pasos: descarga la revisión actual de "Opinion polling for the 2026 Spanish general election" (y guarda su `oldid`
en datos/encuestas/fuentes_2026.json), extrae sus tablas nacionales (TABLAS) con el mismo importador que las series
históricas y, si cambian: reescribe sus ficheros en datos/encuestas/raw/, regenera los CSV limpios (parsear.py),
actualiza datos/MANIFEST.sha256, mueve el corte por defecto (FECHA en motor/proyeccion.py) al día de hoy, pasa los
tests y precalcula los escenarios de la app.

Los partidos de cada tabla se identifican por el enlace de su cabecera (los logotipos no siempre tienen texto). Si
Wikipedia añade una columna que no está en ENLACES, o reorganiza las tablas, el script se para sin tocar nada: hay
que decidir a mano a qué partido del modelo corresponde.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from datos.encuestas.descargar_historicas import USER_AGENT, extraer_tsv
from datos.encuestas.parsear import _fechas
from scripts.consola import configurar_salida_utf8

RAIZ = Path(__file__).resolve().parent.parent
TITULO = "Opinion polling for the 2026 Spanish general election"
RAW_DIR = RAIZ / "datos" / "encuestas" / "raw"
# Tablas nacionales de la página, en orden. Desde el registro de candidaturas (16/10/2026) Wikipedia abre una tabla
# nueva (Frente Amplio y Compromís-Front Valencià por separado) encima de la de 2026 de siempre.
TABLAS = [
    {"fichero": "wiki_2026_ciclo_2026_listas.json", "min_filas": 1, "exige": "FA"},
    {"fichero": "wiki_2026_ciclo_2026.json", "min_filas": 20, "misma_cabecera": True},
]
FUENTES = RAIZ / "datos" / "encuestas" / "fuentes_2026.json"
MANIFEST = RAIZ / "datos" / "MANIFEST.sha256"
PROYECCION = RAIZ / "motor" / "proyeccion.py"
CAMBIAN = [f"datos/encuestas/raw/{t['fichero']}" for t in TABLAS] + ["datos/encuestas/nacionales.csv",
                                                                     "datos/encuestas/autonomicas.csv"]

# Artículo enlazado en la cabecera -> etiqueta que entiende datos/encuestas/parsear.py (PARTIDOS)
ENLACES = {
    "People's_Party_(Spain)": "PP", "Spanish_Socialist_Workers'_Party": "PSOE", "Vox_(political_party)": "Vox",
    "Sumar_(electoral_alliance)": "Sumar", "Sumar_(electoral_platform)": "Sumar", "Broad_Front_(Spain)": "FA", "Valencian_Front": "FV",
    "Republican_Left_of_Catalonia": "ERC", "Together_for_Catalonia_(2020)": "Junts", "EH_Bildu": "EH Bildu",
    "Basque_Nationalist_Party": "PNV", "Galician_Nationalist_Bloc": "BNG", "Canarian_Coalition": "CCa",
    "Navarrese_People's_Union": "UPN", "Adelante_Andalucía_(2021)": "Adelante Andalucía (2021)",
    "Podemos_(Spanish_political_party)": "Podemos", "Se_Acabó_La_Fiesta": "SALF", "Catalan_Alliance": "Aliança.cat",
}


def ultima_revision() -> int:
    q = urllib.parse.urlencode({"action": "query", "titles": TITULO, "redirects": 1, "format": "json",
                                "prop": "revisions", "rvprop": "ids"})
    with urlopen(Request(f"https://en.wikipedia.org/w/api.php?{q}", headers={"User-Agent": USER_AGENT}),
                 timeout=30) as r:
        paginas = json.load(r)["query"]["pages"]
    return int(next(iter(paginas.values()))["revisions"][0]["revid"])


def descargar(oldid: int) -> str:
    url = f"https://en.wikipedia.org/w/index.php?title={TITULO.replace(' ', '_')}&oldid={oldid}"
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as r:
        return r.read().decode("utf-8")


def tablas(html: str) -> list[str]:
    """El HTML desde el comienzo de cada tabla wikitable (extraer_tsv lee la primera de cada trozo)."""
    return [html[m.start():] for m in re.finditer(r'<table[^>]*class="[^"]*wikitable', html)]


def partidos_de_cabecera(html: str) -> list[str]:
    """Etiqueta de cada columna de partido de la primera tabla, leída del enlace de su cabecera."""
    i = html.index('class="wikitable')
    cabecera = html[i:html.index("</tr>", i)]
    celdas = re.findall(r"<th[^>]*>(.*?)</th>", cabecera, re.S)[4:-1]      # sin empresa, fecha, n, part. ni Lead
    out, raros = [], []
    for c in celdas:
        m = re.search(r'href="(?:https://en\.wikipedia\.org)?/wiki/([^"#]+)"', c)
        articulo = urllib.parse.unquote(m.group(1)) if m else re.sub(r"<[^>]+>", "", c).strip()
        if articulo in ENLACES:
            out.append(ENLACES[articulo])
        else:
            raros.append(articulo)
    if raros:
        raise SystemExit(f"Columnas nuevas en la tabla de Wikipedia: {raros}. Añádelas a ENLACES (y, si hace falta, a "
                         "PARTIDOS en datos/encuestas/parsear.py) antes de actualizar.")
    return out


def solo_porcentajes(tsv: str) -> str:
    """Wikipedia pone bajo cada porcentaje la proyección de escaños de la encuesta ("31.4 133", "? 8"): se deja sólo
    el porcentaje, como en los ficheros que ya teníamos (año, empresa, fecha, muestra y participación, intactos)."""
    lineas = tsv.splitlines()
    out = [lineas[0]]
    for linea in lineas[1:]:
        c = linea.split("\t")
        out.append("\t".join(c[:5] + [x.split(" ")[0] if x else x for x in c[5:]]))
    return "\n".join(out)


def _fin(linea: str) -> date | None:
    c = linea.split("\t")
    return _fechas(c[2], int(c[0]))[1] if len(c) > 2 else None


def _ultimo(tsv: str) -> date | None:
    fechas = [f for f in map(_fin, tsv.splitlines()[1:]) if f]
    return max(fechas) if fechas else None


def actualizar_manifest() -> None:
    """Rehace el hash de los ficheros que cambian (y añade los que aún no estaban)."""
    huella = {r: hashlib.sha256((RAIZ / r).read_bytes()).hexdigest() for r in CAMBIAN if (RAIZ / r).exists()}
    out, vistos = [], set()
    for linea in MANIFEST.read_text(encoding="utf-8").splitlines():
        partes = linea.split(maxsplit=1)
        if len(partes) == 2 and partes[1] in huella:
            linea = f"{huella[partes[1]]}  {partes[1]}"
            vistos.add(partes[1])
        out.append(linea)
    out += [f"{h}  {r}" for r, h in huella.items() if r not in vistos]
    MANIFEST.write_text("\n".join(out) + "\n", encoding="utf-8")


def mover_corte(dia: str) -> None:
    texto = PROYECCION.read_text(encoding="utf-8")
    nuevo, n = re.subn(r'^FECHA = "\d{4}-\d{2}-\d{2}"', f'FECHA = "{dia}"', texto, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("No encuentro FECHA en motor/proyeccion.py")
    PROYECCION.write_text(nuevo, encoding="utf-8")


def correr(*args: str) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=RAIZ, check=True)


def programar(hora: str) -> None:
    bat = RAIZ / "actualizar_encuestas.bat"
    bat.write_text(f'@echo off\r\ncd /d "{RAIZ}"\r\n"{sys.executable}" -m scripts.actualizar_encuestas '
                   f'>> resultados\\actualizar_encuestas.log 2>&1\r\n', encoding="utf-8")
    subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", hora, "/TN", "Modelo 29-N - encuestas",
                    "/TR", f'"{bat}"'], check=True)
    print(f"Programado cada día a las {hora} (tarea «Modelo 29-N - encuestas»; el registro va a "
          "resultados/actualizar_encuestas.log). Para quitarlo: schtasks /Delete /TN \"Modelo 29-N - encuestas\" /F")


def comprobar(oldid: int) -> tuple[dict[Path, str], date | None, date | None]:
    """Extrae las tablas e informa de lo nuevo. Devuelve (ficheros que cambian -> TSV, último fin antes, ahora)."""
    trozos = tablas(descargar(oldid))
    if len(trozos) < len(TABLAS):
        raise SystemExit(f"La página tiene {len(trozos)} tablas y se esperaban al menos {len(TABLAS)}.")
    cambian, antes, ahora = {}, [], []
    for n, (t, trozo) in enumerate(zip(TABLAS, trozos), 1):
        ruta = RAW_DIR / t["fichero"]
        partidos = partidos_de_cabecera(trozo)
        if t.get("exige") and t["exige"] not in partidos:
            raise SystemExit(f"La tabla {n} no es la esperada para {t['fichero']} (no tiene {t['exige']}).")
        tsv = solo_porcentajes(extraer_tsv(trozo, 2026, tuple(partidos), min_filas=t["min_filas"]))
        viejo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else ""
        if t.get("misma_cabecera") and viejo and tsv.splitlines()[0] != viejo.splitlines()[0]:
            raise SystemExit(f"{t['fichero']}: han cambiado las columnas; revisa ENLACES y parsear.py a mano.")
        u_viejo, u_nuevo = _ultimo(viejo), _ultimo(tsv)
        if u_viejo and u_nuevo and u_nuevo < u_viejo:
            raise SystemExit(f"{t['fichero']}: la tabla nueva acaba antes que la que tenemos; no se actualiza.")
        antes += [u_viejo] if u_viejo else []
        ahora += [u_nuevo] if u_nuevo else []
        previas = set(viejo.splitlines()[1:])
        nuevas = [x for x in tsv.splitlines()[1:] if x not in previas]
        print(f"{t['fichero']}: {len(tsv.splitlines()) - 1} filas (antes {max(len(viejo.splitlines()) - 1, 0)}), "
              f"{len(nuevas)} nuevas o cambiadas.")
        for x in nuevas[:15]:
            print("  +", " | ".join(x.split("\t")[1:4]))
        if tsv != viejo:
            cambian[ruta] = tsv
    return cambian, max(antes, default=None), max(ahora, default=None)


def main(argv: list[str] | None = None) -> int:
    configurar_salida_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comprobar", action="store_true", help="sólo informa; no cambia nada")
    ap.add_argument("--sin-precalcular", action="store_true", help="no recalcula la caché de la app")
    ap.add_argument("--programar", metavar="HH:MM", nargs="?", const="09:00",
                    help="programa la actualización diaria en Windows (por defecto, a las 9:00)")
    a = ap.parse_args(argv)
    if a.programar:
        programar(a.programar)
        return 0

    oldid = ultima_revision()
    cambian, antes, ahora = comprobar(oldid)
    print(f"Revisión {oldid}. Última encuesta: {ahora:%d/%m} (la que teníamos: {antes:%d/%m}).")
    if not cambian:
        print("Sin cambios: no hay nada que actualizar.")
        return 0
    if a.comprobar:
        print("Sólo comprobación: no se ha cambiado nada. Sin --comprobar se actualiza todo.")
        return 0

    for ruta, tsv in cambian.items():
        ruta.write_text(json.dumps(tsv, ensure_ascii=False), encoding="utf-8")
    FUENTES.write_text(json.dumps({"titulo": TITULO, "oldid": oldid, "descargado": date.today().isoformat(),
                                   "url": f"https://en.wikipedia.org/w/index.php?oldid={oldid}"},
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    correr("datos/encuestas/parsear.py")
    actualizar_manifest()
    mover_corte(date.today().isoformat())
    correr("-m", "pytest", "-q")
    if not a.sin_precalcular:
        correr("-m", "scripts.precalcular")
    print(f"Hecho: encuestas hasta el {ahora:%d/%m}, corte por defecto el {date.today():%d/%m}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
