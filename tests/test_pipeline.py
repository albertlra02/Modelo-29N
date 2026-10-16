from motor.pipeline import Escenario, ejecutar


def test_escenario_base_reparte_350_y_probabilidades_validas():
    r = ejecutar(Escenario(n_sim=300))
    assert (r.sim.sum(axis=1) == 350).all()
    assert r.probs.between(0, 1).all()
    assert len(r.provincias) == 52


def test_frente_amplio_y_participacion():
    base = ejecutar(Escenario(n_sim=400, semilla=7))
    fa = ejecutar(Escenario(n_sim=400, semilla=7, candidaturas="frente_amplio", participacion=0.72))
    assert "FRENTE_AMPLIO" in fa.sim and "SUMAR" not in fa.sim
    assert (fa.sim.sum(axis=1) == 350).all()
    # más participación con reparto histórico: la izquierda sube en voto central
    assert fa.nacional["PSOE"] > base.nacional["PSOE"]
