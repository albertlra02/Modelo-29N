import pytest

from datos.cargar import cargar
from datos.familias import a_familias
from motor.proyeccion import base_2026


@pytest.mark.parametrize("prov, col, candidatura", [
    ("Teruel", "TERUEL", "Teruel Existe"),
    ("León", "UPL", "UPL"),
    ("Soria", "SORIA_YA", "Soria ¡Ya!"),
])
def test_base_conserva_las_candidaturas_locales_de_2023(prov, col, candidatura):
    # Si algún voto se cuenta dos veces (p. ej. en OTROS), la normalización encoge toda la fila
    b = cargar("2023-07")
    f = a_familias(b.votos)
    validos = f.sum(axis=1) + b.meta.blancos
    real = b.votos.at[prov, candidatura] / validos[prov]
    base, _ = base_2026()
    assert base.at[prov, col] == pytest.approx(real, rel=0.03)
    assert base.at[prov, "OTROS"] < 0.05
