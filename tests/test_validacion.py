from datos.cargar import ELECCIONES, cargar, escanos_2026
from validacion.validar_motor import main


def test_motor_reproduce_las_cinco_elecciones():
    assert main() == 0


def test_ficheros_bien_formados():
    for eid in ELECCIONES:
        e = cargar(eid)
        assert (e.votos >= 0).all().all()
        assert (e.validos <= e.meta["censo"]).all()


def test_escanos_2026():
    esc = escanos_2026()
    assert esc.sum() == 350 and esc["Madrid"] == 38 and esc["Cádiz"] == 8
