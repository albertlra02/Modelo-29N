"""
Datos de la web: parámetros del escenario (leídos de la URL), cálculo con caché en memoria y en
disco, y las tablas que pinta cada página. Aquí no hay HTML.

La caché en disco es la de interfaz/calculo.py (la misma que llena `python -m scripts.precalcular`).
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from urllib.parse import urlencode

import pandas as pd

from interfaz import graficos as G
from interfaz.calculo import (BARRIDO, N_SIM, N_SIM_BARRIDO, SEMILLA, en_disco, escenario, fechas_semanales,
                              huella_modelo, limpiar_cache, normalizar)
from interfaz.estilo import nombre
from motor.agregador import agregar, preparar
from motor.pipeline import DERECHA, ELECCION, PART_BASE, REPARTOS, SOCIOS_2023, Escenario, piezas_centrales
from motor.proyeccion import FECHA

FECHAS = fechas_semanales()
VERSION = huella_modelo()
ULTIMA_ENCUESTA = date.fromisoformat(FECHA)
DIAS_CALIBRADOS = 48   # los errores del Monte Carlo están medidos hasta 48 días antes de votar
SIMULACIONES = (2000, 5000, 10000)
PARTICIPACION_MIN, PARTICIPACION_MAX = 60, 76
PARTIDOS_ENCUESTAS = ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "SALF"]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
NOMBRES_CAND = {"separados": "Sumar y Podemos por separado", "frente_amplio": "Frente Amplio"}
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
              "n_sim": "sim", "semilla": "semilla"}


def _entero(v, defecto: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


@dataclass(frozen=True)
class Params:
    fecha: str = FECHAS[-1]
    candidaturas: str = "separados"
    participacion: int = round(100 * PART_BASE)     # % entero
    reparto: str = "historico"
    n_sim: int = N_SIM
    semilla: int = SEMILLA

    @classmethod
    def de_query(cls, q) -> Params:
        """Lee el escenario de la URL; cualquier valor no válido vuelve al de por defecto."""
        b = cls()
        part = min(max(_entero(q.get("part"), b.participacion), PARTICIPACION_MIN), PARTICIPACION_MAX)
        reparto = q.get("reparto") if q.get("reparto") in REPARTOS else b.reparto
        if part == b.participacion:          # con la participación base el reparto no influye
            reparto = b.reparto
        n = _entero(q.get("sim"), b.n_sim)
        return cls(
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
        e = Escenario(fecha=self.fecha, candidaturas=self.candidaturas, participacion=self.participacion / 100,
                      reparto=self.reparto, n_sim=self.n_sim, semilla=self.semilla)
        return replace(e, **cambios)

    def descripcion(self) -> list[str]:
        return [f"Encuestas hasta el {fecha_larga(self.fecha)}", NOMBRES_CAND[self.candidaturas],
                f"Participación del {self.participacion} %", f"{miles(self.n_sim)} simulaciones"]


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
