from datos.oficiales import CONGRESO, comparar
from motor.proyeccion import europeas_2024


def test_csv_del_congreso_coinciden_con_los_ficheros_oficiales():
    for eleccion in CONGRESO:
        assert comparar(eleccion).empty, eleccion


def test_europeas_cuotas_validas():
    eu = europeas_2024()
    assert len(eu) == 52 and eu[["PP", "Sumar", "Podemos", "SALF"]].notna().all().all()
    assert ((eu.sum(axis=1) > 0.97) & (eu.sum(axis=1) < 1.0)).all()   # el resto es voto en blanco
