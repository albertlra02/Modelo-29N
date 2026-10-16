# Modelo electoral – Congreso 29-N 2026

Uso personal. Datos publicados, nada de trabajo de campo.

## Estado

| Paso | Qué | Estado |
|---|---|---|
| 1 | Motor de escaños (D'Hondt, LOREG art. 163) | Hecho, con tests |
| 2 | Resultados 2015–2023 por circunscripción + validación | Hecho: reproduce los 350 escaños de las 5 elecciones |
| 3 | Agregador de encuestas (house effects) | Hecho: backtest en 5 elecciones y calibración leave-one-election-out |
| 4 | Reparto provincial (swing) | Hecho: backtest con oráculo en 4 transiciones |
| 4b | Capa autonómica (encuestas por CCAA) | Hecho: 16 encuestas en 9 CCAA, encogimiento bayesiano |
| 5 | Monte Carlo + backtest | Hecho: error nacional calibrado en 5 elecciones; backtest fuera de muestra en 4 |
| 6 | Web | Hecho: web propia (Starlette + plotly.js), abre con F5 en VS Code o con iniciar.bat |

## Estructura

```
lanzar.py, iniciar.bat   cómo abrir la web (http://127.0.0.1:8029)
docs/biblia.md       cómo explicar el modelo: qué es, cómo leerlo, supuestos (participación) y límites
web/                 la web: servidor.py (rutas), datos.py (escenario y caché), plantillas/ (Jinja), estatico/ (CSS y JS)
app.py               la aplicación Streamlit anterior (ya no se lanza por defecto: streamlit run app.py)
interfaz/            estilo.py (colores, tipos, CSS), graficos.py (Plotly), calculo.py (caché de escenarios)
motor/               el modelo
  pipeline.py          punto de entrada único: Escenario -> Resultado (lo usan la app y los scripts)
  proyeccion.py        piezas deterministas: estimación nacional, base 2026, capa CCAA
  agregador.py         media de encuestas: paseo aleatorio + efecto de casa por encuestadora
  regional.py          encuestas autonómicas -> objetivos por CCAA
  swing.py             nacional/CCAA -> provincias (uniforme, proporcional, logit)
  montecarlo.py        simulación de escaños con error de bloque, trasvase, regional y provincial
  escanos.py           D'Hondt exacto (validación) y vectorizado (Monte Carlo)
datos/               datos fuente y su carga
  raw/                 resultados oficiales por circunscripción (CSV generados con oficiales.py)
  raw/infoelectoral/   ficheros oficiales del Ministerio del Interior, tal cual se descargan
  encuestas/           encuestas de Wikipedia (raw/), importador reproducible y CSV limpios
  geo/                 contornos de provincias para el mapa (es-atlas 0.6.0, datos IGN/CNIG; Canarias desplazada)
  oficiales.py         descarga infoelectoral y genera los CSV de raw/
  candidaturas_oficiales.csv  candidatura oficial -> columna del modelo (confluencias, alias)
  cargar.py, familias.py      carga de resultados; familias de partidos y provincias -> CCAA
  MANIFEST.sha256, validar_integridad.py   hashes de los datos y su comprobación
validacion/          la evidencia: python -m validacion.<script>
  validar_motor.py     el motor reproduce los 350 escaños de 2015–2023
  backtest_agregador.py, calibrar_agregador.py   error de la media de encuestas y sus hiperparámetros
  calibrar_error_nacional.py   escalas de error de bloque y trasvase del Monte Carlo
  backtest_swing.py    error de la capa provincial con el resultado agregado real (oráculo)
  backtest_mc.py       el 23J visto desde 30, 14 y 1 días antes
  backtest_loo.py      backtest fuera de muestra: 2016, 2019A, 2019N y 2023, cada una calibrada sin ella
  evaluar_probabilidades.py  CRPS, Brier y fiabilidad de las probabilidades frente a referencias sin incertidumbre
scripts/             utilidades: python -m scripts.<script>
  prediccion_2026.py   predicción por consola: [fecha] [separados|frente_amplio]
  precalcular.py       rejilla de escenarios de la app (controles instantáneos)
  analisis_electopanel_y_bloques.py   ElectoPanel provincial y voto por bloques frente a participación
resultados/          salidas: validacion/, prediccion/, analisis/ y cache/ (la de la app)
tests/               pytest
```

## Abrir y ejecutar

**VS Code** (extensión Python):
1. Abre la carpeta del proyecto.
2. `Ctrl+Shift+P` → *Python: Create Environment* → venv, con `requirements.txt`.
3. F5 con la configuración "Abrir la aplicación". Hay tareas para instalar, pasar los tests, validar el motor y
   precalcular los escenarios.

**Sin IDE (Windows):** doble clic en `iniciar.bat`. La primera vez crea el entorno e instala las dependencias;
si encuentra un entorno virtual incompleto, intenta reconstruirlo.

**Terminal** (siempre desde la carpeta del proyecto):
```bash
python -m venv .venv && .venv\Scripts\activate      # en macOS/Linux: source .venv/bin/activate
pip install -r requirements-lock.txt                 # entorno reproducible validado con Python 3.12
python -m scripts.precalcular                        # rejilla de escenarios (≈2 min): controles instantáneos
python lanzar.py                                     # la web en http://127.0.0.1:8029
python -m pytest -q                                  # 66 tests
python -m validacion.validar_motor                   # el motor reproduce el Congreso 2015–2023
python datos/validar_integridad.py                   # verifica los hashes de los datos
python -m scripts.prediccion_2026 2026-10-12 frente_amplio   # predicción por consola
```

**Para desarrollar**, una vez:
```bash
pip install -r requirements-dev.txt                  # añade ruff
git config core.hooksPath .githooks                  # ruff + tests antes de cada commit
```
`python -m ruff check .` pasa el lint (configuración en `pyproject.toml`). El hook de `.githooks/pre-commit`
corre ruff y los tests, y `validacion.validar_motor` si el commit toca `motor/escanos.py`; en GitHub, el workflow
`.github/workflows/comprobaciones.yml` repite lo mismo más la integridad de los datos. Los cambios del modelo y
su efecto en las cifras se anotan en `CHANGELOG.md`.

El código requiere Python 3.10 o posterior. `requirements-lock.txt` corresponde al entorno validado con
Python 3.12; `requirements.txt` conserva rangos mínimos para crear un entorno en otra versión.

### Versiones y procedencia de las predicciones

El proyecto está bajo git (`.gitattributes` desactiva la conversión de finales de línea para que los hashes de
`datos/MANIFEST.sha256` sigan valiendo). Cada `scripts.prediccion_2026` escribe, junto a sus CSV,
`resultados/prediccion/procedencia_<fecha>_<escenario>.json` con el commit (y si el código o los datos tenían
cambios sin confirmar), la huella del modelo, el escenario completo (semilla y simulaciones), el número de
encuestas y la última usada, las versiones de Python y librerías y el SHA-256 de cada salida. Con la misma
semilla y el mismo commit la predicción se reproduce byte a byte. Para publicar una cifra, confirmar antes los
cambios: una procedencia con `"cambios_sin_confirmar": true` no se puede reproducir desde el historial.

## La web

`python lanzar.py` arranca un servidor local (Starlette + uvicorn) y abre el navegador. Cada sección tiene su página;
el escenario (corte de encuestas, candidaturas, participación, reparto, simulaciones y semilla) se cambia con el botón
**Cambiar escenario** y viaja en la dirección (`/provincias?cand=frente_amplio&part=70`), así que cualquier vista se
puede guardar como marcador. Las gráficas son las de `interfaz/graficos.py`, pintadas con plotly.js (servido desde el
paquete de Plotly, sin internet salvo las fuentes).

| Página | Qué muestra |
|---|---|
| `/` Resumen | Titular, hemiciclo con el reparto medio, probabilidades principales, ficha de cada partido y accesos al resto |
| `/escanos` | Voto nacional y escaños por partido (mediana, 80 % y 95 %), tabla ordenable y descarga de las simulaciones en CSV |
| `/mayorias` | Calculadora de pactos en el navegador (la coalición queda en la dirección: `#PP+VOX`) y probabilidad de cada escenario |
| `/provincias` | Mapa (partido más votado, escaño en juego o voto de un partido), dónde baila el último escaño, tabla filtrable por comunidad |
| `/encuestas` | Media actual con su cambio a 30 días, evolución, últimas encuestas, sesgo de cada casa y encuestas autonómicas |
| `/evolucion` | Hemiciclo animado semana a semana desde junio y líneas de mayoría y escaños |
| `/participacion` | Barrido de participación del 62 % al 75 % para los dos supuestos de candidaturas |
| `/metodologia` | Método, error medido y límites |

Si un escenario no está en la caché, la página lo calcula desde el navegador (uno a uno, con barra de progreso) y se
recarga al terminar; la evolución y el barrido piden confirmación porque pueden tardar un minuto. El servidor se reinicia
solo al guardar código Python; plantillas y CSS se recogen al recargar la página.

**Caché de escenarios.** Cada escenario calculado se guarda resumido en `resultados/cache/<huella>/`
(`interfaz/calculo.py`). La huella es un hash del modelo y de los datos: si cambia cualquiera, la caché vieja se
borra sola al abrir la app. `python -m scripts.precalcular` calcula de antemano la rejilla que usa la app con los valores
por defecto (20 cortes semanales, participación del 60 al 76 % con los tres repartos y el barrido), en paralelo;
lo que no esté en la rejilla se calcula al vuelo y también se guarda.

Para actualizar con encuestas nuevas: añade las filas a `datos/encuestas/raw/` (o regenera desde Wikipedia),
ejecuta `python datos/encuestas/parsear.py` y cambia `FECHA` en `motor/proyeccion.py` (la app la usa como última fecha
elegible) y vuelve a correr `python -m scripts.precalcular`.

## Fuentes de resultados electorales

Todos los resultados electorales son oficiales: Ministerio del Interior, Área de descargas de infoelectoral
(https://infoelectoral.interior.gob.es/), ficheros `02AAAAMM_MUNI.zip` (Congreso 2015, 2016, abril y noviembre de 2019
y 2023) y `07202406_MUNI.zip` (europeas 2024). Se guardan sin tocar en `datos/raw/infoelectoral/` y sus hashes están en
el manifiesto. `python datos/oficiales.py` regenera los CSV; `--comprobar` compara los CSV con los ficheros oficiales.
Se usan los totales provinciales del escrutinio (fichero 07/08: incluyen el voto CERA). Las candidaturas oficiales se
llevan a las columnas del modelo con `datos/candidaturas_oficiales.csv` (p. ej. todas las confluencias de Podemos a
`Podemos`); en las europeas, las marcas regionales de una lista (Comuns Sumar, Sumar Galicia…) se suman a su cabecera.

Hasta el 14/10/2026 los CSV venían de una fuente no oficial (ya eliminada). Coincidían voto a
voto salvo en una provincia por elección, sin efecto en los escaños reales:

| Elección | Diferencias de la fuente anterior |
|---|---|
| 2015 | Palencia (PP +108, blancos −155, resto ±1); faltaba PCPC en las cuatro provincias catalanas (7.116 votos); ARA, PV en Valencia (−13); dos columnas sin nombre (Libertad Navarra, Justizia Social) |
| 2016 | Zaragoza (Cs −740, blancos +495, resto ±1) |
| 2019 abril | Asturias (PACMA +849, blancos −592) |
| 2019 noviembre | Asturias (Más País +702, blancos −883, resto ±1) |
| 2023 | Sevilla (Vox −1.252, blancos +1.761) |

Las filas de resultado de las tablas de encuestas de Wikipedia (`nacionales.csv`, con las que se mide el error de las
encuestas) coinciden con los oficiales a ±0,05 pp; la excepción es Más País en 2019N (+0,73 pp), porque Wikipedia suma
Compromís, igual que en sus encuestas.

## Notas de datos

- 2023: Vox no concurrió en Santa Cruz de Tenerife (0 votos es correcto). La base de 2023
  no sirve para proyectar a Vox ahí; habrá que usar 2019 o el voto regional.
- Las confluencias de Podemos (2015–2019) vienen agregadas en la columna `Podemos`.
- Escaños 2026 = 2023 con Madrid 38 (+1) y Cádiz 8 (−1).

## Backtest de la capa provincial (oráculo)

Escaños mal asignados por provincia, de media en 4 transiciones (2015→2016 … 2019N→2023),
dando como entrada el resultado agregado real:

| Método | Escaños mal (provincia) | Desvío nacional | MAE voto |
|---|---|---|---|
| uniforme + objetivo por CCAA | 6,2 | 3,2 | 0,5 pp |
| logit + objetivo por CCAA | 6,8 | 4,0 | 0,5 pp |
| proporcional + CCAA | 8,2 | 3,2 | 0,5 pp |
| logit, solo nacional | 17,8 | 6,8 | 1,3 pp |
| proporcional, solo nacional | 18,5 | 6,0 | 1,4 pp |
| uniforme, solo nacional | 22,8 | 7,5 | 1,6 pp |
| sin swing (repetir la anterior) | 61,5 | 56,5 | 4,4 pp |

## Fuentes de encuestas

Las series de 2015, 2016 y abril de 2019 se descargaron el 14/10/2026 con
`python datos/encuestas/descargar_historicas.py`. Cada URL incluye un `oldid`, por lo que una edición futura
de Wikipedia no cambia silenciosamente los datos. Las series más recientes se extrajeron el 12/10/2026.
Los hashes de los ficheros raw y de las tablas procesadas se conservan en `datos/MANIFEST.sha256` y se verifican con
`python datos/validar_integridad.py`. El manifiesto acredita los bytes usados por esta versión; no sustituye una
URL y una copia fechada de la fuente externa.

| Fichero | Contenido |
|---|---|
| [wiki_2015.json](https://en.wikipedia.org/w/index.php?title=Opinion_polling_for_the_2015_Spanish_general_election&oldid=1377201395) | 195 encuestas nacionales de 2015 + resultados |
| [wiki_2016.json](https://en.wikipedia.org/w/index.php?title=Opinion_polling_for_the_2016_Spanish_general_election&oldid=1377201436) | 153 encuestas nacionales del ciclo de 2016 + resultados |
| [wiki_2019a.json](https://en.wikipedia.org/w/index.php?title=Opinion_polling_for_the_April_2019_Spanish_general_election&oldid=1377201530) | 126 encuestas nacionales de enero–abril de 2019 + resultado |
| wiki_2026_ciclo_2026.json / _2025.json | Encuestas nacionales ene 2025 – 11 oct 2026 |
| wiki_2023_final.json | Encuestas de jun–jul 2023 + resultado 23J (backtest) |
| wiki_2019n.json | Encuestas may–nov 2019 + resultado 10N (backtest) |
| wiki_2026_subnacional.json | Encuestas por CCAA y provincias gallegas (CEO, Sondaxe, GAD3…) |

Ojo: Wikipedia suma Compromís dentro de Sumar en las encuestas de 2026 (ElectoPanel 11/10: 4,9 + 1,1 = 6,0).

## Backtest del agregador

Error medio absoluto por partido frente al resultado (pp):

| Días antes | 2015 | 2016 | 2019A | 2019N | 2023 |
|---|---:|---:|---:|---:|---:|
| 1 | 1,44 | 2,02 | 1,30 | 0,75 | 1,27 |
| 14 | 2,70 | 2,42 | 1,18 | 1,68 | 1,48 |
| 30 | 2,62 | 2,23 | 1,36 | 2,05 | 2,15 |
| 48 | 2,68 | 2,12 | 1,92 | 3,28 | – |

La incertidumbre interna del agregador (aproximadamente ±0,4–0,7 pp) es menor que el error real:
lo que domina es el error común de la industria (PSOE −3,2 pp en 2023) y el movimiento
de campaña. El Monte Carlo usará el error empírico, no el interno.
La rejilla leave-one-election-out elige `q = 0,20 pp/día` y `tau = 0,6 pp` en las cinco particiones;
el ancla es `igual` en cuatro y `sin_cis` en una. El MAE medio en la elección no vista es 1,92 pp.
Para producción se usa `q = 0,20`, `tau = 0,6`, ancla `igual`. El detalle reproducible queda en
`resultados/validacion/calibracion_agregador_loo.csv`.

## Backtest fuera de muestra del modelo completo

`python -m validacion.backtest_loo`. Para cada elección evaluada, las escalas de error nacional se recalculan sin ella con la
misma regla que producción (que reproduce exactamente las constantes de `motor/montecarlo.py` con las cinco
elecciones); se proyecta desde la elección anterior con las encuestas de 30, 14 y 1 días antes y se simula 10.000
veces. 2015 no se puede evaluar (falta 2011). Detalle en `resultados/validacion/backtest_loo.txt` y `backtest_loo*.csv`.

| | Fuera de muestra | Dentro de muestra |
|---|---:|---:|
| Escaño real dentro del intervalo del 80 % (estatales, n = 54) | 76 % | 74 % |
| Escaño real dentro del intervalo del 95 % (estatales) | 93 % | 98 % |
| Ídem 80 % / 95 %, todos los partidos (n = 147) | 76 % / 88 % | 76 % / 90 % |
| Error medio absoluto (escaños, estatales): mediana del modelo | 8,1 | 8,1 |
| Ídem, repetir la elección anterior | 21,9 | 21,9 |
| Brier de P(derecha ≥ 176) (referencia 50 %: 0,250) | 0,143 | 0,144 |

Lectura: los intervalos de los partidos estatales están cerca de su cobertura nominal, algo estrechos en el 80 %, y
calibrar sin la elección evaluada apenas cambia nada (no hay sobreajuste visible). Fallos: la subida de Vox en
2019N (real 52, mediana 24 a 30 días y 32 a 14 días, fuera del 95 %) y la caída de Cs; sesgo sistemático del espacio
de Podemos (+7 escaños de media) y del PSOE (−6). Los partidos regionales cubren peor (95 % -> 86 %): casi todos los
fallos son candidaturas sin base en la elección anterior (Teruel Existe, PRC, Navarra Suma, CUP en 2019N), justo el
caso de SALF y Adelante en 2026. La derecha nunca llegó a 176 en las cuatro elecciones; en 2023 el modelo daba entre
un 69 y un 78 %. Límites: sin encuestas autonómicas; K_REG, K_PROV, margen ×1,10, correlación −0,65 y colas t(5) fijos;
los tres horizontes de una misma elección no son independientes (en la práctica n ≈ 4).

## Evaluación de las probabilidades

`python -m validacion.evaluar_probabilidades` (≈1 min). Puntúa la distribución entera de las mismas simulaciones fuera
de muestra del backtest (mismas escalas y semillas) con reglas de puntuación propias, y la compara con dos referencias
sin incertidumbre: la proyección central del modelo (sin simular) y repetir la elección anterior. Detalle en
`resultados/validacion/probabilidades.txt` y `probabilidades_*.csv`.

| Medida (fuera de muestra) | Modelo | Proyección central | Repetir la anterior |
|---|---:|---:|---:|
| CRPS por partido estatal (escaños; n = 54) | 5,7 | 8,0 | 21,9 |
| Brier, «el partido saca al menos k escaños» (estatales, n = 1.011) | 0,034 | 0,044 | 0,139 |
| Brier, sucesos de bloque: derecha ≥ 176 y PP > PSOE (n = 24) | 0,073 | 0,125 | 0,250 |

| Intervalo central (estatales) | 10 % | 20 % | 30 % | 40 % | 50 % | 60 % | 70 % | 80 % | 90 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Resultado real dentro | 6 % | 15 % | 31 % | 48 % | 52 % | 63 % | 65 % | 76 % | 87 % |

Lectura: simular aporta frente a dar sólo la proyección central (CRPS un 28 % menor, Brier de bloque un 41 % menor), y la
mejora se mantiene en las cuatro elecciones y los tres horizontes. Los intervalos están bien centrados hasta el 60 % y se
quedan algo cortos en los anchos (70–90 %): las colas son estrechas. Cuando el modelo da menos de un 2 % a algo, pasó en
un 6 % de los casos (14 de 238); casi todos son candidaturas sin base en la elección anterior (PRC, Teruel Existe, CUP,
Navarra Suma), más Vox ≥ 50 en 2019N y ERC ≥ 15 en 2019A. El percentil medio del resultado real es 0,45 (ligera
sobreestimación). Con 4 elecciones y sucesos muy correlacionados, son tendencias, no una prueba estadística.

## Calibración de la incertidumbre

| Componente | Escala | De dónde sale |
|---|---|---|
| Error de bloque (derecha / izquierda estatal) | dcha 2,1 → 3,6 pp; izda 1,8 → 3,6 pp (víspera → 48 días), ×1,10 y colas t(5); corr. usada −0,65 | Backtest del agregador, 5 elecciones; correlación empírica −0,74 |
| Trasvase dentro del bloque (suma cero) | k = 0,035 → 0,095 | Residuos de partido tras quitar el error común, 5 elecciones |
| Desviación autonómica | k = 0,060 sin encuestas; menor con encuestas | Histórico 2016–2023 |
| Ruido provincial | k = 0,026 | Histórico 2016–2023 |
| Forma del reparto de Vox | mezcla aleatoria logit / uniforme | El histórico no decide |

sd = k · sqrt(s(1−s)). Primera versión trataba el error de cada partido por separado y
daba al voto PP+Vox una sd de ~8 pp: irreal, porque dentro de un bloque los errores se
compensan (2019N a 48 días: Cs +6,5 y Vox −6,8, bloque de derechas −0,5). Las escalas y la correlación
se recalculan con `validacion/calibrar_error_nacional.py`; se mantiene un margen ×1,10 por el tamaño reducido de la muestra.
Los hiperparámetros del agregador y las escalas de error se evalúan fuera de muestra por elección (abajo), pero
cuatro elecciones siguen siendo una serie corta. Las cifras del Monte Carlo son frecuencias condicionadas a estos
supuestos, no probabilidades validadas en una serie larga.
Los tracking polls con trabajos de campo solapados tampoco están modelados con una covarianza específica.
El residual `OTROS` cuenta para el umbral, pero no obtiene escaños: cualquier candidatura nueva con apoyo
territorial concentrado debe añadirse expresamente.
Las escalas de error sólo están medidas hasta 48 días antes de votar; más allá, `interpolar` sigue creciendo como
un paseo aleatorio sin calibración (a 180 días, error de bloque ≈ 6 pp) y la app lo avisa.
Los partidos de una sola comunidad no tienen error de campaña propio: su incertidumbre (capa autonómica + provincial)
no crece con los días que faltan y probablemente se queda corta.
