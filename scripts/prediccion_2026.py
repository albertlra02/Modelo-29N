"""
Predicción del Congreso y del Senado para el 29-N de 2026.

    python -m scripts.prediccion_2026 [fecha] [registradas|lista_unica]

fecha: día de corte de las encuestas (por defecto, hoy en el modelo: 2026-10-12).
"""
import sys
from pathlib import Path

from scripts import procedencia
from scripts.consola import configurar_salida_utf8
from motor.montecarlo import k_nacional
from motor.pipeline import BLOQUES, ELECCION, ESTATALES, MAYORIAS, Escenario, ejecutar  # noqa: F401
from motor.proyeccion import FECHA
from motor.senado import designados_por_lista, pleno
import pandas as pd


def main(fecha=FECHA, n_sim=10_000, escenario="registradas"):
    configurar_salida_utf8()
    r = ejecutar(Escenario(fecha=fecha, candidaturas=escenario, n_sim=n_sim))
    print(f"Escenario: {escenario} · Corte {fecha} · {r.escenario.dias} días a la elección · "
          f"k_trasvase = {k_nacional(r.escenario.dias):.3f} · {n_sim} simulaciones\n")
    print(r.tabla.round(1).to_string())
    print()
    print((100 * r.probs).round(1).astype(str).add(" %").to_string())
    sen = r.senado["sim"]
    q = sen.quantile([0.1, 0.5, 0.9]).T
    q.columns = ["p10", "mediana", "p90"]
    q["mediana sin coalición"] = r.senado["sin_coalicion"].median().reindex(q.index)
    q = q[q.p90 > 0].sort_values("mediana", ascending=False)
    print("\nSenado (208 electos):")
    print(q.to_string())
    pl = pleno(sen).median()
    tot = pd.DataFrame({"electos": sen.median(), "designados": designados_por_lista(), "pleno, mediana": pl})
    tot = tot.fillna(0).astype(int).sort_values("pleno, mediana", ascending=False)
    print("\nSenado completo (208 electos + designados autonómicos actuales):")
    print(tot[tot["pleno, mediana"] > 0].to_string())
    print((100 * r.senado["probs"]).round(1).astype(str).add(" %").to_string())
    print("\nHipótesis de retirada de Vox del Senado (medianas de electos y probabilidades):")
    hip = {"Vox en todas": r.senado} | r.senado["hipotesis_vox"]
    print(pd.DataFrame({h: {"PP": s["sim"]["PP"].median(), "Vox": s["sim"].get("VOX", pd.Series([0])).median(),
                            "P(PP ≥ 105) %": round(100 * s["probs"]["P(PP ≥ 105)"], 1),
                            "P(PP mayoría absoluta) %": round(100 * s["probs"]["P(PP mayoría absoluta)"], 1)}
                        for h, s in hip.items()}).T.to_string())
    carpeta, sufijo = Path("resultados/prediccion"), f"{fecha}_{escenario}"
    salidas = [carpeta / f"simulaciones_{sufijo}.csv.gz", carpeta / f"prediccion_{sufijo}.csv",
               carpeta / f"probabilidades_{sufijo}.csv", carpeta / f"senado_{sufijo}.csv"]
    r.sim.to_csv(salidas[0], index=False)
    r.tabla.to_csv(salidas[1])
    r.probs.to_csv(salidas[2])
    q.to_csv(salidas[3])
    meta = procedencia.escribir(carpeta / f"procedencia_{sufijo}.json", r.escenario, salidas)
    commit = meta["git"]["commit"]
    print(f"\nProcedencia: huella {meta['huella_modelo']} · commit "
          f"{commit[:8] if commit else 'sin git'}{' (con cambios sin confirmar)' if meta['git']['cambios_sin_confirmar'] else ''}")
    return r.sim, r.tabla, r.probs, r.central


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else FECHA
    escenario = sys.argv[2] if len(sys.argv) > 2 else "registradas"
    main(fecha, escenario=escenario)
