"""Contraseña y veda de la web publicada (web/acceso.py)."""
import asyncio
from datetime import datetime

from web import acceso
from web.servidor import app


def pedir(ruta: str, metodo: str = "GET", cuerpo: bytes = b"", cabeceras: dict | None = None):
    """Llama a la aplicación ASGI y devuelve (código, cabeceras, cuerpo)."""
    ruta, _, consulta = ruta.partition("?")
    h = [(b"host", b"prueba")] + [(k.encode(), v.encode()) for k, v in (cabeceras or {}).items()]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo, "scheme": "http",
             "path": ruta, "raw_path": ruta.encode(), "query_string": consulta.encode(), "root_path": "",
             "headers": h, "client": ("127.0.0.1", 1), "server": ("prueba", 80)}
    out, leido = {"cuerpo": b""}, []

    async def recibir():
        if not leido:
            leido.append(True)
            return {"type": "http.request", "body": cuerpo, "more_body": False}
        await asyncio.Event().wait()

    async def enviar(m):
        if m["type"] == "http.response.start":
            out["codigo"] = m["status"]
            out["cabeceras"] = {k.decode(): v.decode() for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            out["cuerpo"] += m.get("body", b"")

    asyncio.run(app(scope, recibir, enviar))
    cuerpo = out["cuerpo"]
    if out["cabeceras"].get("content-encoding") == "gzip":
        import gzip
        cuerpo = gzip.decompress(cuerpo)
    return out["codigo"], out["cabeceras"], cuerpo.decode("utf-8")


def test_veda_sólo_en_la_web_publicada(monkeypatch):
    dentro = datetime(2026, 11, 26, 12, tzinfo=acceso.MADRID)
    fuera = datetime(2026, 11, 29, 21, 30, tzinfo=acceso.MADRID)
    monkeypatch.delenv("VEDA", raising=False)
    monkeypatch.delenv("PUBLICADO", raising=False)
    assert not acceso.en_veda(dentro)                  # en local nunca se cierra
    monkeypatch.setenv("PUBLICADO", "1")
    assert acceso.en_veda(dentro) and not acceso.en_veda(fuera)
    monkeypatch.setenv("VEDA", "no")
    assert not acceso.en_veda(dentro)
    monkeypatch.setenv("VEDA", "si")
    assert acceso.en_veda(fuera)


def test_entrar_sólo_con_contraseña(monkeypatch):
    monkeypatch.delenv("PUBLICADO", raising=False)
    monkeypatch.delenv("VEDA", raising=False)
    monkeypatch.setenv("CLAVE", "secreta")
    codigo, _, html = pedir("/metodologia")
    assert codigo == 401 and 'type="password"' in html and "usuario" not in html.lower()
    assert pedir("/salud")[0] == 200
    assert pedir("/api/mapa")[0] == 401
    codigo, _, html = pedir("/entrar?siguiente=/metodologia", "POST", b"clave=otra",
                            {"content-type": "application/x-www-form-urlencoded"})
    assert codigo == 401 and "incorrecta" in html
    codigo, cab, _ = pedir("/entrar?siguiente=/metodologia", "POST", b"clave=secreta",
                           {"content-type": "application/x-www-form-urlencoded"})
    assert codigo == 303 and cab["location"] == "/metodologia" and "acceso29n=" in cab["set-cookie"]
    galleta = cab["set-cookie"].split(";")[0]
    assert pedir("/metodologia", cabeceras={"cookie": galleta})[0] == 200
    assert pedir("/metodologia", cabeceras={"cookie": "acceso29n=falsa"})[0] == 401


def test_no_redirige_fuera():
    assert acceso.siguiente_seguro("https://otra.web") == "/"
    assert acceso.siguiente_seguro("//otra.web") == "/"
    assert acceso.siguiente_seguro("/senado?part=74") == "/senado?part=74"


def test_la_web_se_cierra_en_veda(monkeypatch):
    monkeypatch.delenv("CLAVE", raising=False)
    monkeypatch.setenv("VEDA", "si")
    codigo, _, html = pedir("/metodologia")
    assert codigo == 503 and "veda electoral" in html


def test_compresion_y_paginas_en_memoria(monkeypatch):
    import gzip

    from web.servidor import app as aplicacion
    monkeypatch.delenv("CLAVE", raising=False)
    monkeypatch.delenv("VEDA", raising=False)
    monkeypatch.setenv("PUBLICADO", "1")
    codigo, cab, _ = pedir("/participacion", cabeceras={"accept-encoding": "gzip"})
    assert codigo == 200 and cab.get("content-encoding") == "gzip"
    memoria = next(m for m in _middlewares(aplicacion) if m.__class__.__name__ == "PaginasEnMemoria")
    claves = [k for k in memoria.guardadas if k[0] == "/participacion"]
    assert claves and gzip.decompress(memoria.guardadas[claves[0]][3]).startswith(b"<!doctype html>")


def _middlewares(aplicacion):
    capa, out = aplicacion.middleware_stack, []
    while capa is not None:
        out.append(capa)
        capa = getattr(capa, "app", None)
    return out
