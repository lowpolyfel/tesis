# 0028. Controles negativos en el banco y revisión a ciegas con orden barajado

- **Fecha:** 2026-10-18
- **Estado:** Aceptada (completa ADR 0027)

## Contexto

El banco v1 del ADR 0027 trae 50 términos, todos ambiguos. Por eso la «detección» que mide la
prueba es solo la **exhaustividad**: sin términos inequívocos no hay precisión ni tasa de
falsas alarmas. Un modelo que contestara «ambiguo» a todo saldría con detección 1.00 y se vería
perfecto, así que la medida no distingue un buen detector de uno alarmista. Es el mismo hueco
que tiene la calibración del umbral sin ground truth negativo (ADR 0026), en otra forma.

Además, la aprobación de la persona revisora se registraba viendo el nombre de los modelos y en
el mismo orden siempre. Es la medida más blanda de las dos: un ✓ dado sabiendo qué modelo es pesa
menos.

## Decisión

### 1. Banco v2 con 23 controles inequívocos (`banco/ambiguedad_v2.json`)

El banco v2 trae los 50 términos de v1 sin cambios y con los mismos ids (B01–B50), más 23
controles B51–B73 de clase **inequívoco**. Cada control trae una sola lectura esperada y
`ambiguo: false`.

La regla para elegir los controles: un control negativo malo es una palabra obviamente inequívoca
(«estetoscopio»), con la que cualquier modelo acierta y la precisión sale inflada sin medir
nada. Un control bueno es vocabulario de dominio que el Extractor sí levantaría, que se ve
sospechoso y que en su dominio solo tiene una lectura. Así se prueba si el modelo sabe
contenerse, no si reconoce palabras raras.

- **10 inequívocos de dominio**, el piso: «contraseña», «código de barras», «radiografía»,
  «kilometraje», «temperatura», «número de serie», «fecha de caducidad», «correo electrónico»,
  «huella digital», «signos vitales».
- **13 sustantivos genéricos de negocio**, los que de verdad miden algo: en el español general
  pueden ser polisémicos, pero en su dominio aterrizan en un solo sentido. Son «paciente»,
  «cita», «caja registradora», «alumno», «recibo», «contrato», «salario», «vacante»,
  «sucursal», «CURP», «proveedor», «domicilio» y «teléfono».

Para no meter pistas de superficie:

- Los sustantivos genéricos se parecen a los positivos.
- Cada control usa el mismo contexto de proyecto que el ambiguo de su dominio.
- Las citas van en el mismo registro coloquial de entrevista.

Veinte controles tienen **pareja**: un ambiguo del mismo dominio (por ejemplo «caja» /
«caja registradora», «consulta» / «paciente»). Si el modelo marca el primero y no el segundo,
responde al contexto y no a la forma de la palabra.

Con 23 controles, el intervalo de Wilson de la tasa de falsas alarmas sigue siendo de unos
±20 puntos. No se baja de 20.

### 2. Los bancos no se editan: se versionan

`ambiguedad_v1.json` queda intacto. Si se editara, cambiaría su huella y las pruebas corridas con
él (la P01 de la tesis) dejarían de corresponder a su banco.

- Cada prueba guarda la versión y la huella de su banco, y se mide siempre con ese banco.
- Una prueba nueva usa el más nuevo, o el que se elija (`banco` en `POST /pruebas-modelos`).
- `GET /bancos/ambiguedad?version=` devuelve cualquiera, con la lista de `versiones`.

### 3. Medidas con controles

Positivo es que el modelo marque el término como ambiguo; la verdad es la del banco.

- **Exhaustividad** (antes «detección», misma llave `deteccion`): ambiguos marcados sobre todos
  los ambiguos. Un error cuenta como no detectado, como en ADR 0027.
- **Tasa de falsas alarmas**: inequívocos marcados como ambiguos sobre los inequívocos que
  respondieron. Un error no es ni alarma ni contención: se deja fuera y se reporta aparte
  («errores en inequívocos»), para no premiar a un modelo que falla.
- **Precisión**: ambiguos sobre todo lo marcado como ambiguo.
- **Matriz de confusión** (VP, FN, FP, VN) y **parejas**: en cuántas parejas del mismo dominio
  marcó el ambiguo y no su control.

Todas llevan intervalo de Wilson al 95 %. Por clase, la columna es «marcó ambiguo»: en las
clases ambiguas es la exhaustividad y en la inequívoca son las falsas alarmas. La pantalla y el
paquete advierten que con 20 a 30 casos por clase los intervalos se traslapan: una diferencia
entre clases es una tendencia por confirmar, no un resultado.

Una prueba del banco v1 sigue mostrándose igual, con el aviso de que no tiene controles.

### 4. Revisión a ciegas de verdad

- «Ocultar nombres de los modelos» asigna las letras A, B, C… en un **orden barajado** fijo por
  prueba, para que la letra no delate qué modelo se agregó primero. Los avisos tampoco nombran
  modelos.
- En la revisión, el **orden de los términos se baraja** por prueba y modelo.
- **Rehacer la revisión** (`DELETE /pruebas-modelos/{id}/revision`) borra todas las marcas y
  conserva las respuestas. Así una revisión hecha viendo los nombres se puede repetir a ciegas y
  la aprobación se endurece.

### 5. Gráfica y Overleaf

- La gráfica suma las falsas alarmas: azul, el color de «no ambiguo», con marca de rombo.
- El paquete suma `tablas/confusion.tex` y las columnas de falsas alarmas y precisión, solo
  cuando el banco tiene controles. `datos/respuestas.csv` lleva además la verdad del banco
  (`ambiguo_esperado`).

## Justificación

- Sin negativos, una medida de detección no separa al detector del alarmista. Con negativos, la
  misma prueba entrega las dos mitades de la matriz de confusión.
- Elegir los controles por la regla de arriba evita la precisión inflada de los negativos
  triviales.
- Versionar el banco conserva la trazabilidad de las pruebas ya citadas.

## Alternativas consideradas

- **Agregar los controles al banco v1:** se descarta porque rompe la correspondencia de P01 con
  su banco.
- **Contar un error en un inequívoco como acierto (no marcó ambiguo):** se descarta porque
  premiaría al modelo que falla.
- **Contarlo como falsa alarma:** se descarta porque castiga algo que el modelo no dijo. Se deja
  fuera y se reporta.

## Consecuencias

- Para citar precisión y falsas alarmas hay que correr una prueba nueva con el banco v2. La P01
  (v1) sigue siendo citable solo por su exhaustividad.
- Esta prueba no sustituye el ground truth de las entrevistas (ADR 0026). La prueba mide al
  Clasificador contra un banco curado; la calibración mide el umbral contra lo que de verdad
  aparece en una entrevista.
- La versión del sistema pasa a **2.3.1**: corrige la medida de la 2.3.0 sin agregar otra
  pantalla.
