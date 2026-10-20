"""
Velocidad de la web publicada (servidores con poca CPU, como el plan gratuito de Render).

- Compresión: todo lo que se envía va comprimido con gzip (la librería de gráficos pasa de 4,8 a 1,5 MB).
- Páginas en memoria: en la web publicada (PUBLICADO), cada página ya generada se guarda en memoria unas horas
  y la siguiente visita la recibe al instante. Una página que todavía está calculando no se guarda.
- Precalentado: al arrancar, se generan en segundo plano las páginas principales del escenario por defecto,
  para que el primer visitante no espere.

En local no se guarda nada (al editar plantillas o código se ve el cambio al momento); sí se comprime.
"""
from __future__ import annotations

import asyncio
import gzip
import os
import threading
import time
from collections import OrderedDict

TTL = 6 * 3600                 # las páginas incluyen «faltan N días»: se regeneran cada pocas horas
MAX_BYTES = 80 * 2**20         # tope de memoria para las páginas guardadas (comprimidas)
NO_GUARDAR = ("/api/calcular", "/salud", "/entrar", "/descargar/")
MARCA_CALCULANDO = b"data-calcular="
PRECALENTAR = ["/estatico/plotly.min.js", "/", "/escanos", "/mayorias", "/provincias", "/senado", "/participacion",
               "/simulador", "/encuestas", "/evolucion", "/metodologia", "/comparar"]


def activo() -> bool:
    return bool(os.environ.get("PUBLICADO"))


class PaginasEnMemoria:
    """Middleware ASGI: guarda las respuestas GET completas (ya comprimidas) y las repite sin recalcular."""

    def __init__(self, app):
        self.app = app
        self.guardadas: OrderedDict[tuple, tuple[float, int, list, bytes]] = OrderedDict()
        self.bytes = 0
        self.candado = threading.Lock()

    def _clave(self, scope) -> tuple:
        cab = dict(scope.get("headers") or [])
        gz = b"gzip" in cab.get(b"accept-encoding", b"")
        return scope["path"], scope.get("query_string", b""), gz

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "GET" or not activo()
                or scope["path"].startswith(NO_GUARDAR)):
            return await self.app(scope, receive, send)
        clave = self._clave(scope)
        with self.candado:
            e = self.guardadas.get(clave)
            if e and time.monotonic() - e[0] < TTL:
                self.guardadas.move_to_end(clave)
        if e and time.monotonic() - e[0] < TTL:
            _, estado, cabeceras, cuerpo = e
            await send({"type": "http.response.start", "status": estado, "headers": cabeceras})
            await send({"type": "http.response.body", "body": cuerpo})
            return

        inicio, trozos = {}, []

        async def capturar(m):
            if m["type"] == "http.response.start":
                inicio.update(m)
            elif m["type"] == "http.response.body":
                trozos.append(m.get("body", b""))
            await send(m)

        await self.app(scope, receive, capturar)
        cuerpo = b"".join(trozos)
        if inicio.get("status") != 200 or MARCA_CALCULANDO in _texto(cuerpo, inicio.get("headers", [])):
            return
        with self.candado:
            if clave in self.guardadas:
                self.bytes -= len(self.guardadas.pop(clave)[3])
            self.guardadas[clave] = (time.monotonic(), 200, list(inicio["headers"]), cuerpo)
            self.bytes += len(cuerpo)
            while self.bytes > MAX_BYTES and self.guardadas:
                self.bytes -= len(self.guardadas.popitem(last=False)[1][3])


def _texto(cuerpo: bytes, cabeceras) -> bytes:
    """El cuerpo sin comprimir, para buscar la marca de «calculando» (sólo HTML)."""
    cab = {k.lower(): v for k, v in cabeceras}
    if not cab.get(b"content-type", b"").startswith(b"text/html"):
        return b""
    return gzip.decompress(cuerpo) if cab.get(b"content-encoding") == b"gzip" else cuerpo


def precalentar(app, cookie: str | None) -> None:
    """Pide las páginas principales a la propia aplicación (sin red), en un hilo aparte."""
    if not activo():
        return

    def pedir(ruta: str) -> None:
        cab = [(b"host", b"interno"), (b"accept-encoding", b"gzip")]
        if cookie:
            cab.append((b"cookie", cookie.encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                 "scheme": "http", "path": ruta, "raw_path": ruta.encode(), "query_string": b"", "root_path": "",
                 "headers": cab, "client": ("127.0.0.1", 0), "server": ("interno", 80)}
        enviado = []

        async def recibir():
            if not enviado:
                enviado.append(True)
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.Event().wait()

        async def enviar(m):
            pass

        asyncio.run(app(scope, recibir, enviar))

    def todo():
        for ruta in PRECALENTAR:
            try:
                pedir(ruta)
            except Exception:  # noqa: BLE001  (precalentar es una ayuda; si falla, la página se genera al pedirla)
                pass

    threading.Thread(target=todo, daemon=True, name="precalentar").start()
