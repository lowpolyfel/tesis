# 0013. Calibración del umbral como análisis de sensibilidad

- **Fecha:** 2026-10-06
- **Estado:** Aceptada

## Contexto

El umbral de divergencia (0.75) es provisional y se calibra en la Fase 3
(ADR 0002). La regla del proyecto es explícita: **no se ajusta el umbral para
que los casos salgan bien; si la similitud no separa los casos, es un
hallazgo.** La pantalla de Calibración tiene que ayudar a calibrar sin
convertirse en una perilla para ajustar el umbral hasta que el corpus "pase".

Dos hechos acotan el diseño:

- La similitud inicial de un término (ronda 0) **no depende del umbral**: es el
  coseno mínimo entre las paráfrasis de sus interpretaciones. El umbral solo
  decide qué se hace con ese número. Por eso la primera decisión del mecanismo
  se puede reconstruir con cualquier umbral sin volver a llamar a los
  embeddings ni a ningún LLM.
- Cada traza guarda la configuración con la que corrió (umbral incluido) y la
  configuración vigente se cambia en `.env` (ADR 0015). Un botón que moviera el
  umbral desde la interfaz rompería esa trazabilidad.

## Decisión

1. **Solo lectura.** El módulo `app/calibracion` nunca escribe la configuración
   ni las trazas, no recalcula embeddings y no llama a ningún LLM. Responde una
   sola pregunta: *qué habría decidido la regla `similitud >= umbral` con otros
   umbrales*, con las similitudes ya calculadas. Usa la misma función `decidir`
   que el grafo, así que el análisis y el mecanismo no pueden discrepar.
2. **Datos.** Por cada término que llegó al mecanismo de divergencia, su
   similitud **inicial**: el mensaje `similitud` de ronda 0 con valor no nulo,
   posterior a la última clasificación de la traza (un nodo reejecutado repite
   sus mensajes, ADR 0008). Se descartan:
   - las similitudes `null` (requisitos sin interpretaciones) y las que no son un
     número finito (el repositorio guarda `NaN` como `null`; si llegara otra cosa,
     el histograma no tendría dónde ponerla);
   - las de rondas de debate, que solo existen para los términos que el umbral
     real mandó a debate y miden interpretaciones ya refinadas;
   - las trazas que un reproceso (`origen.reproceso_de`) ya sustituyó, es decir,
     cuando el reproceso pasó por el mecanismo de divergencia. La cadena se sigue
     hacia atrás: si R02 reprocesa R01 y falla antes de la divergencia y R03
     reprocesa R02 y llega, R03 sustituye a R01 y a R02. Si ningún reproceso
     llegó (sigue en cola o falló antes), la traza anterior se conserva.

   Cada fila lleva `decision_real` (la que registró el mensaje, con el umbral de
   su traza; si el mensaje no la registró, se reconstruye con `decidir` y su
   umbral, y sin ninguno de los dos la fila se omite), `umbral_usado`,
   `tipo_ambiguedad` (las trazas anteriores al tipo se tratan como léxicas, ADR
   0010), `via` (`null` mientras se debate o si el requisito falló) y el estado
   del requisito. Las trazas en `error` cuentan con la similitud que alcanzaron.
3. **Rejilla de umbrales** de `desde` a `hasta` con `paso`, inclusive (por
   omisión `CALIBRACION_DESDE/HASTA/PASO`; la ruta acepta otros valores). Los
   umbrales se redondean a 6 decimales para que `0.5 + 5·0.05` sea `0.75`. El
   umbral configurado se agrega siempre, aunque no caiga en la rejilla, y su
   fila va marcada `configurado`: es la que reproduce lo que pasó. Por umbral se
   informa cuántos términos se aceptarían directo, cuántos irían a debate y
   cuáles **cambian** respecto de su decisión real.
4. **Distribución.** Histograma con ancho igual al `paso` y origen en `desde`,
   para que sus bordes coincidan con los umbrales de la rejilla. Cada bin es
   `[desde, hasta)`: un valor igual a un borde cae a la derecha, como en la regla
   `>=`, y los bins a la izquierda de un umbral de la rejilla suman exactamente
   sus debates (el configurado, si no cae en la rejilla, no es borde de ningún
   bin).
   Se acompaña de n, mínimo, máximo, media y mediana.
5. **Contraste con el ground truth, opcional.** Si la colección `evaluaciones`
   tiene un documento del proyecto con `etiquetas`
   `[{req_id, termino, ambiguo, tipo_ambiguedad}]` (contrato fijo con el módulo
   de evaluación), se usa el más reciente por proyecto. La clase positiva es
   **debate** y la verdad es `ambiguo`; se empareja por `req_id` y término
   normalizado. Por umbral: verdaderos y falsos positivos y negativos,
   precisión y exhaustividad (`null` cuando su denominador es cero), F1 (`null`
   cuando la precisión o la exhaustividad lo son; mismo criterio que la
   evaluación, ADR 0014) y los
   casos mal separados. `separacion` dice si **existe algún** umbral que mande a
   debate todos los ambiguos y ninguno de los otros (máximo de los ambiguos <
   mínimo de los no ambiguos). Las etiquetas sin similitud y las similitudes sin
   etiqueta se informan aparte, sin contarlas. Sin etiquetas,
   `con_ground_truth` es `null`; si el documento solo trae etiquetas que no
   cumplen el contrato, se devuelve igual, con `n_invalidas` y sin pares, para
   que el problema se vea.
6. **Avisos, no correcciones.** La respuesta advierte cuando las similitudes
   vienen de modelos de embeddings distintos, cuando hay términos decididos con
   un umbral distinto del configurado y cuando la similitud no separa los casos
   etiquetados. No filtra ni reajusta nada por su cuenta.
7. **Rutas.** `GET /proyectos/{proyecto_id}/calibracion` y `GET /calibracion`
   (todos los proyectos que no son de evaluación juntos, `proyecto_id: null`),
   con la misma forma (`app/calibracion/formas.py`). `desde >= hasta`, paso no
   positivo o fuera de rango responden 422. El paso mínimo es 0.001: solo
   protege el tamaño de la respuesta (a lo más 1001 umbrales más el configurado y
   2001 bins, porque el coseno está en [-1, 1]); no cambia ningún resultado. Una
   configuración con `CALIBRACION_DESDE >= CALIBRACION_HASTA` se rechaza al
   arrancar (`Settings`).

## Justificación

Como la similitud inicial no depende del umbral, reconstruir la primera
decisión es exacto, barato y reproducible: el mismo corpus da la misma tabla
cada vez. Dejar el módulo en solo lectura hace cumplir la regla del proyecto en
el código y no solo en la documentación: la pantalla muestra las consecuencias
de cada umbral, pero el umbral se cambia a mano, en `.env`, con una decisión que
queda registrada en las trazas nuevas. Si ningún umbral separa los casos, la
respuesta lo dice con el mismo peso que cualquier otro dato.

## Alternativas consideradas

- **Volver a correr el grafo completo con cada umbral:** daría el resultado de
  punta a punta (debates, consensos, arbitrajes), pero cuesta una corrida de
  LLM por umbral y por requisito, y la variación de los LLM se mezclaría con el
  efecto del umbral. Si se necesita, es un experimento explícito del módulo de
  evaluación, no de esta pantalla.
- **Elegir el umbral automáticamente (máximo F1):** con 15–25 requisitos sería
  ajustar el umbral al mismo corpus con el que se evalúa, que es justo lo que la
  regla prohíbe. La respuesta muestra el F1 por umbral pero no recomienda ni
  elige ninguno.
- **Cambiar el umbral desde la interfaz:** rompe la trazabilidad (la
  configuración vive en `.env` y cada traza guarda la suya) e invita a mover el
  umbral hasta que los casos salgan bien.
- **Usar también las similitudes de las rondas de debate:** solo existen para
  los términos que el umbral real mandó a debate y miden interpretaciones ya
  refinadas; mezclarlas sesgaría la distribución hacia ese umbral.
- **Curva ROC y AUC:** con tan pocos casos la curva es ruidosa y difícil de
  leer; la matriz de confusión por umbral dice lo mismo caso por caso y se puede
  derivar de `por_umbral` si se quiere la curva.

## Consecuencias

- **Solo cubre la primera decisión** (`aceptado_directo` frente a `en_debate`).
  No predice cómo habría terminado un debate con otro umbral (el consenso de las
  rondas también usa el umbral), ni qué habría validado el humano.
- **Lo que nunca llegó al umbral es invisible aquí:** términos que el
  Clasificador declaró unívocos, los que filtraron el LEL o los catálogos de
  vaguedad y regionales, y los requisitos que fallaron antes de la divergencia.
  Con etiquetas aparecen en `etiquetas_sin_similitud`: ningún umbral puede
  corregirlos, son errores de otras etapas y los mide el módulo de evaluación.
- **El emparejamiento es literal tras normalizar** (minúsculas sin acentos):
  si el Extractor tomó *la sesión* y la etiqueta dice *sesión*, no se emparejan.
  Se informa en las dos listas de no emparejados en lugar de adivinar.
- **Cuenta términos, no requisitos.** La máquina de estados decide por el peor
  término de cada requisito (ADR 0002); la rejilla muestra cada término por
  separado para que se vea cuál empuja la decisión.
- **Mezclas que solo se advierten:** si un proyecto tiene similitudes de dos
  modelos de embeddings o decididas con umbrales distintos, se incluyen todas y
  se avisa; no son comparables entre sí y no se filtran.
- **Resultados exploratorios.** Con 15–25 casos, un solo caso mueve la
  precisión varios puntos. Calibrar y evaluar con el mismo corpus es una
  limitación que la tesis debe declarar; el umbral que se elija se justifica con
  la distribución y la separación, no solo con el F1.
- **Contrato con el módulo de evaluación:** se usa el documento más reciente
  con `etiquetas` de cada proyecto (los ids se ordenan de forma natural); se
  supone que el documento trae su id en `evaluacion_id` (si no, sale `null`).
  Las etiquetas que no cumplen el contrato se cuentan en `n_invalidas` y se
  dejan fuera.
- **F1 sin debates.** Con un umbral que no manda nada a debate y ambiguos
  etiquetados, la precisión no está definida y el F1 sale `null` (igual que en la
  evaluación). Otras herramientas (p. ej. scikit-learn) informan 0 en ese caso;
  quien compare cifras debe saberlo. La exhaustividad sí sale 0 y lo deja ver.
- **Reprocesos.** Si un requisito etiquetado por la evaluación se reprocesa, su
  etiqueta apunta a la traza sustituida: queda en `etiquetas_sin_similitud` y la
  traza nueva en `valores_sin_etiqueta` (la evaluación no sigue reprocesos, ADR
  0014). Si una misma traza se reprocesa dos veces por separado (dos ramas, no
  una cadena), cuentan las dos versiones nuevas.
