# Registro de cambios

Cambios del modelo y de sus cifras, del más reciente al más antiguo. Cada entrada dice qué cambió, por qué y
cuánto movió la predicción central (escenario `separados`, corte de encuestas más reciente). La versión sigue
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

### Herramientas
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
