"""
Resultados oficiales del Ministerio del Interior -> datos/raw/.

    python datos/oficiales.py              # descarga lo que falte y regenera los CSV
    python datos/oficiales.py --comprobar  # sólo compara los CSV actuales con los oficiales

Fuente: Ministerio del Interior, Área de descargas de infoelectoral
(https://infoelectoral.interior.gob.es/), ficheros <tipo><año><mes>_MUNI.zip. Se guardan tal cual en
datos/raw/infoelectoral/ y sus hashes están en datos/MANIFEST.sha256. De cada ZIP se usan:

    03xxaamm.DAT  candidaturas (código, siglas y cabeceras de agrupación)
    07xxaamm.DAT  totales por provincia (censo de escrutinio, blancos, nulos, escaños)
    08xxaamm.DAT  votos por candidatura y provincia (ámbito superior al municipio, CERA incluido)

Congreso: cada candidatura oficial se lleva a una columna con datos/candidaturas_oficiales.csv
(p. ej. las confluencias de Podemos a 'Podemos'), que mantiene los nombres que usa el modelo.
Europeas: las marcas regionales de una misma lista (Comuns Sumar, Sumar Galicia…) se suman a su
cabecera nacional.
"""
from __future__ import annotations

import argparse
import csv
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).resolve().parent
RAW = DATOS / "raw"
ZIPS = RAW / "infoelectoral"
MAPA = DATOS / "candidaturas_oficiales.csv"
URL = "https://infoelectoral.interior.gob.es/estaticos/docxl/apliextr/{}_MUNI.zip"

CONGRESO = {"2015-12": "02201512", "2016-06": "02201606", "2019-04": "02201904",
            "2019-11": "02201911", "2023-07": "02202307"}
EUROPEAS = {"2024-06": "07202406"}
# Columnas de las europeas que usa el modelo (siglas oficiales de la cabecera nacional -> nombre)
COLUMNAS_EUROPEAS = {"PP": "PP", "PSOE": "PSOE", "VOX": "Vox", "SUMAR": "Sumar", "PODEMOS": "Podemos",
                     'AGRUPACIÓN DE ELECTORES "SE ACABÓ LA FIESTA"': "SALF"}

INE_PROVINCIA = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alacant/Alicante", "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Illes Balears", "08": "Barcelona", "09": "Burgos", "10": "Cáceres", "11": "Cádiz",
    "12": "Castelló/Castellón", "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca",
    "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva", "22": "Huesca",
    "23": "Jaén", "24": "León", "25": "Lleida", "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga",
    "30": "Murcia", "31": "Navarra", "32": "Ourense", "33": "Asturias", "34": "Palencia", "35": "Las Palmas",
    "36": "Pontevedra", "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia",
    "41": "Sevilla", "42": "Soria", "43": "Tarragona", "44": "Teruel", "45": "Toledo", "46": "València/Valencia",
    "47": "Valladolid", "48": "Bizkaia", "49": "Zamora", "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}


def descargar(codigo: str) -> Path:
    """Descarga el ZIP oficial si no está ya en datos/raw/infoelectoral/."""
    destino = ZIPS / f"{codigo}_MUNI.zip"
    if not destino.exists():
        ZIPS.mkdir(parents=True, exist_ok=True)
        # El servidor corta las conexiones sin cabecera de navegador
        req = urllib.request.Request(URL.format(codigo), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            tmp = destino.with_suffix(".tmp")
            tmp.write_bytes(r.read())
        tmp.replace(destino)
    return destino


def leer(ruta: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Devuelve (candidaturas, totales por provincia, votos provincia x código de candidatura)."""
    z = zipfile.ZipFile(ruta)
    nombres = {n[:2]: n for n in z.namelist() if n.upper().endswith(".DAT")}

    def lineas(tipo):
        return [x for x in z.read(nombres[tipo]).decode("latin-1").splitlines() if x.strip()]

    def provincial(x):   # registro de provincia completa (no CCAA ni total nacional)
        return x[11:13] != "99" and x[13] == "9"

    cand = pd.DataFrame([{"codigo": x[8:14], "siglas": x[14:64].strip(), "denominacion": x[64:214].strip(),
                          "cabecera_nacional": x[226:232]} for x in lineas("03")]).set_index("codigo")
    totales = pd.DataFrame([{"provincia": INE_PROVINCIA[x[11:13]], "censo": int(x[85:93]),
                             "blancos": int(x[125:133]), "votos_nulos": int(x[133:141]),
                             "votos_candidaturas": int(x[141:149]), "diputados": int(x[149:155])}
                            for x in lineas("07") if provincial(x)]).set_index("provincia")
    votos = defaultdict(dict)
    for x in lineas("08"):
        if provincial(x):
            votos[INE_PROVINCIA[x[11:13]]][x[14:20]] = int(x[20:28])
    votos = pd.DataFrame(votos).T.fillna(0).astype(int).reindex(totales.index)
    # Coherencia interna del fichero oficial
    assert len(totales) == 52, f"{ruta.name}: {len(totales)} provincias"
    assert (votos.sum(axis=1) == totales.votos_candidaturas).all(), f"{ruta.name}: votos que no cuadran"
    return cand, totales, votos


def mapa_congreso(eleccion: str) -> pd.DataFrame:
    m = pd.read_csv(MAPA, dtype=str, keep_default_na=False)
    return m[m.eleccion == eleccion].set_index("codigo")


def congreso(eleccion: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(totales, votos por columna del modelo, color/bloque por columna) de una elección al Congreso."""
    _, totales, votos = leer(descargar(CONGRESO[eleccion]))
    m = mapa_congreso(eleccion)
    sin_mapa = [c for c in votos.columns if c not in m.index and votos[c].sum() > 0]
    if sin_mapa:
        raise ValueError(f"{eleccion}: candidaturas sin columna en {MAPA.name}: {sin_mapa}")
    por_columna = votos.T.groupby(m.columna.reindex(votos.columns)).sum().T
    por_columna = por_columna[sorted(por_columna.columns, key=str.lower)]
    estilo = m.drop_duplicates("columna").set_index("columna")[["color", "bloque"]]
    return totales, por_columna, estilo


def escribir_congreso(eleccion: str) -> Path:
    """Escribe datos/raw/congreso_AAAA-MM.csv en el formato que lee datos/cargar.py."""
    totales, votos, estilo = congreso(eleccion)
    cols = list(votos.columns)
    ruta = RAW / f"congreso_{eleccion}.csv"
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#color", "", "", ""] + [estilo.at[c, "color"] for c in cols] + [""])
        w.writerow(["#bloque", "", "", ""] + [estilo.at[c, "bloque"] for c in cols] + [""])
        w.writerow(["provincia", "censo", "votos_nulos", "diputados"] + cols + ["Voto en blanco"])
        for prov in sorted(totales.index):
            t = totales.loc[prov]
            w.writerow([prov, t.censo, t.votos_nulos, t.diputados]
                       + [int(votos.at[prov, c]) or "" for c in cols] + [t.blancos])
    return ruta


def escribir_europeas(eleccion: str = "2024-06") -> Path:
    """datos/raw/europeas_AAAA_provincias.csv: votos por provincia, con las marcas regionales sumadas."""
    cand, totales, votos = leer(descargar(EUROPEAS[eleccion]))
    cabecera = cand.cabecera_nacional.where(cand.cabecera_nacional.isin(cand.index) & (cand.cabecera_nacional != "000000"),
                                            cand.index.to_series())
    agrupado = votos.T.groupby(cabecera.reindex(votos.columns)).sum().T
    agrupado.columns = [COLUMNAS_EUROPEAS.get(cand.at[c, "siglas"], cand.at[c, "siglas"]) for c in agrupado.columns]
    agrupado = agrupado.T.groupby(level=0).sum().T
    agrupado = agrupado[sorted(agrupado.columns, key=lambda c: -agrupado[c].sum())]
    df = totales[["censo", "votos_nulos", "blancos"]].join(agrupado)
    ruta = RAW / f"europeas_{eleccion[:4]}_provincias.csv"
    df.sort_index().to_csv(ruta, index_label="provincia", encoding="utf-8")
    return ruta


def comparar(eleccion: str) -> pd.DataFrame:
    """Casillas (provincia, columna) en que el CSV actual difiere del oficial."""
    sys.path.insert(0, str(DATOS.parent))
    from datos.cargar import cargar
    actual = cargar(eleccion)
    totales, votos, _ = congreso(eleccion)
    a = actual.votos.join(actual.meta[["censo", "votos_nulos", "blancos"]])
    o = votos.join(totales[["censo", "votos_nulos", "blancos"]])
    a, o = a.align(o, fill_value=0)
    d = (o - a).stack()
    d = d[d != 0].rename("oficial_menos_actual").reset_index()
    d.columns = ["provincia", "columna", "oficial_menos_actual"]
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description="Resultados oficiales del Ministerio del Interior")
    ap.add_argument("--comprobar", action="store_true", help="sólo compara con los CSV actuales")
    args = ap.parse_args()
    if args.comprobar:
        for e in CONGRESO:
            d = comparar(e)
            print(f"{e}: {'idéntico' if d.empty else f'{len(d)} casillas distintas'}")
            if not d.empty:
                print(d.to_string(index=False))
        return 0
    for e in CONGRESO:
        print("escrito", escribir_congreso(e).relative_to(DATOS.parent))
    for e in EUROPEAS:
        print("escrito", escribir_europeas(e).relative_to(DATOS.parent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
