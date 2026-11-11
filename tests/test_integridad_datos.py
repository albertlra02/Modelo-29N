from datos.validar_integridad import validar


def test_manifest_de_datos():
    assert validar() == []
