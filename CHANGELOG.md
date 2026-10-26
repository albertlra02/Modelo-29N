# Registro de cambios

Cambios del modelo y de sus cifras, del más reciente al más antiguo. Cada entrada dice qué cambió, por qué y
cuánto movió la predicción central (escenario por defecto, corte de encuestas más reciente). La versión sigue
`pyproject.toml`; los cambios que mueven cifras suben la versión menor (1.**1**.0), los arreglos sin efecto en
los resultados, la de parche (1.0.**1**). La huella de cada versión está en la procedencia de sus predicciones.

Plantilla de entrada:

```
## [1.x.y] – AAAA-MM-DD
### Modelo        (supuestos, calibraciones, datos nuevos: qué y por qué)
### Efecto        (p. ej. P(PP + Vox ≥ 176): 89,4 % → 87,1 %; PP: 139 → 136 escaños de mediana)
### Interfaz y herramientas
```

## [Sin publicar]

### Modelo
- **Acuerdo PP-Vox para el Senado (26/10/2026)** en `motor/senado.py`, en lugar de la hipótesis de las 15
  provincias publicadas: Vox no se presenta en 6 provincias (uno de los tres nombres del PP es un independiente
  propuesto por Vox en las de 4 senadores), el PP no se presenta en Gipuzkoa, Girona y Tarragona, y en 14
  provincias Vox lleva un solo candidato y pide marcar dos del PP. Para esto último, reparto candidato a candidato
  (`repartir_candidatos`, que con listas de 3 nombres da lo mismo que `repartir`). Supuestos sin calibrar:
  TRASVASE_VOX 80 %, TRASVASE_PP 60 %, CUMPLE_VOX_UNO 80 %.
- `scripts/analisis_pacto_senado.py`: sin pacto, el acuerdo y el mejor pacto posible por provincia.
### Efecto
- Con un 65 % de participación, PP + Vox con tres quintos del Senado: 17 % sin pacto → 53 % con el acuerdo
  (mediana de electos de PP + Vox: 111 → 133). El mejor pacto posible llegaría al 89 % (77 % con supuestos
  pesimistas). Con un 72 %: 4 % → 15 % (61 % con el mejor pacto).
- **Palancas de escenario** (`motor/palancas.py`), aplicadas a la proyección central antes de simular, así que
  mueven Congreso, Senado y mayorías:
  - Movilización por bloque (izquierda, derecha, nacionalistas y regionalistas), de −20 % a +20 % de su voto,
    en toda España o en una comunidad.
  - Voto útil: Podemos → Frente Amplio, Frente Amplio → PSOE, Vox → PP y SALF → Vox, del 0 al 50 %, en todas las
    provincias o sólo donde el partido de origen no saca escaño con el voto central.

### Efecto
- Ninguno en el escenario por defecto (todas las palancas a cero). Ejemplos con 2000 simulaciones: izquierda +8 %
  → PSOE 107 → 114 escaños y P(PP + Vox ≥ 176) 91 % → 84 %; 20 % de Vox → PP donde Vox no saca escaño → PP 129 → 132.

### Datos
- Encuestas hasta el 17 de octubre (CIS de octubre, dos de Sigma Dos y una de EM-Analytics); corte por defecto el 20 de
  octubre. P(PP + Vox ≥ 176): 91,0 % → 91,6 % (10.000 simulaciones).

### Interfaz y herramientas
- Menú de seis secciones (Resumen, Congreso, Senado, Escenarios, Encuestas, Cómo funciona) con pestañas dentro de cada
  una; bloque «Qué es esto» en la portada; «Cómo funciona» rehecha con los supuestos justificados, sus fuentes
  académicas, qué mueve qué (con enlaces a comparaciones en vivo), validación y límites. README con portada para revisores.
- Panel de escenario con las dos palancas (en la URL: `mov_izda`, `mov_dcha`, `mov_nac`, `ambito`, `util_*`,
  `util_donde`). Comparar enfrenta por defecto el escenario con y sin sus palancas.

## [1.1.0] – 2026-10-17

### Modelo
- **Candidaturas registradas** (cierre de coaliciones del 16 de octubre) como escenario por defecto (`registradas`),
  en lugar de `separados`:
  - Frente Amplio (IU, Movimiento Sumar, Más Madrid y Comuns, con CHA, Més, Batzarre, Somos Asturies…) ocupa el
    espacio que las encuestas llaman Sumar: la columna `SUMAR` pasa a `FRENTE_AMPLIO`.
  - Podemos va por su cuenta, salvo en Cataluña, donde se integra en las listas de ERC (Rufián): sus votantes se
    reparten 60 % a ERC y 40 % a los Comuns (supuesto sin calibrar, `PODEMOS_CATALUNA` en `motor/pipeline.py`).
  - Listas conjuntas de Frente Amplio y Podemos en la C. Valenciana (Compromís-Front Valencià) y en Canarias (Unidad
    del Pueblo Canario, con Nueva Canarias); conservan todos los votos de sus partes.
  - Nueva Canarias pasa a candidatura local (congelada en su base de 2023) en vez de ir dentro de «Otros».
- `frente_amplio` pasa a `lista_unica`: la hipótesis de Frente Amplio y Podemos juntos en toda España, que no se ha
  dado, para comparar. Desaparece `separados`.
- **Senado** (`motor/senado.py`): los 208 senadores electos se reparten en cada simulación desde el voto simulado al
  Congreso, con voto limitado (3 + 1, 2 + 1, 2 + 0 y 1), islas desde el patrón insular del Congreso de 2023, ASG y AHI
  fijos en su voto al Senado de 2023, el 2 + 2 sorteado con la caída de voto entre candidatos medida en 2023, y la
  coalición Senado de Progreso (PSOE + Frente Amplio en 46 provincias y La Gomera; acuerdo del 17 de octubre). Se
  calcula también sin la coalición para medir lo que aporta.
- Datos nuevos desde infoelectoral: Senado 2023 por circunscripción (`datos/raw/senado_2023-07.csv`) y Congreso 2023
  por isla (`datos/raw/congreso_2023-07_islas.csv`), generados con `datos/oficiales.py`.
- Validación `python -m validacion.validar_senado`: con el voto real al Congreso de 2023, el método da 199 de los 208
  senadores de 2023 (PP 122 frente a 120).

### Efecto
- Congreso (10.000 simulaciones, corte del 12 de octubre, `separados` → `registradas`): P(PP + Vox ≥ 176)
  92,7 % → 91,0 %; PP 130 → 129 y PSOE 108 → 107 escaños de mediana; Frente Amplio 12 (Sumar tenía 9) y Podemos 1
  (tenía 2); ERC 8 → 10.
- Senado: PP 106 senadores electos de mediana (123 sin la coalición), Senado de Progreso 67 y PSOE 16;
  P(PP ≥ 105 electos) 51 % (79 % sin la coalición).

- Senado completo: se suman los 58 senadores de designación autonómica actuales (`datos/senado_designados.csv`,
  web del Senado a 17/10/2026; PP 23, PSOE 19, Vox 5, Junts 3 y uno de ERC, BNG, Geroa Bai, PNV, EH Bildu,
  Compromís, Más Madrid y CC). Con ellos, PP 129 de 266 de mediana y mayoría absoluta (134) en el 43 % de las
  simulaciones (73 % sin la coalición).

### Interfaz y herramientas
- Página `/senado`: hemiciclo de 208, comparación con y sin coalición, mapa por provincias (lista con más senadores o
  senador en juego, con el detalle de cada isla) tabla de las 59 circunscripciones y sección del Senado completo (266) con los designados por comunidad. Acceso desde el resumen.
- `scripts.prediccion_2026` acepta `registradas|lista_unica` y guarda también `senado_<fecha>_<escenario>.csv`.
- `pyproject.toml` con los metadatos del proyecto, la configuración de pytest (sustituye a `pytest.ini`) y la de
  ruff. Código limpio de avisos de lint.
- Hook de pre-commit en `.githooks/` (ruff y tests; `validar_motor` si cambia `motor/escanos.py`) y workflow de
  GitHub Actions con las mismas comprobaciones y la integridad de los datos.
- `requirements-dev.txt` con las herramientas de desarrollo.

## [1.0.0] – 2026-10-16

Primera versión bajo control de versiones.

### Modelo
- Motor de escaños D'Hondt (LOREG art. 163) que reproduce los 350 escaños de 2015, 2016, 2019-A, 2019-N y 2023.
- Agregador de encuestas con sesgos de casa, calibrado con backtest en 5 elecciones y validación
  leave-one-election-out.
- Capa autonómica (16 encuestas en 9 CCAA con encogimiento bayesiano) y reparto provincial por swing logit.
- Monte Carlo de escaños con error nacional calibrado en 5 elecciones y backtest fuera de muestra en 4.

### Efecto
- Predicción de referencia con corte del 12 de octubre (333 encuestas, la última del 11 de octubre):
  `resultados/prediccion/`, huella del modelo `3a0e724c84f4d447`.

### Interfaz y herramientas
- Web propia (Starlette + plotly.js) con resumen, escaños, mayorías, provincias, encuestas, evolución,
  participación y metodología.
- Procedencia de las predicciones: cada salida lleva un JSON con commit, huella, escenario, encuestas usadas y
  SHA-256 de los ficheros.
