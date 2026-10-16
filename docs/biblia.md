# Biblia del modelo 29-N

Documento de referencia para explicar el modelo: qué es, cómo funciona, cómo se leen sus cifras, en qué se basa cada
supuesto y cómo presentarlo sin decir más de lo que sabe. Lo vamos editando.

*Última revisión: 15 de octubre de 2026. Datos de ejemplo: encuestas hasta el 12 de octubre, escenario base.*

---

## 1. Qué es y qué no es

Es un **modelo de agregación y simulación**: combina las encuestas publicadas por otros y calcula cuántas veces sale cada
resultado en miles de elecciones simuladas.

- **No es una encuesta.** No pregunta a nadie ni tiene trabajo de campo propio. Toma lo que publican CIS, GAD3, 40dB,
  Sigma Dos y el resto.
- **No es una predicción a secas.** Es una estimación **condicionada a las encuestas**: si todas fallan en la misma
  dirección más de lo que fallaron entre 2015 y 2023, el modelo falla con ellas.
- **Es de la misma familia** que los modelos de FiveThirtyEight o The Economist: media de encuestas, error medido en
  elecciones pasadas y simulación.
- **Uso personal.** Modelo propio construido con datos públicos: encuestas recogidas en Wikipedia y resultados oficiales
  de infoelectoral.

Una frase para definirlo:

> Modelo de estimación de escaños a partir de la media de encuestas publicadas, que simula la elección miles de veces
> con el error que tuvieron las encuestas entre 2015 y 2023.

---

## 2. Cómo funciona, paso a paso

Cuatro pasos llevan de las encuestas publicadas a los 350 escaños; los tres primeros dan un resultado central y el
cuarto le añade la incertidumbre.

1. **Media de encuestas** (`motor/agregador.py`). Junta todas las encuestas nacionales y estima la tendencia día a día de
   cada partido. Corrige el sesgo propio de cada casa (por ejemplo, el CIS da al PP casi 7 puntos menos que la media).
   - La corrección es relativa: supone que el conjunto de casas no tiene sesgo. El error común de toda la industria no
     se ve aquí; se añade en el paso 4.
   - Excluye las encuestas encargadas por partidos y las que ya son medias de otras (KeyData).
2. **Comunidades autónomas** (`motor/regional.py`). Donde hay encuestas autonómicas recientes (CEO, Sondaxe, GAD3…),
   corrige cómo se reparte el voto por territorio sin cambiar el total nacional.
3. **Provincias** (`motor/swing.py`). Lleva el voto de cada comunidad a cada provincia a partir del resultado de 2023,
   con un ajuste logístico (un partido muy fuerte en una provincia no puede subir sin límite).
4. **Simulación** (`motor/montecarlo.py`, `motor/escanos.py`). Repite la elección 5.000 veces. En cada una mueve el voto
   con los errores medidos entre 2015 y 2023:
   - error de bloque (izquierda contra derecha);
   - trasvases dentro de cada bloque;
   - desviaciones por comunidad y por provincia.

   Después reparte los escaños de cada provincia con D'Hondt y el umbral del 3 %, igual que la ley. El motor reproduce
   exactamente los 350 escaños de las cinco elecciones de 2015 a 2023.

El resultado no es un número, sino 5.000 parlamentos posibles. Todo lo que muestra la web sale de contarlos.

---

## 3. Cómo leer los resultados

Cada cifra de la web cuenta algo en las 5.000 simulaciones; ninguna es una certeza.

| Cifra | Qué significa | Ejemplo (12 de octubre) |
| --- | --- | --- |
| Porcentaje de un escenario | En cuántas simulaciones ocurre | PP y Vox suman 176 o más en el 92 % |
| Mediana de escaños | El valor del medio: la mitad de las simulaciones da más y la mitad menos | PP: 130 escaños |
| Rango del 80 % | Entre esos dos valores cae el 80 % central de las simulaciones | PP: 109–156 |
| Rango del 95 % | Ídem con el 95 %; recoge casos más extremos | PP: 95–168 |
| Voto estimado | Resultado central de la media de encuestas, ya corregida | PP: 31,3 % |
| Hemiciclo | Reparto medio de las simulaciones redondeado a 350: una foto típica, no un resultado concreto | PP 131, PSOE 109, Vox 67 |

Tres avisos al leerlas:

- **Un 92 % no es «seguro».** Significa que en 8 de cada 100 simulaciones no pasa. Las cosas con un 8 % ocurren a menudo.
- **Las cifras dependen del modelo.** Son frecuencias dentro de sus supuestos, no probabilidades validadas con una serie
  histórica larga.
- **El hemiciclo y las medianas no suman lo mismo.** La mediana de cada partido se calcula por separado, así que las
  medianas no tienen por qué sumar 350.

---

## 4. Cuánto se equivoca

El modelo se ha probado contra las elecciones reales de 2015 a 2023 (detalle en el README y en `resultados/validacion/`).

| Prueba | Resultado |
| --- | --- |
| Error de la media de encuestas la víspera | Entre 0,75 y 2,02 puntos por partido, según la elección |
| Error en la elección no vista (calibración dejando fuera una elección cada vez) | 1,92 puntos por partido |
| Paso a provincias con el resultado por CCAA perfecto | Unos 7 escaños mal colocados por elección |
| Paso a provincias con sólo el resultado nacional perfecto | Unos 18 escaños mal colocados |
| Backtest fuera de muestra (2016, 2019A, 2019N, 2023; a 30, 14 y 1 días) | El escaño real cayó dentro del intervalo del 80 % en el 76 % de los casos, y dentro del 95 % en el 93 % |
| Error medio de escaños por partido estatal | 8 escaños (22 si se repite la elección anterior) |

### ¿Valen algo las probabilidades?

Lo comprueba `python -m validacion.evaluar_probabilidades`: puntúa la distribución entera, no sólo si el resultado cae
en un intervalo, y la compara con dos referencias que no dan probabilidades. La primera es la proyección central del
modelo sin simular («el PP saca 124»); la segunda, repetir la elección anterior.

| Medida (fuera de muestra, 2016–2023) | Modelo | Proyección central | Repetir la anterior |
| --- | --- | --- | --- |
| CRPS por partido estatal, en escaños (menor es mejor) | 5,7 | 8,0 | 21,9 |
| Brier de «el partido saca al menos k escaños» | 0,034 | 0,044 | 0,139 |
| Brier de «la derecha suma 176» y «el PP supera al PSOE» | 0,073 | 0,125 | 0,250 |

- **Simular aporta.** Las probabilidades puntúan entre un 23 % y un 41 % mejor que dar sólo el resultado central, en las
  cuatro elecciones y a 30, 14 y 1 días.
- **Las colas son estrechas.** Los intervalos aciertan bien hasta el 60 %, pero el del 70 % acierta un 65 %, el del
  80 % un 76 % y el del 90 % un 87 %.
- **Lo «imposible» pasa a veces.** Cuando el modelo da menos de un 2 % a algo, ocurrió el 6 % de las veces. Casi siempre
  son candidaturas nuevas (PRC, Teruel Existe, CUP), más Vox en noviembre de 2019.
- **El percentil medio del resultado real es 0,45**: una ligera tendencia a sobreestimar.

Cómo decirlo: «En las elecciones de 2016 a 2023, las probabilidades del modelo puntuaron mejor que su propia estimación
central, pero sus márgenes se quedaron algo cortos». Con cuatro elecciones son tendencias, no una prueba.

Qué quiere decir: los intervalos son **algo estrechos**. Un intervalo del 80 % debería acertar el 80 % de las veces y
acertó el 76 %; el modelo es un poco optimista con su propia precisión.

Fallos conocidos:

- **Vox en noviembre de 2019:** sacó 52 escaños; el modelo daba 24–32 a un mes y a dos semanas.
- **Espacio de Podemos:** lo sobreestima de forma sistemática, unos 7 escaños de media.
- **23J (2023):** a 30 días daba un 78 % de mayoría a PP, Vox y UPN, que no se produjo (sacaron 171).

---

## 5. Participación

### Qué hace el deslizador

Con la participación del **65 %** el modelo **no añade nada**: las encuestas ya llevan dentro su propio supuesto de
participación, y el 65 % es la media de lo que declaran las que la publican (julio–octubre de 2026).

Mover la participación es un **escenario hipotético** («¿y si…?»), no algo que el modelo estime:

- si sube, añade votantes nuevos y los reparte según una regla fija;
- si baja, los quita con esa misma regla;
- dentro de cada bloque, los votantes nuevos se reparten en proporción al voto actual de cada partido.

El código está en `motor/pipeline.py` (`ajuste_participacion` y `REPARTOS`).

### En qué se basa la regla «como en 2015–2023»

Es una regresión de los votos de cada bloque frente al total de votantes en las cinco elecciones generales de 2015 a
2023 (`scripts/analisis_electopanel_y_bloques.py`; datos en `resultados/analisis/bloques_2015_2023.csv`).

| Elección | Participación | Votantes (M) | Derecha (M) | Izquierda (M) |
| --- | --- | --- | --- | --- |
| Diciembre de 2015 | 69,7 % | 25,4 | 10,8 | 11,7 |
| Junio de 2016 | 66,5 % | 24,3 | 11,1 | 10,5 |
| Abril de 2019 | 71,8 % | 26,5 | 11,3 | 11,5 |
| Noviembre de 2019 | 66,2 % | 24,5 | 10,5 | 10,5 |
| Julio de 2023 | 66,6 % | 25,0 | 11,3 | 10,9 |

Derecha = PP, Cs, Vox y derecha navarra. Izquierda = PSOE y su izquierda.

Lo que se ve: el voto de la derecha es casi constante (10,5–11,3 millones); el de la izquierda se mueve con la
participación (11,5 millones en abril de 2019 frente a 10,5 en 2016 y noviembre de 2019).

| Por cada 100 votantes de más… | Regresión (recalculada) | Lo que usa el modelo |
| --- | --- | --- |
| Izquierda | 51 (r = 0,82) | 57 |
| Derecha | 19 (r = 0,45) | 18 |
| Resto (nacionalistas, regionalistas…) | 30 | 25 |

La diferencia entre 51/19/30 y 57/18/25 probablemente se debe a que la recalculada usa el total de votantes y la
original los votos válidos. **Pendiente de comprobar.**

### Los tres repartos

| Reparto | Izquierda / derecha / resto (de cada 100 votos extra) | De dónde sale |
| --- | --- | --- |
| Como en 2015–2023 | 57 / 18 / 25 | La regresión de arriba |
| Simétrico, como el 10N | 49 / 45 / 6 | Cómo cayó la participación entre abril y noviembre de 2019 |
| Muy asimétrico | 80 / 5 / 15 | No viene de ningún dato: es una prueba de estrés |

### Por qué cambian las probabilidades

Es pura mecánica:

1. Más participación añade sobre todo votos de izquierda (con el reparto histórico).
2. Eso sube su porcentaje y sus escaños.
3. Baja la frecuencia de mayoría de PP y Vox.

Con menos participación pasa lo contrario. El modelo **no dice que la participación vaya a subir**: dice qué pasaría si
sube y los votantes adicionales se comportan como en 2015–2023.

### Hasta dónde llega esta base

- **Sólo cinco elecciones.** Con cinco puntos, una regresión es muy frágil; la de la derecha apenas tiene relación
  (r = 0,45).
- **Es una correlación entre elecciones, no un dato sobre los votantes marginales.** Que en las elecciones con más
  participación ganara votos la izquierda no prueba que los abstencionistas de 2026 sean de izquierdas. En abril de 2019
  se movilizó la izquierda ante la llegada de Vox; la próxima vez puede movilizarse otro bloque.
- **El reparto dentro del bloque es un supuesto.** Que los nuevos votantes de izquierda se repartan como el voto actual
  de PSOE, Sumar y Podemos no está medido.

### Cómo presentarlo

Como un **análisis de sensibilidad**, no como una afirmación:

> «Si la participación supera el 65 % que suponen las encuestas y los votantes adicionales se reparten como entre 2015 y
> 2023, la mayoría de PP y Vox baja del X % al Y %. Con un reparto simétrico, apenas cambia.»

---

## 6. Cómo presentarlo

| En lugar de… | Mejor… |
| --- | --- |
| «El PP ganará las elecciones» | «El PP queda primero en el 77 % de las simulaciones» |
| «PP y Vox tienen un 92 % de probabilidad de gobernar» | «PP y Vox suman mayoría absoluta en el 92 % de las simulaciones» |
| «Encuesta propia» | «Modelo basado en la media de encuestas publicadas» |
| «El PP sacará 130 escaños» | «El PP sacaría entre 109 y 156 escaños; 130 es la mediana» |
| «Si sube la participación gana la izquierda» | «Si sube la participación y los nuevos votantes se comportan como en 2015–2023, baja la mayoría de PP y Vox» |
| «El bloque de 2023 no puede gobernar» | «El bloque de 2023 llega a 176 en el 6 % de las simulaciones; que llegue no garantiza la investidura» |

Texto corto de presentación:

> Modelo de estimación de escaños a partir de la media de encuestas publicadas. Simula la elección 5.000 veces con el
> error que tuvieron las encuestas entre 2015 y 2023. Los porcentajes indican en cuántas simulaciones ocurre algo, no la
> certeza de que vaya a ocurrir.

---

## 7. Límites conocidos

- **Serie histórica corta.** La calibración nacional usa cinco elecciones y el backtest cuatro (2015 no tiene elección
  base).
- **Candidaturas nuevas.** Las que no se presentaron en la elección anterior quedaron fuera de sus intervalos en el
  backtest. En 2026 afecta a SALF y a Adelante Andalucía.
- **Distancia a la elección.** El error de las encuestas está medido hasta 48 días antes de votar; con fechas anteriores
  se extrapola.
- **Partidos de una sola comunidad** (ERC, Junts, PNV, EH Bildu, BNG, CC). No tienen error de campaña propio; su
  incertidumbre probablemente se queda corta.
- **Participación.** Es un supuesto, no una estimación (ver sección 5).
- **Frente Amplio.** El escenario supone que la lista conjunta conserva todos los votos de Sumar y Podemos.
- **«Otros».** Ayuda a calcular el umbral, pero no puede obtener escaños: una candidatura nueva con voto concentrado
  tendría que añadirse al modelo a mano.
- **Investidura.** Sumar 176 escaños no garantiza un Gobierno: el modelo cuenta escaños, no negociaciones.

---

## 8. Aviso legal

La ley electoral (LOREG, art. 69) prohíbe difundir sondeos electorales en los cinco días anteriores a la votación. Para
el 29 de noviembre, eso es **desde el 24 de noviembre**. Una media de encuestas probablemente entra en esa prohibición:
si se publica el modelo, conviene no actualizarlo ni difundirlo en esos días.

*Pendiente: confirmar el alcance exacto del artículo y los requisitos de ficha técnica.*

---

## 9. Preguntas abiertas

- [ ] Comprobar por qué la regresión de participación recalculada (51/19/30) no coincide con la del modelo (57/18/25).
- [ ] Decidir si se añade la explicación de la sección 5 a las páginas de Participación y Metodología de la web.
- [ ] Confirmar el alcance de la LOREG art. 69 para una media de encuestas.
- [ ] ¿Hay que ampliar el error de los partidos de una sola comunidad?
- [ ] Las colas son estrechas (intervalo del 90 % → 87 %; sucesos de menos de un 2 % → 6 %): ¿ensanchar las colas o añadir un error específico para candidaturas nuevas (SALF, Adelante)?
