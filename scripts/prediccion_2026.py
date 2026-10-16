"""
Predicción del Congreso para el 29-N de 2026.

    python -m scripts.prediccion_2026 [fecha] [separados|frente_amplio]

fecha: día de corte de las encuestas (por defecto, hoy en el modelo: 2026-10-12).
"""
import sys
from pathlib import Path

from scripts import procedencia
from scripts.consola import configurar_salida_utf8
from motor.montecarlo import k_nacional
from motor.pipeline import BLOQUES, ELECCION, ESTATALES, MAYORIAS, Escenario, ejecutar, fusionar  # noqa: F401
from motor.proyeccion import FECHA
def main(fecha=FECHA, n_sim=10_000, escenario="separados"):
    configurar_salida_utf8()
    r = ejecutar(Escenario(fecha=fecha, candidaturas=escenario, n_sim=n_sim))
    print(f"Escenario: {escenario} · Corte {fecha} · {r.escenario.dias} días a la elección · "
          f"k_trasvase = {k_nacional(r.escenario.dias):.3f} · {n_sim} simulaciones\n")
    print(r.tabla.round(1).to_string())
    print()
    print((100 * r.probs).round(1).astype(str).add(" %").to_string())
    carpeta, sufijo = Path("resultados/prediccion"), f"{fecha}_{escenario}"
    salidas = [carpeta / f"simulaciones_{sufijo}.csv.gz", carpeta / f"prediccion_{sufijo}.csv",
               carpeta / f"probabilidades_{sufijo}.csv"]
    r.sim.to_csv(salidas[0], index=False)
    r.tabla.to_csv(salidas[1])
    r.probs.to_csv(salidas[2])
    meta = procedencia.escribir(carpeta / f"procedencia_{sufijo}.json", r.escenario, salidas)
    commit = meta["git"]["commit"]
    print(f"\nProcedencia: huella {meta['huella_modelo']} · commit "
          f"{commit[:8] if commit else 'sin git'}{' (con cambios sin confirmar)' if meta['git']['cambios_sin_confirmar'] else ''}")
    return r.sim, r.tabla, r.probs, r.central


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else FECHA
    escenario = sys.argv[2] if len(sys.argv) > 2 else "separados"
    main(fecha, escenario=escenario)
