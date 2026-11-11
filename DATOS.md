# Procedencia y licencias de los datos

El código del repositorio está bajo licencia MIT (ver `LICENSE`). Los datos de terceros conservan sus condiciones:

| Datos | Ficheros | Fuente | Condiciones |
|---|---|---|---|
| Resultados oficiales del Congreso 2015–2023 y del Senado 2023 | `datos/raw/`, `datos/raw/infoelectoral/` | Ministerio del Interior, [infoelectoral.interior.gob.es](https://infoelectoral.interior.gob.es) | Reutilización de información del sector público (Ley 37/2007), citando la fuente |
| Encuestas publicadas | `datos/encuestas/raw/`, `datos/encuestas/nacionales.csv` | Recopilación de Wikipedia «Opinion polling for the next Spanish general election» y artículos de ciclos anteriores; cada encuesta es de su empresa y medio | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/): se redistribuyen con la misma licencia y citando la fuente |
| Senadores designados por las comunidades autónomas | `datos/senado_designados.csv` | Web del Senado, [senado.es](https://www.senado.es) | Información pública, citando la fuente |

## Qué es y qué no es

Esto no es una encuesta: no hay trabajo de campo propio. Es un modelo que combina encuestas ya publicadas con resultados
oficiales. Las cifras que produce dependen de supuestos que se documentan en `docs/` y en la página «Cómo funciona» de la
aplicación.

Durante los cinco días anteriores a la votación (del 24 al 28 de noviembre de 2026) la LOREG (art. 69.7) prohíbe publicar
y difundir sondeos; la aplicación publicada se cierra sola esos días.
