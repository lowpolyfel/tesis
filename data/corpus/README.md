# corpus

Requisitos de prueba en español de México con su ground truth, para la
evaluación empírica (CONTEXTO §9 y §11, ADR 0014). Cada corpus es un directorio:

```
data/corpus/<nombre>/          # CORPUS_DIR; el nombre solo lleva letras, dígitos, - y _
├── requisitos.jsonl           # lo único que llega al sistema y a la línea base
├── ground_truth.jsonl         # separado: nunca entra a un prompt
└── corpus.json                # opcional: descripción y procedencia
```

> **`ejemplo/` es un EJEMPLO del formato, no el corpus de la tesis.** Siete
> requisitos escritos por el asistente de código para mostrar cada tipo de caso.
> Nadie validó su ground truth y sus resultados no se reportan. El corpus real
> (15 a 25 requisitos, con casos sin ambigüedad) lo construye la tesista y, de
> preferencia, lo revisa otra persona.

## `requisitos.jsonl`

Una línea JSON por requisito:

```json
{"id": "EJ02", "texto": "El sistema debe registrar la sesión del usuario."}
```

- `id`: letras, dígitos, `.`, `-` o `_` (hasta 40). Único en el archivo.
- `texto`: hasta 2000 caracteres.

## `ground_truth.jsonl`

Una línea por requisito, con el **mismo `id`**:

```json
{"id": "EJ03", "ambiguo": true,
 "terminos": [{"termino": "jalar", "tipo_ambiguedad": "lexica",
               "interpretaciones_validas": ["consultar los datos", "descargar los datos", "procesar los datos"],
               "interpretacion_esperada": null}],
 "vaguedad": ["ahorita"], "regionales": ["jalar"], "notas": "..."}
```

| Campo | Qué es |
|---|---|
| `ambiguo` | `true` si y solo si hay al menos un término ambiguo. La vaguedad no es ambigüedad: un requisito solo vago lleva `false`. |
| `terminos` | Términos ambiguos. `tipo_ambiguedad`: `lexica`, `alcance`, `anaforica` o `sintactica`. Al menos dos `interpretaciones_validas`. `interpretacion_esperada` es una de ellas, o `null` si no se fija. |
| `vaguedad` | Expresiones vagas (sin dos interpretaciones discretas): *ahorita*, *rápido*. |
| `regionales` | Expresiones regionales presentes. Si además son ambiguas, van también en `terminos`. |
| `notas` | Texto libre. |

**Escribe cada término tal como aparece en el texto** (*jale* si el texto dice
*jale*): el emparejamiento con lo que detecta el sistema es por palabras
normalizadas, por contención palabra por palabra o por lema (ADR 0014), y el
lematizador falla con las formas regionales.

## `corpus.json` (opcional)

```json
{"descripcion": "...", "ejemplo": false, "autoria": "quién construyó el ground truth", "validado_por": "quién lo revisó"}
```

## Validación

El cargador (`app/evaluacion/corpus.py`) reporta todos los errores juntos, con
archivo, línea e id: JSON inválido, campos que faltan o sobran, ids repetidos,
ids que no coinciden entre los dos archivos, `ambiguo` incoherente con
`terminos`, menos de dos interpretaciones válidas distintas, una esperada que no
está entre las válidas, términos repetidos y un término que está a la vez en
`terminos` y en `vaguedad` (la vaguedad no es ambigüedad). Un corpus inválido
aparece en `GET /corpus` con sus errores y no se puede evaluar. Los archivos van
en UTF-8, con o sin BOM.

También avisa, sin rechazar, si un término listado no aparece tal cual en el
texto o si no hay requisitos sin ambigüedad.

## Evaluar

`POST /evaluaciones {"corpus": "<nombre>"}` crea un proyecto de evaluación, corre
cada requisito por el sistema (hasta `pendiente_validacion`, sin validación
humana) y por la línea base de un solo agente (`agente_unico_v1`), y
`GET /evaluaciones/{id}` compara ambos contra una copia del ground truth guardada
al crear la evaluación. Qué se cuenta y cómo: ADR 0014.
