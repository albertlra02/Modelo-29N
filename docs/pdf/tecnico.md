# Modelo 29-N: la aplicación

Oct 20, 2026 · @Alberto

## Qué es

Es una aplicación web que he desarrollado para seguir las generales del 29 de noviembre. Coge las encuestas publicadas, las convierte en 10.000 elecciones simuladas al Congreso y al Senado y te deja cambiar en directo los supuestos que más pesan en el resultado: la participación, cuánto se moviliza cada bloque, el voto útil, las candidaturas o si Vox se retira del Senado en algunas provincias.

La pregunta que intenta responder es sencilla: con lo que dicen hoy las encuestas, ¿cada cuánto sale cada mayoría, y qué tendría que pasar para que cambie? No hago trabajo de campo. Todo sale de datos públicos: las encuestas que se publican, los resultados oficiales del Ministerio del Interior y las encuestas autonómicas.

Lo que creo que la diferencia de lo que se puede encontrar en medios y agregadores es que permite jugar con escenarios, y no sólo ver una predicción. Calcula el Senado completo, con su voto limitado, las islas, la coalición de PSOE y Frente Amplio y los senadores designados por las comunidades. Usa las candidaturas reales que se han registrado para el 29-N. Y el margen de error no me lo invento: está medido con las generales de 2015 a 2023, y la he probado con elecciones que no conocía. Además, cada predicción queda registrada con los datos y la versión que la produjeron, así que cualquier cifra se puede reproducir.

Se usa desde el navegador, sin instalar nada. Este documento acompaña a otro de análisis, «Una mayoría que depende de quién vote», en el que uso la aplicación para estudiar el peso de la participación y del Senado.

## Cómo está organizada

Tiene seis secciones, y todas comparten el mismo escenario: lo que cambias en el panel se aplica en todas las páginas y queda guardado en la dirección, así que puedes guardar o mandar cualquier vista tal cual.

| Sección | Qué muestra |
| --- | --- |
| Resumen | Titular, hemiciclo con el reparto medio, probabilidades principales y ficha de cada partido |
| Congreso | Voto y escaños con sus rangos y descarga de las simulaciones; calculadora de cualquier suma de partidos; mapa y tabla de las 52 provincias con el escaño en juego |
| Senado | 208 electos y pleno de 266, con y sin la coalición Senado de Progreso, las hipótesis de retirada de Vox, mapa con el detalle de cada isla y designados por comunidad |
| Escenarios | Barrido de participación; simulador «¿Y si…?» que fija el voto de cualquier partido; dos escenarios lado a lado |
| Encuestas | Media actual, serie de cada partido, sesgo de cada encuestadora y evolución semana a semana |
| Cómo funciona | Pasos, supuestos con su justificación y fuentes, validación y límites |

La noche del 29-N se añade una séptima sección que va proyectando los escaños a medida que avanza el escrutinio.

### Lo que se puede cambiar

| Palanca | Valores | Qué hace |
| --- | --- | --- |
| Encuestas hasta | Cortes semanales desde junio | Usa sólo las encuestas terminadas antes de esa fecha: muestra qué decía el modelo entonces |
| Candidaturas | Registradas / lista única | Las coaliciones registradas el 16 de octubre, o la hipótesis de Frente Amplio y Podemos juntos en toda España |
| Participación | 60 a 76 % | Suma o resta votantes respecto al 65 % que suponen las encuestas |
| Reparto de votantes adicionales | Histórico, simétrico, muy asimétrico | De cada 100 votos extra: 57/18/25 (izquierda/derecha/resto), 49/45/6 o 80/5/15 |
| Movilización por bloque | −20 a +20 %, en España o una comunidad | Sube o baja el voto de la izquierda, la derecha o los nacionalistas y regionalistas |
| Voto útil | 0 a 50 %, en todas las provincias o sólo donde el partido no saca escaño | Podemos → Frente Amplio, Frente Amplio → PSOE, Vox → PP, SALF → Vox |
| Simulaciones y semilla | 2.000 a 10.000 | Misma semilla y mismo escenario dan exactamente el mismo resultado |

Los escenarios más habituales están calculados de antemano y se abren al momento. Uno nuevo tarda unos segundos, y mientras tanto la página va enseñando el progreso.

## Cómo funciona

La aplicación no da un resultado, sino muchos. Repite la elección 10.000 veces, cada vez con un error distinto en las encuestas (del tamaño de los que han tenido de verdad), y cuenta cuántas veces sale cada cosa. El proceso tiene cuatro pasos:

&#91;embedded content: Método · 3 fuentes de datos, 4 pasos, 2 resultados\]

1. **Media de encuestas.** Junto todas las encuestas publicadas y sigo la tendencia de cada partido día a día. Cada empresa tiene su propio sesgo (unas dan sistemáticamente más a un partido que otras), y el modelo lo estima y lo descuenta.
2. **Comunidades.** Donde hay encuestas autonómicas recientes, las uso para corregir cómo se reparte el voto entre comunidades, sin cambiar el total nacional.
3. **Provincias.** Llevo el voto a cada una de las 52 provincias partiendo del resultado de 2023, con las candidaturas reales del 29-N y con el escenario que haya elegido el usuario.
4. **Simulación.** En cada una de las 10.000 elecciones el voto se mueve con los errores que han tenido las encuestas entre 2015 y 2023: uno común a cada bloque (cuando fallan, la izquierda y la derecha suelen fallar a la vez en sentido contrario), trasvases dentro de cada bloque y desviaciones por comunidad y por provincia. Cuantos más días faltan para votar, más grande es el error.

Con cada una de esas elecciones simuladas reparto el Congreso con D’Hondt y el umbral del 3 %, exactamente como manda la ley, y el Senado con su voto limitado, isla a isla, con la coalición Senado de Progreso y los 58 senadores que designan los parlamentos autonómicos. Todo lo que enseña la aplicación (medianas, rangos, la probabilidad de cada mayoría) sale de contar esos 10.000 parlamentos.

## Las decisiones, una a una

Un modelo electoral es una cadena de decisiones, y en casi todas hay varias opciones razonables. En esta sección explico las que he tomado, qué alternativas había y cómo he comprobado que la elegida funciona. La regla que he seguido es sencilla: cada opción se prueba contra las generales de 2015 a 2023, y si no mejora el resultado en elecciones pasadas, no entra. Cuando no hay forma de probarla, lo digo y la dejo como algo que el usuario puede cambiar.

### 1. De dónde salen las encuestas

Uso la recopilación de Wikipedia de todas las encuestas publicadas, que recoge la empresa, el medio, las fechas de campo, la muestra y la estimación de cada partido, y se mantiene al día. La alternativa era ir a la web de cada empresa, que es mucho más lento y no aporta nada. La descarga es automática, pero se detiene si la tabla cambia de forma (por ejemplo, si aparece un partido nuevo), para no meter datos mal leídos sin darme cuenta.

Dejo fuera dos tipos de encuesta: las encargadas por un partido, porque tienen un interés evidente en el resultado, y las que ya son una media de otras encuestas, porque contaría dos veces los mismos datos.

### 2. Cómo promediar las encuestas

Una media simple trata igual a todas las empresas, pero cada una tiene su propio sesgo, estable en el tiempo: unas dan sistemáticamente más a un partido que otras. Por eso uso el enfoque más habitual en la literatura ([Jackman, 2005](http://www.uh.edu/hobby/eitm/_docs/past-lectures/2015-lectures/harold-clarke/pooling-the-polls-over-an-election-campaign.pdf)): el voto real de cada partido cambia poco a poco de un día para otro, y cada encuesta lo mide con el sesgo de su empresa más su error de muestra. El modelo estima a la vez la tendencia y el sesgo de cada casa.

Dos parámetros deciden lo nerviosa que es la media: cuánto puede moverse el voto real cada día y cuánto error tiene una encuesta además del de la muestra. No los elegí a ojo. Probé una rejilla de valores dejando fuera cada vez una de las cinco elecciones y midiendo el error en la que quedaba fuera, y en las cinco ganó la misma combinación: 0,2 puntos al día y 0,6 puntos de error extra. Con ella, el error medio en la elección que el modelo no había visto fue de 1,92 puntos por partido.

Hay un supuesto que conviene tener claro: para medir el sesgo de cada casa hay que fijar un «cero», y lo fijo suponiendo que la media de todas las empresas no está sesgada. No es del todo cierto, porque a veces fallan todas a la vez hacia el mismo lado; ese error común no lo corrige la media y lo añado aparte en la simulación (decisión 6).

### 3. Las comunidades autónomas

Una encuesta nacional dice bastante bien cuánto vota cada partido en toda España, pero no cómo se reparte ese voto por territorios. Donde hay encuestas autonómicas recientes (el CEO en Cataluña, Sondaxe en Galicia, GAD3 y otras) las uso, aunque no tal cual, porque una sola encuesta regional también puede estar sesgada. Combino lo que diría el voto nacional repartido como en 2023 con lo que dicen las encuestas de la comunidad, dándole más peso a las grandes y a las recientes (una actualización bayesiana), con 1,5 puntos de error propio por encuesta y 2 puntos al año de deriva por antigüedad. Después vuelvo a cuadrar el total nacional con la media de encuestas.

### 4. De las comunidades a las provincias

Para llevar el voto a cada provincia hay tres opciones clásicas: sumarle a todas los mismos puntos (swing uniforme), multiplicar su voto anterior por el mismo factor (proporcional) o moverlo en una escala logística, que frena a un partido cuando ya es muy fuerte. Para elegir hice una prueba con trampa a favor: dar a cada método el resultado real de cada comunidad en las cuatro transiciones entre elecciones de 2015 a 2023, y contar cuántos escaños colocaba mal en las provincias.

| Método | Escaños mal colocados por elección |
| --- | --- |
| Uniforme, con el resultado de cada comunidad | 6,2 |
| Logístico, con el resultado de cada comunidad | 6,8 |
| Proporcional, con el resultado de cada comunidad | 8,2 |
| Logístico, sólo con el resultado nacional | 17,8 |
| Repetir la elección anterior | 61,5 |

De aquí salen dos decisiones. La primera, que lo que de verdad importa es trabajar por comunidades: pasar del resultado nacional al de cada comunidad baja el error de unos 18 a unos 7 escaños, y por eso existe el paso 3. La segunda es el método. El uniforme acierta un poco más que el logístico, pero puede dar porcentajes negativos a un partido que cae mucho y hace crecer sin límite a los que ya son muy fuertes en una provincia; elegí el logístico porque se porta mejor en los casos extremos. Para Vox, cuyo reparto provincial ha cambiado mucho de una elección a otra, cada simulación mezcla las dos formas en una proporción al azar, porque los datos no permiten decidir cuál de las dos acertará.

### 5. El reparto de escaños

En cada provincia uso D’Hondt con el umbral del 3 % sobre los votos válidos, como manda la ley electoral. Antes de usarlo lo validé con los votos oficiales: reproduce exactamente los 350 escaños de cada una de las cinco generales de 2015 a 2023, incluidos los desempates. Dentro de la simulación uso una versión que reparte las 10.000 elecciones a la vez, que da el mismo resultado y es mucho más rápida.

### 6. Cómo medir la incertidumbre

Esta es la decisión que más pesa en el resultado. El propio agregador dice que su margen de error es pequeño, entre 0,4 y 0,7 puntos por partido, pero en las elecciones de 2015 a 2023 el error real fue varias veces mayor. Lo que domina no es el error de muestra, sino que todas las encuestas fallen a la vez (en 2023, la media infravaloró al PSOE en 3,2 puntos) y que la campaña mueva votos. Así que la incertidumbre no la saco del agregador, sino de medir cuánto se equivocó de verdad la media en las cinco elecciones.

Mi primera versión trataba el error de cada partido por separado, y daba a la suma de PP y Vox una incertidumbre de unos 8 puntos, que no tiene sentido. Dentro de un bloque los errores se compensan: en noviembre de 2019, a 48 días de votar, las encuestas daban 6,5 puntos de más a Ciudadanos y 6,8 de menos a Vox, pero el bloque de derechas sólo falló en medio punto. Por eso la cambié por un error de bloque: izquierda y derecha fallan a la vez en sentido contrario, y dentro de cada bloque hay trasvases entre partidos que suman cero.

Con los datos de 2015 a 2023, el error del bloque de derechas es de 2,1 puntos la víspera y el de izquierdas de 1,8, y los dos llegan a 3,6 a 48 días de votar. La correlación medida entre ambos fue de −0,74; uso −0,65, algo más prudente. Encima añado dos colchones, porque con sólo cinco elecciones lo peor que puede pasar es quedarse corto: multiplico el error por 1,10 y uso colas gruesas (una t de Student con 5 grados de libertad), para que los fallos grandes sean algo más probables que con una normal. Entre la víspera y los 48 días, el error crece como lo haría un paseo aleatorio:

&#91;embedded content: Calibración del modelo con las generales de 2015 a 2023 · incluye el margen de prudencia de un 10 %\]

A todo esto se suman una desviación por comunidad (pequeña donde hay encuestas autonómicas recientes) y un ruido por provincia, los dos medidos con los resultados de 2016 a 2023. Un límite que reconozco: los partidos de una sola comunidad (ERC, Junts, PNV, EH Bildu, BNG, CC) no tienen un error de campaña propio, así que su incertidumbre probablemente se queda corta.

### 7. Las candidaturas del 29-N

Las encuestas se siguen publicando con las etiquetas de siempre, pero el 16 de octubre se registraron candidaturas nuevas, así que he tenido que traducir unas a otras. El Frente Amplio (IU, Movimiento Sumar, Más Madrid, Comuns y sus aliados territoriales) ocupa el espacio que las encuestas llaman «Sumar», y Podemos va por su cuenta.

Hay tres territorios con reglas propias. En la Comunitat Valenciana y en Canarias, Frente Amplio y Podemos van en una sola lista (Compromís-Front Valencià y Unidad del Pueblo Canario, esta con Nueva Canarias). Supongo que esas listas conservan todos los votos de sus partes, y sé que es optimista: la única fusión parecida que se puede medir en España, Unidos Podemos en 2016, conservó el 83 % de los votos que Podemos e IU habían sacado por separado en 2015, y la literatura explica por qué parte del electorado del socio menor no sigue a su partido ([Gschwend y Hooghe, 2008](https://madoc.bib.uni-mannheim.de/25457/)). En Cataluña, Podemos no presenta lista y pide el voto para ERC; supongo que el 60 % de sus votantes sigue la consigna y el 40 % se va a los Comuns. Este reparto no tiene precedente con el que calibrarlo, así que medí cuánto importa: entre mandarlo todo a ERC y mandar sólo el 30 %, ERC pasa de 11 a 9 escaños y la mayoría de PP y Vox no se mueve.

Las candidaturas que no tienen una base comparable en 2023 necesitan otra referencia para saber cómo se reparten por provincias: la división entre Sumar y Podemos sale de las europeas de 2024, igual que el patrón de SALF, y el de Adelante Andalucía, de una encuesta provincial. Además, mantengo como hipótesis comparativa una lista única de Frente Amplio y Podemos en toda España, que no se ha dado, para poder medir cuánto les cuesta ir separados.

### 8. La participación

Las encuestas que publican su estimación de participación suponen de media un 65 %, y ese es el punto de partida. El usuario puede moverla entre el 60 % y el 76 %, y entonces hay que decidir a quién votan los que se suman o se restan. Para eso hice una regresión de los votos de cada bloque sobre el total de votantes en las cinco generales de 2015 a 2023: de cada 100 votantes adicionales, 57 votaron izquierda, 18 derecha y 25 al resto.

No me fío del todo de esa regla. Cinco elecciones son pocas, para la derecha la relación es débil (r = 0,45), y la literatura no da una regla fija: en España la relación entre participación y voto al PSOE responde a varios mecanismos que no siempre empujan hacia el mismo lado ([Lago y Montero, 2009](https://reis.cis.es/index.php/reis/article/download/791/1003/1312)), y en otros países más participación sobre todo hace el resultado menos predecible ([Hansford y Gomez, 2010](https://www.cambridge.org/core/journals/american-political-science-review/article/estimating-the-electoral-effects-of-voter-turnout/8A880C28E79BE770A5CA1A9BB6CF933C)). Por eso no impongo una regla, sino que ofrezco tres: la histórica; una simétrica, que reproduce cómo cayó la participación entre abril y noviembre de 2019 (49 a la izquierda y 45 a la derecha); y una muy asimétrica (80 y 5), que no sale de ningún dato y sirve como prueba de estrés.

### 9. Movilización y voto útil

La regla de participación es nacional y no puede recoger lo que de verdad se discute en una campaña: que se movilice un bloque y no el otro, o una comunidad y no el resto. Por eso añadí una palanca que sube o baja hasta un 20 % el voto de la izquierda, la derecha o los nacionalistas, en toda España o en una sola comunidad, dejando igual el resto. La investigación sobre polarización justifica que estos movimientos existen ([Hobolt y Hoerner, 2020](https://researchonline.lse.ac.uk/id/eprint/100529/); [Harteveld y Wagner, 2023](https://dare.uva.nl/id/4d0dc46d-f01d-4429-9227-2e941dfcd6a1)), pero el tamaño lo elige el usuario.

El voto útil (Podemos al Frente Amplio, Frente Amplio al PSOE, Vox al PP, SALF a Vox) se aplica por defecto sólo en las provincias donde el partido pequeño no saca escaño con la proyección central. La razón es que ahí es donde su voto se pierde y donde cambiar de papeleta tiene sentido: en España el voto estratégico se concentra en las circunscripciones pequeñas y se forma mirando el resultado anterior ([Lago](https://aecpa.es/files/congress/7/actas/area04/GT12/Ilago.pdf)). Las dos palancas se aplican antes de simular, así que mueven a la vez el Congreso, el Senado y las mayorías.

### 10. El Senado

El Senado tiene un sistema muy distinto: en cada provincia se eligen cuatro senadores, pero cada votante sólo marca tres nombres, de modo que lo normal es que la lista más votada se lleve tres y la segunda uno. Las encuestas no preguntan por el Senado, así que tuve que decidir cómo pasar del voto al Congreso al voto al Senado.

La opción más sencilla es suponer voto de partido: que cada lista saca en el Senado lo mismo que su partido en el Congreso y que la gente marca a los tres candidatos de su partido. La investigación confirma que es lo que hace la mayoría de los electores (Montabes y Ortega, *Revista Española de Ciencia Política*, n.º 7). Pero no quise quedarme en eso, y lo probé con datos: apliqué el método al voto real al Congreso de 2023 y lo comparé con los senadores que salieron. Acertó 199 de 208 (al PP le daba 122 y sacó 120).

Los nueve fallos enseñan dónde están los límites del método. Cuatro eran provincias muy igualadas que acabaron dos y dos (Badajoz, Cáceres, Huelva y Valencia), porque el tercer candidato de la lista ganadora saca algo menos que el primero y el segundo de la otra lista lo adelanta. Eso sí lo he incorporado: medí esa caída entre candidatos en las 47 provincias de 2023 y ahora se sortea en cada simulación (en 2023 el dos y dos salió con márgenes del 1 al 2 %, y nunca con más del 3,5 %). Otros tres fallos fueron provincias donde las listas al Senado no coincidieron con las del Congreso (Barcelona, Gipuzkoa y Navarra), y los dos últimos, islas donde el voto al Senado se apartó del del Congreso (Tenerife y La Palma); esos no los puedo prever con este método.

Hay dos islas que trato aparte desde el principio: La Gomera y El Hierro, donde ganan partidos que no se presentan al Congreso (ASG y AHI). Como no hay encuesta que los mida, les dejo su voto al Senado de 2023, y por eso esos dos escaños salen bien en la validación de forma automática.

El resto de decisiones del Senado: las islas se calculan desde su provincia con el patrón que tuvo cada isla en el Congreso de 2023, municipio a municipio; la coalición Senado de Progreso suma íntegros los votos de PSOE y Frente Amplio en las 46 provincias del acuerdo más La Gomera (con la misma reserva que las listas conjuntas); y los 58 senadores que designan los parlamentos autonómicos se suman tal y como están hoy, según la web del Senado. Para la posible retirada de Vox supongo que el 80 % de su voto va al PP donde no se presente; no hay precedente directo, así que lo anclo en el 83 % de Unidos Podemos.

### 11. Dónde le conviene a Vox retirarse

Para responder en qué provincias le conviene a Vox no presentarse si la derecha quiere los tres quintos del Senado, probar todas las combinaciones es imposible: con 52 provincias hay más de cuatro mil billones. Me fijé en algo que lo simplifica mucho: retirarse en una provincia sólo cambia los senadores de esa provincia. Así que simulo cada provincia una vez, con las mismas 5.000 elecciones simuladas, y cualquier combinación se calcula sumando lo que cambia en cada una. Después elijo las provincias de una en una, siempre la que más sube la probabilidad de los tres quintos. Este método no garantiza la combinación óptima en todos los casos, pero como las provincias son independientes entre sí, se queda muy cerca.

### 12. Cuántas simulaciones

En local uso 10.000 simulaciones por escenario. Con ese número, una probabilidad en torno al 50 % tiene un margen de unos ±1 punto solo por el azar de la simulación, que es mucho menos que la incertidumbre real. La aplicación publicada usa 5.000, porque 10.000 necesitan unos 630 MB de memoria y el servidor gratuito tiene 512; el margen sube a unos ±1,4 puntos. Todas las simulaciones usan una semilla fija, de modo que el mismo escenario da siempre exactamente el mismo resultado.

## Cuánto acierta

Para saber si el modelo sirve de algo lo probé con las generales de 2016, las dos de 2019 y 2023, cada vez calibrándolo sin la elección que estaba intentando predecir y con las encuestas de 30, 14 y 1 días antes. El resultado: se equivoca en unos 8 escaños por partido, frente a 22 si simplemente repites la elección anterior.

| Prueba | Resultado |
| --- | --- |
| Reparto del Congreso | Reproduce los 350 escaños reales de las cinco generales de 2015 a 2023 |
| Media de encuestas, la víspera | Error medio por partido de 0,75 a 2,02 puntos según la elección |
| Escaño real dentro del rango del 80 % / 95 % (partidos estatales) | 76 % / 93 % |
| Error medio por partido estatal | 8,1 escaños (repetir la elección anterior: 21,9) |
| Simular frente a dar sólo una cifra central | Error de la distribución un 28 % menor |
| Senado, con el voto real de 2023 | 199 de 208 senadores bien asignados |

Para mí lo más importante no es el error medio, sino que los rangos digan la verdad. Si el modelo dice que un partido sacará entre 47 y 85 escaños el 80 % de las veces, eso debería cumplirse más o menos 8 de cada 10 veces:

&#91;embedded content: Backtest fuera de muestra · generales de 2016, abril y noviembre de 2019 y 2023 · partidos estatales\]

Hasta el 60 % los rangos aciertan prácticamente lo que prometen. Los más anchos se quedan algo cortos (el del 80 % acertó el 76 % de las veces), así que lo muy improbable pasa un poco más de lo que dice el modelo.

También ha fallado, y conviene decirlo. No vio venir la subida de Vox en noviembre de 2019 (sacó 52 escaños y la mediana a un mes era de 24), tampoco la caída de Ciudadanos, y tiende a sobrestimar el espacio de Podemos en unos 7 escaños. En 2023 daba entre un 69 y un 78 % a una mayoría de derechas que no llegó.

Cada predicción queda registrada con la versión del modelo, los datos y la semilla aleatoria que la produjeron, así que cualquier cifra que publique se puede volver a sacar exactamente igual.

## Datos y actualización

Todo lo que usa la aplicación son datos públicos, y las encuestas se actualizan solas cada día.

| Dato | Fuente | Actualización |
| --- | --- | --- |
| Encuestas nacionales | Todas las publicadas, recogidas en Wikipedia | Diaria; la última incorporada es del 17 de octubre de 2026 |
| Encuestas autonómicas | CEO, Sondaxe, GAD3 y otras | Con cada encuesta nueva |
| Resultados 2015–2023 y Senado 2023 | Ministerio del Interior (infoelectoral) | Fijos, sellados para detectar cualquier cambio |
| Senadores designados | Web del Senado | A 17 de octubre de 2026 |
| Candidaturas | Coaliciones registradas ante la Junta Electoral Central | 16 de octubre; las listas se cierran el 26 |

Cuando sale una encuesta nueva, la aplicación la incorpora, comprueba que el modelo sigue pasando todas sus pruebas, recalcula los escenarios habituales y publica la versión nueva. La noche electoral se puede cargar el escrutinio para ir proyectando los escaños a medida que avanza el recuento.

## Cómo se accede y cómo usarla

Se entra desde el navegador con un enlace y una contraseña, sin instalar nada. Cualquier escenario se queda guardado en la dirección de la página, así que se puede mandar a otra persona tal cual.

Un par de cosas a tener en cuenta. Del 24 al 28 de noviembre la ley electoral prohíbe publicar sondeos y proyecciones, así que esos días la aplicación se cierra sola y vuelve el 29 al cerrar los colegios. Y los porcentajes son frecuencias, no certezas: un 92 % significa que eso pasa en 92 de cada 100 elecciones simuladas con los supuestos del modelo. Lo que cambia el usuario en el panel (participación, voto útil…) son supuestos suyos, no estimaciones.

Está pensada para analistas, equipos de campaña y empresas de estudios de opinión que quieran explorar escenarios. No es una encuesta ni sustituye al trabajo de campo.

## Límites

El mayor riesgo, como en cualquier agregador, es que todas las encuestas fallen a la vez y hacia el mismo lado, y más de lo que fallaron entre 2015 y 2023. Eso no lo corrige nadie. Además:

- El error está calibrado con cinco elecciones y probado con cuatro, que es poco para las colas: lo muy improbable pasa algo más de lo que dice el modelo.
- Las candidaturas sin precedente en 2023 (SALF, Adelante Andalucía, las listas conjuntas) son las que peor se proyectan; en las pruebas, casi todos los fallos grandes vinieron de casos así.
- Para los partidos de una sola comunidad la incertidumbre probablemente se queda corta.
- Supongo que las listas conjuntas conservan todos los votos de sus partes, y eso es optimista.
- En el Senado supongo que la gente vota a los tres candidatos de su partido, así que no recoge el voto personal ni el cruzado.
- Cuenta escaños, no Gobiernos: que un bloque sume 176 no garantiza una investidura.

Lo siguiente que quiero hacer es comparar la proyección final con el resultado del 29-N para usarlo como un punto más de calibración, medir cuántos votos pierden de verdad las listas conjuntas y darle a los partidos autonómicos un error de campaña propio.

## Cómo lo he construido

Lo construí por etapas, y no pasaba a la siguiente hasta que la anterior aguantaba una prueba con datos reales. Primero, el reparto de escaños, hasta que reprodujo los 350 de las cinco generales de 2015 a 2023. Después, la media de encuestas, probada dejando fuera cada vez una elección; luego el paso a provincias, comparando métodos con el resultado real; después la simulación, calibrada con los errores de esas cinco elecciones y probada fuera de muestra. El Senado vino al final, validado con los 208 senadores de 2023, y la aplicación web se apoya en todo lo anterior sin añadir cálculos propios.

Está escrito en Python, con numpy y pandas para el cálculo, Plotly para los gráficos y un servidor web ligero, sin base de datos. Son unas 6.300 líneas de código y 101 pruebas automáticas que se ejecutan con cada cambio. Hay tres cosas que cuido especialmente:

- **Los datos fuente no se tocan a mano.** Los resultados oficiales se descargan del Ministerio del Interior y cada fichero está sellado con una huella digital, así que cualquier cambio accidental se detecta.
- **Cada predicción es reproducible.** Junto a cada resultado se guarda la versión del modelo, las encuestas usadas y la semilla de la simulación, de modo que cualquier cifra se puede volver a obtener exactamente.
- **Se actualiza solo, pero con freno.** La descarga diaria de encuestas se detiene si la tabla de origen cambia de forma, y la versión nueva sólo se publica si pasan todas las pruebas.

La aplicación publicada funciona en un servidor gratuito con poca memoria y poca CPU. Para que vaya rápida, los escenarios habituales (unos 170) están calculados de antemano, las páginas viajan comprimidas y se guardan en memoria una vez generadas. Tiene contraseña y se cierra sola durante la veda electoral.

He desarrollado el proyecto con ayuda de un asistente de inteligencia artificial (Claude, de Anthropic), que he usado para programar, revisar el código, buscar y contrastar fuentes y redactar la documentación. La IA no produce las cifras: todas salen de ejecutar el modelo sobre datos públicos, y cada decisión de este documento está respaldada por una prueba reproducible o por una referencia que se puede consultar. Usarla me ha permitido llegar mucho más lejos en el tiempo que tenía; lo que no cambia es que cada elección del método tiene que poder explicarse y defenderse, y eso es lo que he intentado hacer en estas páginas.

## Fuentes

- Jackman, S. (2005). [«Pooling the polls over an election campaign»](http://www.uh.edu/hobby/eitm/_docs/past-lectures/2015-lectures/harold-clarke/pooling-the-polls-over-an-election-campaign.pdf). *Australian Journal of Political Science*, 40(4).
- Jennings, W. y Wlezien, C. (2018). «Election polling errors across time and space». *Nature Human Behaviour*, 2(4). [Resumen](https://phys.org/news/2018-03-pre-election-polls-reliable.html).
- Hansford, T. G. y Gomez, B. T. (2010). [«Estimating the electoral effects of voter turnout»](https://www.cambridge.org/core/journals/american-political-science-review/article/estimating-the-electoral-effects-of-voter-turnout/8A880C28E79BE770A5CA1A9BB6CF933C). *American Political Science Review*, 104(2).
- Lago, I. y Montero, J. R. (2009). [«Participación y resultados electorales en España»](https://reis.cis.es/index.php/reis/article/download/791/1003/1312). *REIS*, 126.
- Hobolt, S. y Hoerner, J. (2020). [«The mobilising effect of political choice»](https://researchonline.lse.ac.uk/id/eprint/100529/). *European Journal of Political Research*, 59(2).
- Harteveld, E. y Wagner, M. (2023). [«Does affective polarisation increase turnout?»](https://dare.uva.nl/id/4d0dc46d-f01d-4429-9227-2e941dfcd6a1). *West European Politics*, 46(4).
- Lago, I. [«Rational expectations or heuristics? Strategic voting in multimember districts»](https://aecpa.es/files/congress/7/actas/area04/GT12/Ilago.pdf). Universitat Pompeu Fabra.
- Gschwend, T. y Hooghe, M. (2008). [«Should I stay or should I go?»](https://madoc.bib.uni-mannheim.de/25457/). *European Journal of Political Research*, 47(5).
- Montabes, J. y Ortega, C. «El voto limitado en las elecciones al Senado español». *Revista Española de Ciencia Política*, 7.
- Datos: Ministerio del Interior (infoelectoral), encuestas publicadas recogidas en Wikipedia, web del Senado.
