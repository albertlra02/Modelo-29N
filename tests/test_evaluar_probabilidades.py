import numpy as np

from validacion.evaluar_probabilidades import brier, crps


def test_crps_de_una_prediccion_puntual_es_el_error_absoluto():
    assert crps(np.full(100, 130), 137) == 7


def test_crps_coincide_con_la_definicion():
    rng = np.random.default_rng(0)
    x, y = rng.integers(80, 160, 400), 121
    directo = np.abs(x - y).mean() - 0.5 * np.abs(x[:, None] - x[None, :]).mean()
    assert np.isclose(crps(x, y), directo)


def test_crps_premia_la_incertidumbre_honesta():
    rng = np.random.default_rng(1)
    reales = rng.normal(100, 10, 2000)
    ancha = rng.normal(100, 10, 4000)
    estrecha = rng.normal(100, 1, 4000)
    assert np.mean([crps(ancha, r) for r in reales[:200]]) < np.mean([crps(estrecha, r) for r in reales[:200]])


def test_brier():
    assert brier([1, 0], [True, False]) == 0
    assert brier([0.5, 0.5], [True, False]) == 0.25
