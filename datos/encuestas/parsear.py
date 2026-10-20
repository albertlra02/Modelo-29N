"""
Convierte las tablas de Wikipedia (datos/encuestas/raw/*.json, texto TSV
extraído tal cual de la página) en tablas limpias:

  datos/encuestas/nacionales.csv     una fila por encuesta nacional (6 ciclos)
  datos/encuestas/autonomicas.csv    una fila por encuesta autonómica / provincial

Columnas: ciclo, ambito, encuestadora, medio, inicio, fin, n, participacion,
tipo ('encuesta' | 'resultado'), y una columna por partido en % (NaN si no se
publicó). Los nombres de partido se normalizan a etiquetas comunes.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).parent / "raw"
OUT = Path(__file__).parent

MESES = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# Normalización de etiquetas de partido entre tablas
PARTIDOS = {
    "PP": "PP", "PSOE": "PSOE", "PSC": "PSOE", "PSE–EE (PSOE)": "PSOE", "PSdeG–PSOE": "PSOE",
    "Vox": "VOX", "Sumar": "SUMAR", "Podemos": "PODEMOS", "Podem": "PODEMOS",
    # Desde octubre de 2026 Wikipedia separa Frente Amplio (FA) y Compromís-Front Valencià (FV); antes Compromís iba
    # dentro de Sumar. Ambos son el espacio que el modelo llama SUMAR (y que pasa a FRENTE_AMPLIO con las candidaturas
    # registradas, con la lista valenciana incluida).
    "FA": "SUMAR", "FV": "SUMAR",
    "Unidas Podemos": "PODEMOS", "Unidos Podemos": "PODEMOS",
    "IU–UPeC": "IU", "IU-UPeC": "IU", "IU–LV": "IU", "IU-LV": "IU",
    "Más País": "MAS_PAIS", "Compromís": "COMPROMIS",
    "Cs": "CS", "ERC": "ERC", "ERC–Sobiranistes": "ERC", "Junts": "JUNTS", "JxCat": "JUNTS",
    "DiL": "JUNTS", "PDeCAT": "JUNTS",
    "EH Bildu": "BILDU", "PNV": "PNV", "BNG": "BNG", "CCa": "CC", "CC–NCa": "CC", "NCa": "NC",
    "UPN": "UPN", "NA+": "NAV_DCHA", "CUP": "CUP", "PRC": "PRC", "EV": "EV", "SALF": "SALF",
    "Aliança.cat": "ALIANCA", "Adelante Andalucía (2021)": "ADELANTE", "Existe": "TERUEL",
    "CHA": "CHA", "UPL": "UPL", "Ara|Més": "MES", "IE": "IE", "GBai": "GBAI", "CpM": "CPM",
}

FICHEROS_NAC = [
    ("wiki_2015.json", "2015"),
    ("wiki_2016.json", "2016"),
    ("wiki_2019a.json", "2019A"),
    ("wiki_2026_ciclo_2026_listas.json", "2026"),     # desde el registro de candidaturas (FA y FV aparte)
    ("wiki_2026_ciclo_2026.json", "2026"),
    ("wiki_2026_ciclo_2025.json", "2026"),
    ("wiki_2023_final.json", "2023"),
    ("wiki_2019n.json", "2019N"),
]


def _num(v: str) -> float:
    v = (v or "").strip()
    es_cota_superior = v.startswith("<")
    m = re.match(r"^<?\s*([\d.,]+)", v)
    if not m:
        return np.nan
    token = m.group(1)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
        token = token.replace(",", "")              # 1,200 -> 1200
    elif "," in token and "." not in token:
        token = token.replace(",", ".")             # 4,9 -> 4.9
    else:
        token = token.replace(",", "")              # 1,200.5 -> 1200.5
    valor = float(token)
    # Una publicación "<1" aporta un intervalo, no una observación exacta de 1.
    return valor / 2 if es_cota_superior else valor


def _fechas(txt: str, anio_tabla: int | None) -> tuple[date | None, date | None]:
    """'22 Sep–1 Oct', '10–11 Oct', '11 Oct', '30 Apr–7 May 2026', '29 Dec–5 Jan'."""
    t = txt.replace("–", "-").strip()
    m_anio = re.search(r"(\d{4})$", t)
    anio = int(m_anio.group(1)) if m_anio else anio_tabla
    t = re.sub(r"\s*\d{4}$", "", t)
    partes = [p.strip() for p in t.split("-")]
    fin = partes[-1].split()
    if len(fin) != 2 or fin[1] not in MESES or anio is None:
        return None, None
    d_fin = date(anio, MESES[fin[1]], int(fin[0]))
    ini = partes[0].split()
    if len(partes) == 1:
        return d_fin, d_fin
    if len(ini) == 1:  # '10-11 Oct'
        return date(anio, d_fin.month, int(ini[0])), d_fin
    mes_ini = MESES[ini[1]]
    anio_ini = anio - 1 if mes_ini > d_fin.month else anio
    return date(anio_ini, mes_ini, int(ini[0])), d_fin


def _filas(texto: str, ciclo: str, ambito: str, cabecera: list[str], lineas: list[str], anio_col: bool):
    out = []
    for linea in lineas:
        celdas = linea.split("\t")
        if anio_col:
            anio, celdas = int(celdas[0]), celdas[1:]
        else:
            anio = None
        if len(celdas) < 4 or not celdas[0].strip():
            continue
        if len(celdas) != len(cabecera):
            raise ValueError(
                f"{ciclo}/{ambito}: fila con {len(celdas)} columnas; "
                f"se esperaban {len(cabecera)} ({celdas[0]!r})"
            )
        quien, cuando, n, part = celdas[0], celdas[1], celdas[2], celdas[3]
        es_resultado = bool(re.search(r"election", quien, re.I))
        ini, fin = _fechas(cuando, anio)
        firma, _, medio = quien.partition("/")
        fila = {
            "ciclo": ciclo, "ambito": ambito, "encuestadora": firma.strip(), "medio": medio.strip(),
            "inicio": ini, "fin": fin, "n": _num(n), "participacion": _num(part),
            "tipo": "resultado" if es_resultado else "encuesta",
        }
        for nombre, valor in zip(cabecera[4:], celdas[4:]):
            clave = PARTIDOS.get(nombre)
            if clave:
                x = _num(valor)
                fila[clave] = np.nansum([fila.get(clave, np.nan), x]) if not np.isnan(x) else fila.get(clave, np.nan)
        out.append(fila)
    return out


def nacionales() -> pd.DataFrame:
    filas = []
    for fichero, ciclo in FICHEROS_NAC:
        if not (RAW / fichero).exists():          # la tabla posterior al registro sólo existe desde octubre de 2026
            continue
        texto = json.load(open(RAW / fichero, encoding="utf-8"))
        lineas = texto.split("\n")
        cab = lineas[0].split("\t")[1:]
        filas += _filas(texto, ciclo, "España", cab, lineas[1:], anio_col=True)
    df = pd.DataFrame(filas)
    df = df.drop_duplicates()
    return df


def autonomicas() -> pd.DataFrame:
    texto = json.load(open(RAW / "wiki_2026_subnacional.json", encoding="utf-8"))
    filas, cab, ambito, bloque = [], None, None, []
    for linea in texto.split("\n") + ["#FIN\t"]:
        if linea.startswith("#"):
            if cab:
                filas += _filas(texto, "2026", ambito, cab, bloque, anio_col=False)
            partes = linea[1:].split("\t")
            ambito, cab, bloque = partes[0], partes[1:], []
        else:
            bloque.append(linea)
    return pd.DataFrame(filas)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    nac, aut = nacionales(), autonomicas()
    nac.to_csv(OUT / "nacionales.csv", index=False)
    aut.to_csv(OUT / "autonomicas.csv", index=False)
    enc = nac[nac.tipo == "encuesta"]
    print("Nacionales:", len(enc), "encuestas,", enc.encuestadora.nunique(), "encuestadoras")
    print(enc.groupby("ciclo").agg(n=("fin", "size"), desde=("fin", "min"), hasta=("fin", "max")))
    print("Sin fecha:", int(enc.fin.isna().sum()))
    print("Autonómicas:", (aut.tipo == "encuesta").sum(), "encuestas en", aut.ambito.nunique(), "ámbitos")
