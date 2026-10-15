# 0024. Versión 2: de la entrevista a los requisitos, con el LEL interactivo como centro

- **Fecha:** 2026-10-13
- **Estado:** Aceptada (cambia la entrada y la salida del sistema; la versión 1 se conserva)

## Contexto

En la versión 1 se pegaban o subían **requisitos ya escritos**; los agentes los separaban,
buscaban la ambigüedad de cada uno, debatían cuando las interpretaciones divergían y los
reescribían. El producto final, sin embargo, debe ser **los requisitos mismos**: lo que llega
de verdad del cliente es una entrevista, y ahí es donde aparece la ambigüedad que importa
(«el doctor quiere registrar las consultas»: ¿la cita médica o una consulta a la base de
datos?) y los regionalismos del habla de trabajo («checar», «dar de alta»). Separar la
entrevista en requisitos antes de entender su vocabulario repetía el problema.

KMoS-RE y KMoS-SSA ya proponen ese orden: elicitar con entrevistas, construir el Léxico
Extendido del Lenguaje (LEL) del dominio, un modelo conceptual, validarlo con los
especialistas y de ahí obtener los requisitos.

## Decisión

### 1. El flujo por fases

Un proyecto pasa por cinco fases; cada una se abre cuando la anterior quedó **validada por
una persona experta**:

```
entrevista → LEL interactivo → mapa conceptual con propósito → metas → requisitos
```

La compuerta se calcula con **huellas en cadena** (`app/fases/documento.py`): el mapa guarda
la huella del LEL validado y de los acuerdos con que se generó; las metas, la del LEL y el
mapa; los requisitos, la de los tres. Si algo de atrás cambia, lo de adelante deja de estar
«al día»: se vuelve a generar o se conserva tal cual (`/conservar`).

### 2. Entrada: la entrevista (`app/entrevistas/`)

Texto pegado, PDF con texto o .txt (la extracción y la limpieza de ADR 0009). Se lee en
**turnos** (`T1`, `T2`…): por hablante si el texto dice «Nombre: …» (al menos dos etiquetas
que se repiten; la hora delante y los títulos «Dra.» se aceptan) o, si no, un turno por
párrafo. Quien más pregunta es probablemente quien entrevista. La vista previa no guarda
nada; al confirmar, la entrevista entra a la cola (ADR 0008). Un proyecto puede tener
varias entrevistas.

### 3. Fase del LEL: un grafo nuevo sobre la entrevista completa (`orchestration/grafo_entrevista.py`)

Ya no se separa en requisitos. Los mismos agentes, el mismo mecanismo de divergencia y el
mismo debate, con prompts para la entrevista:

```
cargada → leida → extraida → interpretada ──────────────→ modelada → lista
                                 └→ en_debate ⟲ → arbitrada ─┘
```

- **Revisor** (`revisor_entrevista_v1`): la ficha de la entrevista — participantes, objetivo,
  problemas, necesidades y reglas, cada punto con sus turnos (las metas y los requisitos la
  usan como evidencia).
- **Extractor** (`extractor_entrevista_v1`): los términos del dominio por partes. El código
  los ubica en **todos** los turnos donde aparecen (spaCy y una clave en singular), descarta
  los que no están, suma los regionales del catálogo y marca los vagos.
- **Filtros contra la memoria**: un término que ya está en el LEL del proyecto o tiene un
  acuerdo no se vuelve a interpretar (`resuelto_por_lel`, como en la versión 1); uno que la
  persona descartó ya no se propone.
- **Clasificador** (`clasificador_intencion_v1`): la **intención** de cada término — a qué se
  refiere (`significado`), qué quiere lograr quien lo usa (`intencion`) y una cita reescrita
  para esa interpretación (`parafrasis`). Una sola intención: unívoco. Varias: intenciones
  candidatas. Es una interpretación (ADR 0001) con un campo más.
- **Divergencia** (sin cambios, ADR 0002): similitud coseno mínima entre las paráfrasis;
  bajo el umbral, debate.
- **Crítico** (`critico_entrevista_v1`, `critico_arbitraje_entrevista_v1`) y **Clasificador**
  (`clasificador_refinamiento_entrevista_v1`): el debate acotado de la versión 1, con las
  citas de la entrevista en lugar del requisito (R1 y R2 en código, R3 el LLM).
- **Modelador** (`modelador_lexico_v1`): cada término como entrada del LEL — símbolo
  canónico, tipo, noción, impacto, intención y sinónimos — con sus citas y, si fue ambiguo,
  las intenciones consideradas y cómo se resolvió.

Los mensajes van a la **bitácora** de la entrevista con el mismo sobre y los mismos tipos de
la traza de un requisito (más `ficha`): la escena en vivo los anima con la misma coreografía
de esferas. Recuperación tras un reinicio, cancelar y volver a procesar, como en ADR 0008.

### 4. El LEL interactivo y la memoria del proyecto (`app/fases/lexico.py`, `memoria.py`)

Cada entrada queda `propuesta`. La persona experta: **valida**, **corrige** (o parte de otra
intención de las que vieron los agentes), **descarta** (no es del dominio), **restaura** o
**agrega** un término. Todo queda en el historial de la entrada.

**El sistema aprende** de lo que corrige, de lo que confirma entre varias intenciones y de
lo que descarta: lo guarda como un **acuerdo del proyecto** (colección `memoria`):

> «consulta» significa *registrar la atención médica de cada paciente*;
> **no** significa *búsqueda en la base de datos*.

Los acuerdos valen solo en su proyecto (la memoria no se mezcla entre dominios, ADR 0008).
Se usan para resolver el término en las entrevistas siguientes sin volver a interpretarlo, y
van en los prompts del Clasificador y del Modelador en todas las fases. Se pueden olvidar.
El LEL validado con sus acuerdos es el **sistema cognitivo** del dominio: con él se abre el
mapa.

### 5. Mapa conceptual con propósito (`app/fases/mapa.py`)

Reemplaza al mapa de la versión 1 (ADR 0020), que se armaba desde requisitos. El Modelador
(`modelador_mapa_proposito_v1`) propone la **pregunta de enfoque** (Novak), los conceptos
—cada uno ligado al símbolo del LEL que representa; los verbos del LEL son enlaces, no
conceptos— y las proposiciones. El código verifica las referencias (un reintento), liga los
símbolos, quita repetidas, lazos y conceptos sueltos. La persona lo edita **sobre el propio
mapa** (React Flow, `components/fases/EditorMapa.jsx`): mover, renombrar, unir arrastrando,
quitar, agregar desde el LEL, cambiar el concepto central, deshacer y validar cada componente.
Se guarda solo; cada cambio queda en el historial en palabras («renombró «Consulta» como
«Consulta médica»»). Se exporta como Mermaid, PNG o SVG.

### 6. Metas en tres niveles (`app/fases/metas.py`)

El Modelador (`modelador_metas_v1`) propone **metas de la organización** (MO), **estratégicas**
(ME, contribuyen a una MO) y **específicas** (MS, contribuyen a una ME, con indicador), con
los símbolos del LEL que usan y las citas de la entrevista que las respaldan. El código
verifica la jerarquía (un reintento), renumera, liga símbolos y deja solo citas que existen.

### 7. Requisitos (`app/fases/requisitos.py`)

El Modelador (`modelador_requisitos_v1`) escribe los requisitos **por meta estratégica**, con
la entrevista, el LEL, el contexto, el mapa, las metas y los acuerdos, y los que ya escribió
para no repetir. Cada requisito: texto, funcional o no funcional (ISO/IEC 25010 + legal),
prioridad, metas específicas que realiza, símbolos del LEL, citas, criterios de aceptación
y supuestos. El código numera RF/RNF y avisa lo que una persona debe mirar: expresiones
vagas (lista propia + catálogo de vaguedad), sin términos del LEL, sin citas, sin criterios,
y metas específicas que ningún requisito realiza. `GET /proyectos/{id}/fases/requisitos/markdown`
arma la **especificación completa** con su matriz de trazabilidad (requisito → metas →
términos → entrevista).

### 8. Generar en la cola, con el avance en vivo (`app/fases/progreso.py`)

Mapa, metas y requisitos se generan en el trabajador único de la cola (prioridad `fase`) y la
respuesta cuenta cada paso en NDJSON. Si se pide otra vez la misma fase mientras se genera,
la petición se suma a la que corre y recibe su avance desde el principio (React monta dos
veces en desarrollo; la persona puede volver a la pantalla).

### 9. Las esferas

- Cada fase es una sección con su tono (entrevista rosa durazno, léxico cian, mapa turquesa,
  metas oro, requisitos verde); el camino del proyecto las dibuja como esferas pequeñas que
  se llenan al validarse.
- La esfera **recibe** la entrevista (se suelta el PDF sobre ella) y la **procesa en escena**
  con cuatro esferas como máximo (ADR 0025): el sistema; el agente que tiene el turno, que
  viaja por las estaciones Entrevista, Intención, Discusión y Léxico con el tono y el nombre
  de quien habla; y las dos intenciones más distintas de un término ambiguo, que se acercan o
  alejan según su similitud.
- En la validación, lo que la persona valida o corrige **viaja como una esfera pequeña** de la
  tarjeta a la esfera grande; si el sistema aprendió algo, la esfera toma el tono «aprende» y
  dice qué aprendió.
- Generar el mapa, las metas o los requisitos sube la esfera al centro con el tono de la fase.

### 10. La versión 1 se conserva

El grafo por requisito, la divergencia calibrada, la evaluación contra el corpus y sus
pantallas siguen igual: `/proyectos/:id/v1` y «Más». Sirven para la evaluación del capítulo 4
y para analizar requisitos sueltos ya escritos. Las rutas de la API de la versión 1 no cambian.

## Justificación

- **La intención es lo que se malinterpreta.** Un término no es ambiguo en abstracto: lo es
  para quien no estuvo en la entrevista. Pedir al Clasificador qué quiere lograr quien habla
  (no solo qué significa la palabra) y debatir cuando las intenciones divergen ataca la
  ambigüedad y los regionalismos en el punto donde nacen, antes de escribir un requisito.
- **La aportación de la tesis se conserva.** La divergencia entre interpretaciones de un mismo
  enunciado sigue siendo la señal que activa el debate; cambia el enunciado (la cita de la
  entrevista en lugar del requisito) y el lugar del flujo (el LEL, antes que los requisitos).
- **KMoS-SSA pide el punto de revisión humana** (fase 4): ahora hay uno por fase y es el que
  abre la siguiente. Las metas y los requisitos se apoyan en lo que la persona ya validó, no
  en propuestas sin revisar.
- **Aprender solo dentro del proyecto.** «Consulta» significa algo en un consultorio y otra
  cosa en un sistema de inventario; un acuerdo global contaminaría otros dominios.
- **Editar el mapa sobre el mapa.** Corregir un JSON exige conocer su forma; mover, unir y
  renombrar sobre el dibujo es lo que hace un experto del dominio que no es informático.
- **Trazabilidad (el NFR central).** Cada requisito se rastrea a sus metas, sus términos del
  LEL y los turnos de la entrevista; cada término, a sus citas y a cómo se resolvió; cada
  cambio de la persona queda en un historial.

## Alternativas consideradas

- **Separar la entrevista en requisitos y seguir con el flujo de la versión 1.** Era lo más
  barato, pero obliga a escribir requisitos antes de entender el vocabulario, que es justo
  donde se cuela la ambigüedad.
- **Un agente nuevo por fase (Estratega, Redactor).** Más nombres sin una diferencia de
  método; el Modelador ya formaliza lo validado en todas las fases (KMoS-SSA, fase 5).
- **Memoria global de la cuenta.** Descartada por la contaminación entre dominios.
- **Generar metas y requisitos en una sola llamada.** Con modelos locales la salida se
  trunca; por meta estratégica cada llamada es acotada y el avance se ve.
- **Un editor de mapas propio en SVG.** React Flow (MIT) ya resuelve arrastrar, unir, acercar
  y seleccionar con teclado; se conserva su atribución.

## Consecuencias

- Colecciones nuevas: `entrevistas`, `bitacoras`, `lexico`, `memoria`, `fase_mapa`,
  `fase_metas`, `fase_requisitos`. Borrar un proyecto las borra también.
- Variables nuevas (`.env`): `ENTREVISTA_MAX_CARACTERES`, `ENTREVISTA_TANDA_CARACTERES`,
  `REVISOR_TANDA_CARACTERES`, `LEL_MAX_TERMINOS`, `LEL_TANDA_TERMINOS`,
  `LEL_CITAS_POR_TERMINO`, `MAPA_MAX_CONCEPTOS`, `MAPA_MAX_RELACIONES`.
- Una entrevista larga hace muchas llamadas: una por parte para el Revisor y el Extractor, una
  por cada 8 términos para el Clasificador y el Modelador, y el debate de los términos que
  divergen. Con Ollama local tarda; la escena lo muestra paso a paso.
- Nueva dependencia del frontend: `@xyflow/react` (React Flow 12).
- La versión del sistema es la **2.0.0** (frontend y API).
