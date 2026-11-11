import json

from motor.pipeline import Escenario
from scripts import procedencia


def test_procedencia_registra_escenario_encuestas_y_hashes(tmp_path):
    salida = tmp_path / "prediccion.csv"
    salida.write_text("PP,PSOE\n140,110\n", encoding="utf-8")
    esc = Escenario(fecha="2026-10-12", n_sim=500, semilla=7)
    destino = tmp_path / "procedencia.json"
    meta = procedencia.escribir(destino, esc, [salida])

    assert json.loads(destino.read_text(encoding="utf-8")) == meta
    assert meta["escenario"]["semilla"] == 7 and meta["escenario"]["n_sim"] == 500
    assert len(meta["huella_modelo"]) == 16
    assert meta["ficheros"]["prediccion.csv"] == procedencia.sha256(salida)
    assert meta["encuestas"]["n"] > 0
    assert meta["encuestas"]["ultima"]["fin"] <= "2026-10-12"
    assert set(meta["git"]) == {"commit", "cambios_sin_confirmar"}


def test_encuestas_usadas_respeta_el_corte():
    antes = procedencia.encuestas_usadas("2026-06-01")
    despues = procedencia.encuestas_usadas("2026-10-12")
    assert antes["n"] < despues["n"]
    assert antes["ultima"]["fin"] <= "2026-06-01"
