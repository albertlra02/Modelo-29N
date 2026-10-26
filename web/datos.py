"""
Datos de la web: parámetros del escenario (leídos de la URL), cálculo con caché en memoria y en
disco, y las tablas que pinta cada página. Aquí no hay HTML.

La caché en disco es la de interfaz/calculo.py (la misma que llena `python -m scripts.precalcular`).
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from urllib.parse import urlencode

import pandas as pd

from datos.cargar import cargar
from interfaz import graficos as G
from interfaz.calculo import (BARRIDO, N_SIM, N_SIM_BARRIDO, SEMILLA, en_disco, escenario, fechas_semanales,
                              huella_modelo, limpiar_cache, normalizar)
from interfaz.estilo import nombre
from motor.agregador import agregar, preparar
from motor.escanos import dhondt_exacto
from motor.pipeline import DERECHA, ELECCION, PART_BASE, REPARTOS, SOCIOS_2023, Escenario, piezas_centrales
from motor.palancas import AMBITOS, LIMITE_MOV, LIMITE_UTIL, Palancas
from motor.proyeccion import FECHA

FECHAS = fechas_semanales()
VERSION = huella_modelo()
ULTIMA_ENCUESTA = date.fromisoformat(FECHA)
DIAS_CALIBRADOS = 48   # los errores del Monte Carlo están medidos hasta 48 días antes de votar
# En la web publicada (plan gratuito, 512 MB) se limita con MAX_SIM: 10.000 simulaciones piden unos 630 MB
SIMULACIONES = tuple(n for n in (2000, 5000, 10000) if n <= int(os.environ.get("MAX_SIM", 10_000)))
PARTICIPACION_MIN, PARTICIPACION_MAX = 60, 76
PARTIDOS_ENCUESTAS = ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "SALF"]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
NOMBRES_CAND = {"registradas": "Candidaturas registradas", "lista_unica": "Hipótesis de lista única"}
DETALLE_CAND = {
    "registradas": "Frente Amplio y Podemos por separado; Podemos dentro de ERC en Cataluña y en listas "
                   "conjuntas con el Frente Amplio en la C. Valenciana y Canarias.",
    "lista_unica": "Lo que no ha pasado: Frente Amplio y Podemos en una sola lista en toda España.",
}
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
ATAJOS = {
    "PP + Vox": ["PP", "VOX"],
    "Toda la derecha": DERECHA,
    "Bloque de 2023": SOCIOS_2023 + ["FRENTE_AMPLIO"],
    "PSOE y su izquierda": ["PSOE", "SUMAR", "PODEMOS", "FRENTE_AMPLIO"],
}
ESCENARIOS_SENADO = {   # clave de las probabilidades del Senado -> texto (las primeras, las que se comparan)
    "P(PP + Vox tres quintos)": "PP y Vox, tres quintos del pleno (160)",
    "P(PP + Vox + UPN mayoría absoluta)": "PP, Vox y UPN, mayoría absoluta del pleno (134)",
    "P(izquierda mayoría absoluta)": "La izquierda, mayoría absoluta del pleno",
    "P(PP + Vox ≥ 105)": "PP y Vox tienen la mitad de los electos",
    "P(izquierda ≥ 105)": "La izquierda tiene la mitad de los electos",
    "P(PP mayoría absoluta)": "El PP solo, mayoría absoluta del pleno",
    "P(PP mayoría absoluta sin coalición)": "El PP solo, si no hubiera coalición",
    "P(PP ≥ 105)": "El PP solo tiene la mitad de los electos",
    "P(PP ≥ 105 sin coalición)": "El PP solo, si no hubiera coalición",
    "P(izquierda ≥ 105 sin coalición)": "La izquierda, si no hubiera coalición",
}
ESCENARIOS = {   # clave de Resultado.probs -> texto
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
    return f"{int(n):,}".replace(",", ".")


# ------------------------------------------------------------------ parámetros del escenario (URL)

CLAVES_URL = {"fecha": "fecha", "candidaturas": "cand", "participacion": "part", "reparto": "reparto",
              "n_sim": "sim", "semilla": "semilla",
              "mov_izda": "mov_izda", "mov_dcha": "mov_dcha", "mov_nac": "mov_nac", "mov_ambito": "ambito",
              "util_pod_fa": "util_pod_fa", "util_fa_psoe": "util_fa_psoe", "util_vox_pp": "util_vox_pp",
              "util_salf_vox": "util_salf_vox", "util_donde": "util_donde"}
NOMBRES_MOV = {"mov_izda": "Izquierda", "mov_dcha": "Derecha", "mov_nac": "Nacionalistas y regionalistas"}
DETALLE_MOV = {"mov_izda": "PSOE, Frente Amplio, Podemos y Adelante", "mov_dcha": "PP, Vox, SALF y UPN",
               "mov_nac": "ERC, Junts, EH Bildu, PNV, BNG, CC, NC y locales"}
NOMBRES_UTIL = {"util_pod_fa": "Podemos → Frente Amplio", "util_fa_psoe": "Frente Amplio → PSOE",
                "util_vox_pp": "Vox → PP", "util_salf_vox": "SALF → Vox"}
NOMBRES_DONDE = {"sin_escano": "Sólo donde el partido de origen no saca escaño", "todas": "En todas las provincias"}


def _entero(v, defecto: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


@dataclass(frozen=True)
class Params:
    fecha: str = FECHAS[-1]
    candidaturas: str = "registradas"
    participacion: int = round(100 * PART_BASE)     # % entero
    reparto: str = "historico"
    n_sim: int = N_SIM
    semilla: int = SEMILLA
    mov_izda: int = 0              # palancas (motor/palancas.py), en %
    mov_dcha: int = 0
    mov_nac: int = 0
    mov_ambito: str = "España"
    util_pod_fa: int = 0
    util_fa_psoe: int = 0
    util_vox_pp: int = 0
    util_salf_vox: int = 0
    util_donde: str = "sin_escano"

    @classmethod
    def de_query(cls, q) -> Params:
        """Lee el escenario de la URL; cualquier valor no válido vuelve al de por defecto."""
        b = cls()
        part = min(max(_entero(q.get("part"), b.participacion), PARTICIPACION_MIN), PARTICIPACION_MAX)
        reparto = q.get("reparto") if q.get("reparto") in REPARTOS else b.reparto
        if part == b.participacion:          # con la participación base el reparto no influye
            reparto = b.reparto
        n = _entero(q.get("sim"), b.n_sim)

        def acotado(k, lim, minimo):
            return min(max(_entero(q.get(k), 0), minimo), lim)
        palancas = {k: acotado(k, LIMITE_MOV, -LIMITE_MOV) for k in NOMBRES_MOV}
        palancas |= {k: acotado(k, LIMITE_UTIL, 0) for k in NOMBRES_UTIL}
        palancas["mov_ambito"] = q.get("ambito") if q.get("ambito") in AMBITOS else b.mov_ambito
        palancas["util_donde"] = q.get("util_donde") if q.get("util_donde") in NOMBRES_DONDE else b.util_donde
        if not any(palancas[k] for k in NOMBRES_MOV):        # sin movilización el ámbito no influye
            palancas["mov_ambito"] = b.mov_ambito
        if not any(palancas[k] for k in NOMBRES_UTIL):
            palancas["util_donde"] = b.util_donde
        return cls(**palancas,
            fecha=q.get("fecha") if q.get("fecha") in FECHAS else b.fecha,
            candidaturas=q.get("cand") if q.get("cand") in NOMBRES_CAND else b.candidaturas,
            participacion=part, reparto=reparto,
            n_sim=n if n in SIMULACIONES else b.n_sim,
            semilla=max(0, _entero(q.get("semilla"), b.semilla)),
        )

    def query(self, **cambios) -> str:
        """'?clave=valor…' con sólo lo que difiere del escenario por defecto ('' si es el de por defecto)."""
        p, b = replace(self, **cambios), Params()
        pares = [(url, getattr(p, k)) for k, url in CLAVES_URL.items() if getattr(p, k) != getattr(b, k)]
        return "?" + urlencode(pares) if pares else ""

    @property
    def es_base(self) -> bool:
        return self == Params()

    def escenario(self, **cambios) -> Escenario:
        pal = Palancas(self.mov_izda, self.mov_dcha, self.mov_nac, self.mov_ambito, self.util_pod_fa,
                       self.util_fa_psoe, self.util_vox_pp, self.util_salf_vox, self.util_donde == "sin_escano")
        e = Escenario(fecha=self.fecha, candidaturas=self.candidaturas, participacion=self.participacion / 100,
                      reparto=self.reparto, n_sim=self.n_sim, semilla=self.semilla, palancas=pal)
        return replace(e, **cambios)

    def descripcion(self) -> list[str]:
        out = [f"Encuestas hasta el {fecha_larga(self.fecha)}", NOMBRES_CAND[self.candidaturas],
               f"Participación del {self.participacion} %"]
        sitio = "" if self.mov_ambito == "España" else f" en {self.mov_ambito}"
        out += [f"{NOMBRES_MOV[k]} {getattr(self, k):+d} %{sitio}" for k in NOMBRES_MOV if getattr(self, k)]
        donde = " (donde no saca escaño)" if self.util_donde == "sin_escano" else ""
        out += [f"{NOMBRES_UTIL[k]}: {getattr(self, k)} %{donde}" for k in NOMBRES_UTIL if getattr(self, k)]
        return out + [f"{miles(self.n_sim)} simulaciones"]


# ------------------------------------------------------------------ cálculo (memoria + disco)

_CANDADO = threading.Lock()                 # un cálculo a la vez: numpy ya usa todos los núcleos
_MEMORIA: OrderedDict[Escenario, dict] = OrderedDict()
_MAX_MEMORIA = 64
_centrales = lru_cache(maxsize=24)(piezas_centrales)


def iniciar() -> None:
    limpiar_cache(VERSION)


def calculado(esc: Escenario) -> bool:
    esc = normalizar(esc)
    return esc in _MEMORIA or en_disco(esc, VERSION)


def correr(esc: Escenario) -> dict:
    """Resumen del escenario (interfaz/calculo.py): de memoria, de disco o calculándolo."""
    esc = normalizar(esc)
    with _CANDADO:
        if esc in _MEMORIA:
            _MEMORIA.move_to_end(esc)
            return _MEMORIA[esc]
        d = escenario(esc, VERSION, centrales=_centrales)
        _MEMORIA[esc] = d
        while len(_MEMORIA) > _MAX_MEMORIA:
            _MEMORIA.popitem(last=False)
        return d


TAREAS = ("escenario", "evolucion", "barrido")


def escenarios_de(p: Params, tarea: str) -> list[Escenario]:
    """Escenarios que necesita una página: el elegido, la serie semanal o el barrido de participación."""
    if tarea == "evolucion":
        return [p.escenario(fecha=f) for f in FECHAS]
    if tarea == "barrido":
        return [p.escenario(candidaturas=c, participacion=x, n_sim=N_SIM_BARRIDO) for x in BARRIDO for c in NOMBRES_CAND]
    return [p.escenario()]


def pendientes(p: Params, tarea: str) -> list[Escenario]:
    return [e for e in escenarios_de(p, tarea) if not calculado(e)]


def texto_tarea(esc: Escenario, tarea: str) -> str:
    if tarea == "evolucion":
        return f"Calculando la semana del {fecha_larga(esc.fecha)}…"
    if tarea == "barrido":
        return f"Calculando la participación del {round(100 * esc.participacion)} % ({NOMBRES_CAND[esc.candidaturas]})…"
    return f"Simulando {miles(esc.n_sim)} elecciones…"


# ------------------------------------------------------------------ piezas derivadas

@lru_cache(maxsize=6)
def encuestas(fecha: str) -> tuple[pd.DataFrame, dict]:
    """Encuestas usables hasta la fecha y media del agregador por partido."""
    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    enc = preparar(nac[nac.ciclo == "2026"], fecha)
    return enc, {x: agregar(enc, x, fecha) for x in PARTIDOS_ENCUESTAS}


@lru_cache(maxsize=1)
def _encuestas_brutas() -> pd.DataFrame:
    nac = pd.read_csv("datos/encuestas/nacionales.csv", parse_dates=["fin"])
    return nac[(nac.ciclo == "2026") & (nac.tipo == "encuesta")]


def resumen_encuestas(fecha: str) -> dict:
    """Recuento rápido (sin correr el agregador) para la portada."""
    e = _encuestas_brutas()
    e = e[e.fin <= pd.Timestamp(fecha)].sort_values("fin")
    ult = e.iloc[-1]
    return {"n": len(e), "casas": e.encuestadora.nunique(), "ultima_casa": ult.encuestadora,
            "ultima_fecha": fecha_larga(ult.fin)}


def evolucion(p: Params) -> dict:
    return _evolucion(replace(p, fecha=FECHAS[-1]))


@lru_cache(maxsize=8)
def _evolucion(p: Params) -> dict:
    reps, probs, medianas = {}, {}, {}
    for f in FECHAS:
        d = correr(p.escenario(fecha=f))
        reps[f] = G.reparto_representativo(d["sim"])
        probs[f] = d["probs"]
        medianas[f] = d["sim"].median()
    return {"reps": reps, "probs": pd.DataFrame(probs).T, "medianas": pd.DataFrame(medianas).T}


@lru_cache(maxsize=6)
def barrido(p: Params) -> pd.DataFrame:
    filas = []
    for esc in escenarios_de(p, "barrido"):
        d = correr(esc)
        filas.append({"participacion": esc.participacion, "candidaturas": NOMBRES_CAND[esc.candidaturas],
                      "P(mayoría PP + Vox)": d["probs"]["P(PP + Vox ≥ 176)"],
                      "P(investidura tipo 2023)": d["probs"]["P(bloque de investidura 2023 ≥ 176)"],
                      "P(PSOE primero)": d["probs"]["P(PSOE primero)"],
                      "PP + Vox (mediana)": float(d["ppvox"].median())})
    return pd.DataFrame(filas)


# Candidatura del modelo -> candidatura de 2023 que se le compara (sólo las que son la misma lista).
# Frente Amplio y Podemos no tienen equivalente: en 2023 iban juntos dentro de Sumar.
EQUIVALENTES_2023 = {"PP": "PP", "PSOE": "PSOE", "VOX": "VOX", "ERC": "ERC", "JUNTS": "JUNTS",
                     "BILDU": "EH BILDU", "PNV": "PNV", "BNG": "BNG", "CC": "CC", "NC": "NC", "UPN": "UPN",
                     "UPL": "UPL", "TERUEL": "Teruel Existe", "SORIA_YA": "Soria ¡Ya!", "ADELANTE": "Adelante And."}


@lru_cache(maxsize=1)
def pesos_2023() -> pd.Series:
    """Votos válidos de 2023 por provincia: el peso de cada una en la media nacional."""
    return cargar("2023-07").validos


@lru_cache(maxsize=1)
def resultados_2023() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Congreso de julio de 2023 por provincia: % de votos válidos y escaños de cada candidatura."""
    b = cargar("2023-07")
    pct = 100 * b.votos.div(b.validos, axis=0)
    esc = pd.DataFrame([dhondt_exacto(b.votos.loc[x].to_dict(), int(b.meta.at[x, "diputados"]),
                                      int(b.meta.at[x, "blancos"])) for x in b.votos.index],
                       index=b.votos.index)
    return pct, esc


def visibles(d: dict) -> list[str]:
    """Partidos que se muestran (con escaño o con al menos un 1 % de voto), ordenados por voto."""
    tabla, voto = d["tabla"], d["voto"]
    orden = list(tabla.sort_values("voto_%", ascending=False).index)
    return [x for x in orden if tabla.at[x, "media"] >= 0.5 or voto.at[x, "mediana"] >= 1]


def dias_hasta(fecha) -> int:
    return int((ELECCION - pd.Timestamp(fecha)).days)


def quienes(partidos: list[str]) -> str:
    n = [nombre(x) for x in partidos]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " y " + n[-1]
