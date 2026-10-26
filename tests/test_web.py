"""La web responde en todas sus páginas y en la API con el escenario por defecto.

Se llama a la aplicación ASGI directamente (sin servidor ni dependencias extra). El escenario por
defecto sale de la caché si `python -m scripts.precalcular` ya se ha corrido; si no, se calcula.
"""
import asyncio
import json
from urllib.parse import urlsplit

import pytest

from web import datos as D
from web.servidor import NAV, OTRAS, app


def pedir(url: str, metodo: str = "GET") -> tuple[int, str]:
    partes = urlsplit(url)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo, "scheme": "http",
             "path": partes.path, "raw_path": partes.path.encode(), "query_string": partes.query.encode(),
             "root_path": "", "headers": [(b"host", b"prueba")], "client": ("127.0.0.1", 1), "server": ("prueba", 80)}
    estado, cuerpo, leido = {}, [], []

    async def recibir():
        if not leido:
            leido.append(True)
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()     # el cliente no se desconecta (las respuestas de fichero lo escuchan)

    async def enviar(m):
        if m["type"] == "http.response.start":
            estado["codigo"] = m["status"]
        elif m["type"] == "http.response.body":
            cuerpo.append(m.get("body", b""))

    asyncio.run(app(scope, recibir, enviar))
    return estado["codigo"], b"".join(cuerpo).decode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def escenario_calculado():
    D.correr(D.Params().escenario())


@pytest.mark.parametrize("ruta", [r for r, _ in NAV if r not in ("/evolucion", "/participacion")] + OTRAS)
def test_paginas_responden(ruta):
    codigo, html = pedir(ruta)
    assert codigo == 200
    assert ('aria-current="page"' in html) == (ruta not in OTRAS)       # las de fuera del menú no se marcan
    assert "Hay que calcular" not in html


@pytest.mark.parametrize("ruta,tarea", [("/evolucion", "evolucion"), ("/participacion", "barrido")])
def test_paginas_largas_responden_o_piden_calcular(ruta, tarea):
    codigo, html = pedir(ruta)
    assert codigo == 200
    assert ("Hay que calcular" in html) == bool(D.pendientes(D.Params(), tarea))


def test_parametros_no_validos_vuelven_al_escenario_por_defecto():
    p = D.Params.de_query({"fecha": "1999-01-01", "cand": "x", "part": "900", "sim": "7", "semilla": "-3"})
    assert p == D.Params(participacion=D.PARTICIPACION_MAX, semilla=0)
    assert D.Params.de_query({"reparto": "simetrico"}).reparto == "historico"   # sin efecto al 65 %
    assert D.Params().query() == ""
    assert D.Params().query(candidaturas="lista_unica") == "?cand=lista_unica"


def test_api_mapa_y_encuestas():
    for modo in ("ganador", "partido", "cambios"):
        codigo, cuerpo = pedir(f"/api/mapa?modo={modo}&partido=VOX")
        assert codigo == 200
        assert json.loads(json.loads(cuerpo)["fig"])["data"]
    codigo, cuerpo = pedir("/api/encuestas?partidos=PP,VOX&desde=2025-07-01")
    assert codigo == 200 and json.loads(json.loads(cuerpo)["fig"])["data"]
    codigo, _ = pedir("/api/casas?partido=PSOE")
    assert codigo == 200


def test_api_provincia():
    codigo, cuerpo = pedir("/api/provincia?nombre=Madrid")
    assert codigo == 200
    html = json.loads(cuerpo)["html"]
    assert "Madrid" in html and "dist__barra" in html
    # en Madrid ningún reparto concreto se repite lo bastante: no se enseñan; en Soria (4 escaños), sí
    assert "Repartos más probables" not in html
    assert "Repartos más probables" in json.loads(pedir("/api/provincia?nombre=Soria")[1])["html"]
    codigo, _ = pedir("/api/provincia?nombre=Atlantis")
    assert codigo == 404


def test_resultados_2023_reproducen_el_congreso():
    _, esc = D.resultados_2023()
    assert esc.to_numpy().sum() == 350
    assert esc["PP"].sum() == 137 and esc["PSOE"].sum() == 121


def test_api_calcular_sin_pendientes():
    codigo, cuerpo = pedir("/api/calcular?tarea=escenario", "POST")
    assert codigo == 200 and json.loads(cuerpo)["pendientes"] == 0
    assert pedir("/api/calcular?tarea=otra", "POST")[0] == 400


def test_descarga_y_errores():
    codigo, csv = pedir("/descargar/simulaciones.csv")
    assert codigo == 200 and len(csv.splitlines()) == D.N_SIM + 1
    assert pedir("/no-existe")[0] == 404
    assert pedir("/estatico/plotly.min.js")[0] == 200


def test_api_simulador_y_paginas_nuevas():
    codigo, cuerpo = pedir("/api/simulador?v_PP=36&v_VOX=15")
    assert codigo == 200
    j = json.loads(cuerpo)
    assert abs(j["votos"]["PP"] - 36) < 0.05 and "Frente a la proyección" in j["html"]
    codigo, html = pedir("/simulador?v_PP=36")
    assert codigo == 200 and "fijado" in html
    codigo, html = pedir("/comparar?b_cand=lista_unica")
    assert codigo == 200 and "Escenario B" in html
