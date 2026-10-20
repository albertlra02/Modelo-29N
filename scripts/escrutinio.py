"""
Escrutinio de la noche electoral (datos/escrutinio/escrutinio.csv, ver datos/escrutinio.py).

    python -m scripts.escrutinio simulacro --avance 40   # prueba: 2023 escrutado al ~40 %
    python -m scripts.escrutinio comprobar                # valida el fichero y resume lo escrutado
    python -m scripts.escrutinio borrar                   # quita el escrutinio (la página /noche vuelve a esperar)
"""
from __future__ import annotations

import argparse

from datos import escrutinio as E
from datos.cargar import cargar, escanos_2026
from scripts.consola import configurar_salida_utf8


def main(argv: list[str] | None = None) -> None:
    configurar_salida_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("simulacro", help="genera un escrutinio de prueba con los votos de 2023")
    s.add_argument("--avance", type=float, default=40.0, help="%% escrutado medio (0-100)")
    s.add_argument("--semilla", type=int, default=29)
    sub.add_parser("comprobar", help="valida el fichero y resume lo escrutado")
    sub.add_parser("borrar", help="borra el escrutinio")
    a = ap.parse_args(argv)

    if a.orden == "simulacro":
        E.CARPETA.mkdir(exist_ok=True)
        E.simulacro(a.avance, a.semilla).to_csv(E.RUTA)
        E.MARCA_SIMULACRO.write_text("Escrutinio de prueba con los votos de 2023", encoding="utf-8")
        print(f"Simulacro con los votos de 2023 escrito en {E.RUTA} (avance medio {a.avance:.0f} %).")
        print("Es una prueba: bórralo con `python -m scripts.escrutinio borrar` antes de la noche electoral.")
    if a.orden in ("simulacro", "comprobar"):
        esc = E.leer(provincias=list(escanos_2026().index))
        if esc is None:
            print(f"No hay escrutinio en {E.RUTA}.")
            return
        pesos = cargar("2023-07").validos.reindex(esc.index)
        print(f"Provincias: {int((esc.escrutado > 0).sum())} con votos contados de 52; "
              f"escrutado (ponderado por votantes de 2023): {(esc.escrutado * pesos).sum() / pesos.sum():.1f} %.")
        votos = esc.drop(columns=["escrutado"]).sum()
        print((100 * votos / votos.sum()).sort_values(ascending=False).head(10).round(1).to_string())
    if a.orden == "borrar":
        E.MARCA_SIMULACRO.unlink(missing_ok=True)
        if E.RUTA.exists():
            E.RUTA.unlink()
            print(f"Borrado {E.RUTA}.")
        else:
            print("No había escrutinio.")


if __name__ == "__main__":
    main()
