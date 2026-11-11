"""
Acceso a la web publicada: contraseña y veda electoral. En local no hace nada.

Se configura con variables de entorno (las pone render.yaml en el servidor):

    CLAVE       si existe, la web pide una contraseña en una página de entrada propia (sólo contraseña,
                sin usuario) y la recuerda 30 días con una cookie firmada
    PUBLICADO   si existe, la web se cierra sola durante la veda
    VEDA        «si» la cierra ya; «no» la deja abierta aunque sea veda (para pruebas)

Veda: el art. 69.7 de la LOREG prohíbe publicar y difundir sondeos durante los cinco días anteriores a la
votación. La web publicada se cierra del 24 de noviembre a las 0:00 hasta el cierre de los colegios en Canarias
(29 de noviembre, 21:00 en la península).
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
from datetime import datetime
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, quote
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
VEDA_DESDE = datetime(2026, 11, 24, 0, 0, tzinfo=MADRID)
VEDA_HASTA = datetime(2026, 11, 29, 21, 0, tzinfo=MADRID)
SIN_CLAVE = ("/salud",)          # comprobación de vida del alojamiento
ENTRAR = "/entrar"
COOKIE = "acceso29n"
DURACION = 30 * 24 * 3600        # segundos que se recuerda el acceso

ESTILO = """<style>body{font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;background:#F3F5F7;color:#15202B;
display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}main{width:100%;max-width:26rem;padding:2rem;
background:#fff;border:1px solid #D8DEE4;border-radius:12px;box-shadow:0 2px 8px rgba(21,32,43,.05)}
h1{font-size:1.35rem;margin:0 0 .3rem}p{margin:.3rem 0 1rem;color:#4A5664}label{display:block;font-weight:600;
margin-bottom:.35rem}input{width:100%;box-sizing:border-box;font:inherit;padding:.6rem .7rem;border:1px solid #B7C0C9;
border-radius:8px}button{margin-top:1rem;width:100%;font:inherit;font-weight:600;color:#fff;background:#7A5F14;
border:0;border-radius:8px;padding:.65rem}button:hover{background:#5F4A10}.error{color:#B42318;font-weight:600}
.marca{font-weight:700;letter-spacing:-.01em;color:#7A5F14;margin-bottom:.6rem}</style>"""

PAGINA_VEDA = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Veda electoral · 29-N</title>{ESTILO}</head>
<body><main><p class="marca">29-N · Congreso y Senado</p><h1>Cerrado por la veda electoral</h1>
<p>Del 24 al 28 de noviembre la ley electoral (art. 69.7 de la LOREG) prohíbe publicar y difundir sondeos y
proyecciones. El modelo vuelve a estar disponible el 29 de noviembre al cerrar los colegios.</p></main></body></html>"""


def pagina_entrar(siguiente: str, error: bool = False) -> str:
    aviso = '<p class="error">Contraseña incorrecta.</p>' if error else ""
    destino = html.escape(f"{ENTRAR}?siguiente={quote(siguiente, safe='/')}", quote=True)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Entrar · Modelo 29-N</title>{ESTILO}</head>
<body><main><p class="marca">29-N · Congreso y Senado</p><h1>Modelo de las generales del 29-N</h1>
<p>Escribe la contraseña que te han facilitado.</p>{aviso}
<form method="post" action="{destino}"><label for="clave">Contraseña</label>
<input id="clave" name="clave" type="password" autocomplete="current-password" autofocus required>
<button type="submit">Entrar</button></form></main></body></html>"""


def en_veda(ahora: datetime | None = None) -> bool:
    modo = os.environ.get("VEDA", "").lower()
    if modo == "si":
        return True
    if modo == "no" or not os.environ.get("PUBLICADO"):
        return False
    ahora = ahora or datetime.now(MADRID)
    return VEDA_DESDE <= ahora < VEDA_HASTA


def ficha(clave: str) -> str:
    """Valor de la cookie: firma de la contraseña (cambiar CLAVE invalida los accesos guardados)."""
    return hmac.new(clave.encode(), b"modelo-29n", hashlib.sha256).hexdigest()


def clave_valida(dada: str | None, clave: str) -> bool:
    return bool(dada) and hmac.compare_digest(dada.encode(), clave.encode())


def siguiente_seguro(valor: str | None) -> str:
    """Sólo rutas propias (evita redirigir a otra web)."""
    return valor if valor and valor.startswith("/") and not valor.startswith("//") else "/"


class Acceso:
    """Middleware ASGI: veda primero, contraseña después."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in SIN_CLAVE:
            return await self.app(scope, receive, send)
        if en_veda():
            return await _responder(send, 503, PAGINA_VEDA)
        clave = os.environ.get("CLAVE")
        if not clave:
            return await self.app(scope, receive, send)

        cabeceras = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
        consulta = parse_qs(scope.get("query_string", b"").decode())
        if scope["path"] == ENTRAR:
            siguiente = siguiente_seguro((consulta.get("siguiente") or [None])[0])
            if scope["method"] == "POST":
                dada = (parse_qs((await _cuerpo(receive)).decode("utf-8", "replace")).get("clave") or [None])[0]
                if clave_valida(dada, clave):
                    segura = "; Secure" if cabeceras.get("x-forwarded-proto", scope.get("scheme")) == "https" else ""
                    cookie = f"{COOKIE}={ficha(clave)}; Path=/; Max-Age={DURACION}; HttpOnly; SameSite=Lax{segura}"
                    return await _responder(send, 303, "", [("location", siguiente), ("set-cookie", cookie)])
                return await _responder(send, 401, pagina_entrar(siguiente, error=True))
            return await _responder(send, 200, pagina_entrar(siguiente))

        galletas = SimpleCookie(cabeceras.get("cookie", ""))
        if COOKIE in galletas and hmac.compare_digest(galletas[COOKIE].value, ficha(clave)):
            return await self.app(scope, receive, send)
        if scope["path"].startswith(("/api/", "/descargar/", "/estatico/")):
            return await _responder(send, 401, "Hace falta la contraseña.", tipo="text/plain")
        actual = scope["path"] + (f"?{scope['query_string'].decode()}" if scope.get("query_string") else "")
        return await _responder(send, 401, pagina_entrar(actual))


async def _cuerpo(receive) -> bytes:
    trozos, mas = [], True
    while mas:
        m = await receive()
        trozos.append(m.get("body", b""))
        mas = m.get("more_body", False)
        if sum(map(len, trozos)) > 10_000:     # una contraseña no ocupa más
            break
    return b"".join(trozos)


async def _responder(send, estado: int, cuerpo: str, cabeceras: list[tuple[str, str]] | None = None,
                     tipo: str = "text/html") -> None:
    datos = cuerpo.encode("utf-8")
    h = [(b"content-type", f"{tipo}; charset=utf-8".encode()), (b"content-length", str(len(datos)).encode()),
         (b"cache-control", b"no-store")]
    h += [(k.encode(), v.encode()) for k, v in cabeceras or []]
    await send({"type": "http.response.start", "status": estado, "headers": h})
    await send({"type": "http.response.body", "body": datos})
