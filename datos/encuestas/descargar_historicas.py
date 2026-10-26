"""Descarga de forma reproducible las encuestas nacionales históricas.

Las páginas se fijan por ``oldid`` para que una edición posterior de Wikipedia
no cambie silenciosamente el conjunto de calibración.  El resultado se guarda
como TSV dentro de un JSON, el mismo formato intermedio usado por el resto de
las encuestas del proyecto.

Uso::

    python datos/encuestas/descargar_historicas.py

Requiere conexión a Internet.  No forma parte del arranque normal de la app.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


RAW = Path(__file__).with_name("raw")
USER_AGENT = "ModeloElectoral/1.0 (importador reproducible de datos públicos)"


@dataclass(frozen=True)
class Fuente:
    ciclo: str
    anio: int
    titulo: str
    oldid: int
    fichero: str
    partidos: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"https://en.wikipedia.org/w/index.php?title={self.titulo}&oldid={self.oldid}"


FUENTES = (
    Fuente(
        "2015", 2015,
        "Opinion_polling_for_the_2015_Spanish_general_election",
        1377201395,
        "wiki_2015.json",
        ("PP", "PSOE", "IU–UPeC", "UPyD", "CiU", "EH Bildu", "PNV", "ERC–CatSí",
         "BNG", "CC", "Compromís", "Cs", "Podemos", "DiL"),
    ),
    Fuente(
        "2016", 2016,
        "Opinion_polling_for_the_2016_Spanish_general_election",
        1377201436,
        "wiki_2016.json",
        ("PP", "PSOE", "Podemos", "Cs", "IU–UPeC", "ERC–CatSí", "DiL", "PNV",
         "PACMA", "EH Bildu", "CC", "Unidos Podemos"),
    ),
    Fuente(
        "2019A", 2019,
        "Opinion_polling_for_the_April_2019_Spanish_general_election",
        1377201530,
        "wiki_2019a.json",
        ("PP", "PSOE", "Unidas Podemos", "Cs", "ERC–Sobiranistes", "PDeCAT", "PNV",
         "PACMA", "EH Bildu", "CCa", "Vox", "Compromís", "JxCat", "NA+"),
    ),
)


@dataclass
class Celda:
    etiqueta: str
    colspan: int = 1
    rowspan: int = 1
    textos: list[str] = field(default_factory=list)
    imagenes: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return " ".join(" ".join(self.textos).split())


class _PrimeraTablaEncuestas(HTMLParser):
    """Extrae la primera tabla ``wikitable`` sin dependencias de HTML externas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.en_tabla = False
        self.terminada = False
        self.profundidad_tabla = 0
        self.en_fila = False
        self.celda: Celda | None = None
        self.fila: list[Celda] = []
        self.filas: list[list[Celda]] = []
        self.ignorar = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        atr = dict(attrs)
        if tag == "table":
            if not self.en_tabla and not self.terminada and "wikitable" in atr.get("class", "").split():
                self.en_tabla = True
                self.profundidad_tabla = 1
            elif self.en_tabla:
                self.profundidad_tabla += 1
            return
        if not self.en_tabla or self.profundidad_tabla != 1:
            return
        if tag == "tr":
            self.en_fila = True
            self.fila = []
        elif tag in {"th", "td"} and self.en_fila:
            self.celda = Celda(
                tag,
                max(1, int(atr.get("colspan", "1"))),
                max(1, int(atr.get("rowspan", "1"))),
            )
        elif tag in {"sup", "style", "script"} and self.celda is not None:
            self.ignorar += 1
        elif tag == "img" and self.celda is not None:
            alt = atr.get("alt", "").strip()
            if alt:
                self.celda.imagenes.append(alt)
        elif tag == "br" and self.celda is not None and not self.ignorar:
            self.celda.textos.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.en_tabla:
            return
        if tag == "table":
            self.profundidad_tabla -= 1
            if self.profundidad_tabla == 0:
                self.en_tabla = False
                self.terminada = True
            return
        if self.profundidad_tabla != 1:
            return
        if tag in {"sup", "style", "script"} and self.celda is not None and self.ignorar:
            self.ignorar -= 1
        elif tag in {"th", "td"} and self.celda is not None:
            self.fila.append(self.celda)
            self.celda = None
            self.ignorar = 0
        elif tag == "tr" and self.en_fila:
            if self.fila:
                self.filas.append(self.fila)
            self.en_fila = False

    def handle_data(self, data: str) -> None:
        if self.celda is not None and not self.ignorar and self.profundidad_tabla == 1:
            self.celda.textos.append(data)


def _nombre_cabecera(celda: Celda) -> str:
    texto = celda.texto.strip()
    if texto:
        return texto
    imagenes = [x for x in celda.imagenes if x and x.lower() != "logo"]
    return imagenes[0] if imagenes else ""


def _expandir_fila(
    fila: list[Celda],
    pendientes: dict[int, tuple[int, Celda]],
    ancho: int,
) -> list[Celda]:
    """Expande ``rowspan``/``colspan`` conservando la cuadrícula de la tabla."""
    salida: list[Celda] = []
    columna = 0

    def incorporar_pendientes() -> None:
        nonlocal columna
        while columna in pendientes:
            restantes, celda = pendientes[columna]
            salida.append(celda)
            if restantes <= 1:
                del pendientes[columna]
            else:
                pendientes[columna] = (restantes - 1, celda)
            columna += 1

    for celda in fila:
        incorporar_pendientes()
        for desplazamiento in range(celda.colspan):
            copia = celda if desplazamiento == 0 else Celda(celda.etiqueta)
            salida.append(copia)
            if celda.rowspan > 1:
                pendientes[columna + desplazamiento] = (celda.rowspan - 1, copia)
        columna += celda.colspan
    incorporar_pendientes()
    while columna < ancho and columna in pendientes:
        incorporar_pendientes()
    return salida


def extraer_tsv(html: str, anio: int, partidos: tuple[str, ...] | None = None, min_filas: int = 20) -> str:
    """Convierte la primera tabla nacional de la página a TSV estable."""
    p = _PrimeraTablaEncuestas()
    p.feed(html)
    if not p.filas:
        raise ValueError("no se encontró ninguna tabla wikitable")

    cabeceras = [_nombre_cabecera(c) for c in p.filas[0]]
    if cabeceras[:4] != ["Polling firm/Commissioner", "Fieldwork date", "Sample size", "Turnout"]:
        raise ValueError(f"cabecera inesperada: {cabeceras[:4]!r}")
    if cabeceras[-1] != "Lead":
        raise ValueError(f"última cabecera inesperada: {cabeceras[-1]!r}")
    if partidos is not None:
        if len(cabeceras) != len(partidos) + 5:
            raise ValueError(
                f"la fuente tiene {len(cabeceras) - 5} columnas de partido; "
                f"se esperaban {len(partidos)}"
            )
        # Los logotipos históricos llegan con algunos textos dañados desde el
        # renderizador de revisiones antiguas. Su orden sí es estable y se fija
        # explícitamente para no depender del texto alternativo de una imagen.
        cabeceras = cabeceras[:4] + list(partidos) + ["Lead"]
    elif any(not x for x in cabeceras):
        detalle = [(c.texto, c.imagenes) for c in p.filas[0]]
        raise ValueError(f"cabecera incompleta: {cabeceras!r}; detalle={detalle!r}")

    lineas = ["year\t" + "\t".join(cabeceras[:-1])]
    pendientes: dict[int, tuple[int, Celda]] = {}
    for fila in p.filas[1:]:
        if not fila or fila[0].etiqueta != "td":
            continue
        valores = [c.texto for c in _expandir_fila(fila, pendientes, len(cabeceras))]
        if len(valores) != len(cabeceras):
            raise ValueError(
                f"fila con {len(valores)} columnas; se esperaban {len(cabeceras)}: {valores[:3]!r}"
            )
        # La última columna es sólo la ventaja del ganador; el motor no la usa.
        valores = [re.sub(r"\s+", " ", x).strip() for x in valores[:-1]]
        lineas.append(str(anio) + "\t" + "\t".join(valores))
    if len(lineas) - 1 < min_filas:
        raise ValueError(f"tabla anormalmente corta: {len(lineas) - 1} filas")
    return "\n".join(lineas)


def descargar(fuente: Fuente, destino: Path = RAW) -> Path:
    peticion = Request(fuente.url, headers={"User-Agent": USER_AGENT})
    with urlopen(peticion, timeout=60) as respuesta:
        html = respuesta.read().decode("utf-8")
    tsv = extraer_tsv(html, fuente.anio, fuente.partidos)
    ruta = destino / fuente.fichero
    ruta.write_text(json.dumps(tsv, ensure_ascii=False), encoding="utf-8")
    return ruta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciclo", choices=[f.ciclo for f in FUENTES], action="append")
    args = parser.parse_args()
    elegidas = [f for f in FUENTES if not args.ciclo or f.ciclo in args.ciclo]
    for fuente in elegidas:
        ruta = descargar(fuente)
        filas = len(json.loads(ruta.read_text(encoding="utf-8")).splitlines()) - 1
        print(f"{fuente.ciclo}: {filas} filas -> {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
