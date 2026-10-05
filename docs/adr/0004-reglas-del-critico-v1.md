# 0004. Reglas del Crítico, versión verificable v1 (provisional)

- **Fecha:** 2026-10-05
- **Estado:** Provisional — se revisa con la asesora antes del Capítulo 4

## Contexto

El Crítico evalúa cada interpretación contra tres reglas y emite objeciones; no
genera interpretaciones propias. La fase pide que lo verificable se verifique
**en código** y no por LLM:

- **R1 Consistencia de vocabulario:** la interpretación no introduce términos de
  contenido ausentes del requisito y del LEL acumulado (lematización spaCy).
- **R2 Sin entidades nuevas:** no introduce sustantivos ni entidades nombradas
  ausentes del requisito (spaCy).
- **R3 Reduce ambigüedad:** la paráfrasis asigna un único referente al término.
  La juzga el LLM con salida estructurada y evidencia textual.

Leídas al pie de la letra, R1 y R2 se contradicen con el propio trabajo del
Clasificador: para desambiguar *sesión* hay que decir *periodo de uso* o *evento
de conexión*, palabras que no están en el requisito. Con la versión literal,
casi toda interpretación útil viola R1.

## Decisión

1. **Dos versiones de R1 y R2, una decide y otra se registra.**
   - **Relajada (decide):** vocabulario permitido = requisito + LEL +
     `significado` de la propia interpretación.
   - **Estricta (solo traza):** vocabulario permitido = requisito + LEL. Se guarda
     como `r1_estricta` / `r2_estricta` en cada `EvaluacionInterpretacion` y no
     afecta objeciones ni ruteo. Ambas quedan disponibles para el Capítulo 4.
2. **El `significado` está acotado** a `SIGNIFICADO_MAX_PALABRAS` (12 por
   defecto, en `.env`). Lo valida el contrato `Interpretacion`; si el LLM lo
   excede, se reintenta una vez con el error y, si persiste, el caso va a `error`.
   Así el `significado` no se vuelve una puerta para colar vocabulario.
3. **La evidencia separa el origen de cada token** (en `ResultadoRegla.detalle`):
   - `nuevos_en_parafrasis`: fuera de requisito + LEL;
   - `de_ellos_cubiertos_por_significado`: de esos, los que aporta el significado;
   - `de_ellos_no_justificados`: el resto — son los que hacen fallar la relajada;
   - `nuevos_en_significado`: lo que el propio significado agrega a requisito + LEL.
   La relajada cumple si `de_ellos_no_justificados` está vacío; la estricta, si
   `nuevos_en_parafrasis` y `nuevos_en_significado` están vacíos.
4. **Qué se revisa y qué permite.** Se filtra por categoría solo el lado
   revisado (paráfrasis y significado): R1 toma sustantivos, nombres propios,
   verbos, adjetivos y adverbios que no sean *stopwords*; R2 toma sustantivos,
   nombres propios y entidades nombradas. El lado que permite (requisito, cada
   pieza del LEL, significado) se toma completo, sin filtrar categoría.
5. **Comparación por lema o por forma.** Un token cuenta como conocido si su lema
   **o** su forma superficial (ambos en minúsculas y sin acentos) aparecen en el
   vocabulario permitido. Cada pieza del LEL (símbolo, cada noción, cada impacto)
   se analiza por separado.
6. **R3 por LLM** (`critico_v1`): por interpretación devuelve `cumple`,
   `evidencia` (cita de la paráfrasis) y `objecion`. El código registra en
   `detalle.evidencia_es_cita_de_la_parafrasis` si la evidencia aparece de verdad
   en la paráfrasis; no cambia la decisión, solo deja el dato.
7. **Objeciones:** una por regla que falle en su versión relajada (R1, R2) y una
   por R3 si `cumple` es falso, con la objeción del LLM o, si falta, su evidencia.

## Justificación

- La versión relajada conserva la intención de R1/R2 (no inventar contenido) sin
  castigar el acto mismo de desambiguar; la estricta conserva el dato literal.
- **Hallazgo al implementar (punto 5):** el lema de `es_core_news_sm` depende del
  contexto. *Bitácora* sola se etiqueta ADJ con lema *bitácoro*; dentro de
  «bitácora registro de eventos se consulta» sale VERB *bitácorar*; dentro de
  una oración completa es NOUN *bitácora*. Comparar solo por lema hacía que una
  entrada del LEL no ampliara el vocabulario. Por eso se compara por lema o forma
  y no se concatenan las piezas del LEL. El caso está fijado en
  `tests/agents/critico/test_reglas.py`.

## Alternativas consideradas

- **Solo la versión estricta:** casi toda interpretación útil fallaría R1; el
  debate se volvería ruido y el arbitraje, la norma.
- **Solo la relajada:** se pierde el dato literal que pide la tesis.
- **Juzgar R1/R2 con el LLM:** no reproducible; contradice la consigna.
- **Usar `vectors`/similitud semántica para R1:** el modelo `sm` no trae vectores
  y convertiría una regla verificable en otra calibrable.

## Consecuencias

- Las reglas son tan buenas como el etiquetado de `es_core_news_sm`; un modelo
  `md`/`lg` cambiaría resultados. El modelo usado queda en la traza (`spacy_model`).
- Comparar por forma superficial puede aceptar homógrafos de distinta categoría
  (*consulta* sustantivo frente a *se consulta* verbo). Se acepta en v1.
- El tope de 12 palabras es un parámetro calibrable y se registra en la traza.
