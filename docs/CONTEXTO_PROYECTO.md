# Contexto del proyecto y alcance del desarrollo

> Documento de contexto para pasarle a un agente de código o a un chat nuevo.
> Última actualización: 5 de octubre de 2026.

---

## 1. Identificación

| | |
|---|---|
| **Autor** | Felipe Martínez Castorena — matrícula 203637 |
| **Institución** | Universidad Autónoma de Ciudad Juárez (UACJ) |
| **Adscripción** | Instituto de Ingeniería y Tecnología, Departamento de Ingeniería Eléctrica y Computación |
| **Asesora** | Dra. Karla Olmos Sánchez |
| **Título** | Detección de ambigüedad en requisitos de software mediante un sistema multiagente basado en LLMs y el marco KMoS-SSA |
| **Tipo** | Tesis de licenciatura. El entregable es un **prototipo**, no un producto. |
| **Plazo** | Un semestre de desarrollo. |

---

## 2. El problema

Un requisito de software puede leerse de formas distintas aunque esté bien
redactado. El problema no es la mala redacción: es que el lenguaje natural
permite esa doble lectura. Cuando eso pasa sin que nadie lo note, el producto
terminado refleja una interpretación que quizá nunca fue la correcta.

Ejemplo: *"el sistema debe registrar la sesión del usuario"*. La frase es
gramatical y completa. Pero **sesión** puede ser el periodo de uso continuo o
el evento de conexión. El analista escribe pensando una cosa; el desarrollador
lee la otra. Nadie se entera hasta que el sistema está construido.

El caso se agrava con el español de trabajo en México. Un requisito puede pedir
que el sistema *jale* los datos, que *dé de alta* al usuario, que *cheque* que
el campo no esté vacío. Para quien estuvo en la reunión eran claras. Para quien
lee después, no.

**Enunciado del problema:** los sistemas actuales de procesamiento de requisitos
no tienen un mecanismo que detecte cuándo una frase admite más de una
interpretación válida y que compare esas interpretaciones entre sí antes de
aceptar una como definitiva.

---

## 3. El vacío que se ataca

De la revisión sistemática (PRISMA 2020, 33 estudios incluidos):

- Los sistemas que detectan ambigüedad (Alotaibi, ClarifyGPT) procesan el
  requisito de forma aislada o comparan salidas sucesivas de un mismo modelo.
  Ningún agente especializado confronta interpretaciones alternativas.
- Los sistemas multiagente de IR que sí existen —**MARE, iReDev, Elicitron,
  ArgRE**— reparten trabajo entre agentes con roles, pero para otras tareas:
  generar especificaciones, simular usuarios, negociar conflictos entre
  requisitos *que ya se entienden con claridad*.
- Ninguno usa la **divergencia semántica entre interpretaciones de un mismo
  enunciado** como señal para activar discusión entre agentes.

**ArgRE es el antecedente más cercano** y comparte técnica (comparación
semántica, rondas acotadas, registro del proceso), pero su objeto es distinto:
negocia *cuánto peso* tiene un requisito frente a otro, no *qué significa* un
enunciado.

---

## 4. Qué se va a construir

Un prototipo web de cuatro agentes LLM orquestados que, ante un requisito en
español, detectan si admite más de una lectura, confrontan esas lecturas entre
sí, y formalizan la resolución como conocimiento reutilizable.

### 4.1 Los cuatro agentes

| Agente | Qué hace | Qué NO hace |
|---|---|---|
| **Extractor** | Recibe el requisito crudo y separa el vocabulario relevante del dominio | No interpreta todavía |
| **Clasificador** | Construye la primera estructura. Cuando un término admite varias lecturas, las genera como interpretaciones candidatas | No decide cuál es la correcta |
| **Crítico** | Cuando las interpretaciones divergen, conduce un debate acotado y las evalúa contra criterios explícitos. Arbitra si se agotan las rondas | No genera interpretaciones propias |
| **Modelador** | Toma la interpretación validada y la formaliza como entrada del LEL y como artefactos | No valida: eso lo hace un humano |

### 4.2 El mecanismo de divergencia

Es el núcleo de la aportación y **va separado de los agentes**:

```
interpretaciones -> embeddings -> similitud coseno
                                       |
                 >= umbral  ->  se acepta directo, sin debate
                 <  umbral  ->  debate acotado (máx. 2 rondas)
                                       |
                              consenso  |  arbitraje del Crítico
```

- **Umbral inicial: 0.75.** Es provisional y se calibra experimentalmente.
  Nunca presentarlo como decisión tomada.
- **Máximo 2 rondas** por caso.
- Sustento teórico: Chantree et al. distinguen ambigüedad **nociva** (lectores
  distintos entienden distinto) de **inocua**. El sistema no resuelve toda
  ambigüedad, solo la que diverge. Eso es lo que lo separa de ArgRE.

### 4.3 Criterios del Crítico

Tres, y **deben reescribirse como reglas verificables antes de programar**:

1. Consistencia con el vocabulario ya establecido
2. No introduce entidades nuevas
3. Reduce la ambigüedad

Ejemplo de reescritura: *"consistencia con el vocabulario"* no se puede
evaluar; *"la interpretación no introduce términos que no aparezcan en el LEL
acumulado"* sí.

---

## 5. Marco metodológico: KMoS-SSA

Framework desarrollado en la propia UACJ por Rodas-Osollo y Olmos-Sánchez,
evolución de KMoS-RE. Diseñado para dominios de estructura informal, donde el
conocimiento es tácito y está repartido entre varios especialistas.

**Se aplica en dos niveles:**

- **Nivel producto** — organiza los roles de los agentes
- **Nivel proceso** — guía el desarrollo del propio proyecto

### Correspondencia de fases

| Fase KMoS-SSA | Rol en el marco original | Componente del sistema |
|---|---|---|
| 1. Enriquecimiento de conocimiento | Analista Cognitivo, Proveedores de Solución | Agente Extractor |
| 2. Generación de modelo | Proveedores de Solución | Agente Clasificador |
| 3. Discusión de modelo | Arquitecto Cognitivo | Agente Crítico |
| 4. Validación de modelo | Especialistas del Dominio, Tomador de Decisión | Interfaz web (humano) |
| 5. Enriquecimiento (cierre) | Analista Cognitivo | Agente Modelador |

**Por qué este marco y no otro:** no por comparación entre métodos, sino por
elección. La **fase 3, discusión de modelo**, está en el cruce entre el espacio
de pensamiento sistémico y el del mundo real, y el marco la describe como el
momento en que el choque con los especialistas hace aparecer las distintas
visiones sobre lo mismo. Esa descripción coincide con el mecanismo que se
quería implementar. El marco no se ajustó a la idea: la idea ya tenía lugar
dentro de él.

---

## 6. Taxonomía de ambigüedad: qué entra y qué no

| Tipo | Tratamiento |
|---|---|
| **Léxica** | Núcleo. Debate entre agentes |
| **Semántica de alcance** | Núcleo. Debate entre agentes |
| **Anafórica** (referente dentro del mismo requisito) | Núcleo. Debate entre agentes |
| **Sintáctica** | Oportunista: solo si el Clasificador genera lecturas alternativas por su cuenta. No se garantiza |
| **Vaguedad** | Secundaria. Catálogo determinista, **sin debate** |
| **Pragmática** | FUERA. Requiere contexto externo no consultable |
| **Contradicción entre requisitos distintos** | FUERA. El sistema procesa cada requisito por separado |

### Términos regionales

Enfoque de tres capas: catálogo determinista, detección por modelo, y el
mecanismo de resolución ya existente.

| Expresión | Clasificación | Lecturas | Tratamiento |
|---|---|---|---|
| jalar | Mexicanismo | consultar / descargar / procesar | Debate |
| checar | Mexicanismo | validar / revisar / mostrar | Debate |
| dar de alta | Administrativo panhispánico | registrar / activar / autorizar | Debate + detección de frase multipalabra |
| ahorita | Mexicanismo | rango temporal impreciso | Catálogo de vaguedad, **sin debate** |

La distinción vaguedad/ambigüedad es crítica: *ahorita* no produce dos lecturas
discretas que comparar, marca un límite temporal impreciso. Sin esa distinción
el sistema intentaría debatir algo que no tiene dos interpretaciones.

El catálogo se construye filtrando dos obras lexicográficas (Gómez de Silva,
*Diccionario breve de mexicanismos*; AML, *Diccionario de mexicanismos*) para
conservar solo vocabulario que aparece en contextos técnicos y de trabajo.

---

## 7. Artefactos de salida

1. **Entrada del LEL** (Léxico Extendido del Lenguaje, de Leite) con campos
   símbolo, tipo (sujeto/objeto/verbo/estado), noción e impacto.
   Es la **memoria del sistema**: un término ya debatido no se vuelve a debatir.
2. **Modelo de metas estratégicas** del dominio.
3. **Big Picture** como representación textual estructurada en JSON o grafo de
   conocimiento. Su conversión a gráfico depende de herramienta externa y queda
   fuera del prototipo.

---

## 8. Stack

> **Decisión en curso (pendiente de confirmar con la asesora).** El Capítulo 3
> está redactado sobre el stack original con Python. Cambiar implica editar
> Alcances, Limitaciones y metodología: unas 2–3 horas.

**Opción recomendada — todo Node:**

| Capa | Tecnología |
|---|---|
| Frontend | React + Vite, JavaScript, React Router, Tailwind |
| Backend | Node + Express o Fastify |
| Orquestación | `@langchain/langgraph` (versión JS) |
| Generación (4 agentes) | Modelos por API |
| Embeddings | Ollama local vía HTTP — gratis, fijo, reproducible |
| Similitud | Coseno, implementado a mano |
| Detección de frases multipalabra | Matcher propio en JS contra el catálogo curado |
| Base de datos | MongoDB |
| Despliegue | Hostinger |

**Qué se gana:** un solo lenguaje, un proceso, sin entornos de Python, costo
acotado (el volumen está en los embeddings, que quedan locales).

**Qué se pierde:** el etiquetado gramatical de spaCy. El filtrado de candidatos
por categoría gramatical pasa al LLM y deja de ser determinista. **Documentar
como ADR.**

**Stack original (si se revierte):** FastAPI + Python, LangGraph, Ollama local
para Extractor/Clasificador/Modelador, API solo para el Crítico, spaCy
`es_core_news_sm` + PhraseMatcher.

**Riesgo conocido:** el costo real de las APIs no está en la evaluación (15–25
requisitos es calderilla) sino en las cientos de corridas depurando prompts
durante el desarrollo.

---

## 9. Alcances y limitaciones

**Alcances**
- Los cuatro agentes programados desde cero, con roles, responsabilidades y
  protocolo de comunicación siguiendo las etapas de KMoS-SSA
- Resolución de ambigüedad léxica, semántica de alcance y anafórica intra-requisito
- Corpus de prueba de 15 a 25 requisitos construidos a propósito, usado para
  calibrar y para evaluar
- Esquema en MongoDB con el historial completo de interpretaciones, debates y
  consensos
- Interfaz web mínima donde un especialista revisa y aprueba los artefactos
- Entrada únicamente de texto plano y PDF con texto extraíble
- Evaluación empírica con grupo reducido, comparando el consenso de los agentes
  contra la interpretación de un solo agente

**Limitaciones**
- Español únicamente
- Un semestre: sin optimización a fondo ni seguridad avanzada
- Herramienta de apoyo a un especialista, no reemplazo; no para sistemas
  críticos ni regulados
- Evaluación con pocos participantes en ambiente controlado: resultados
  exploratorios
- Frontend al mínimo indispensable, sin inversión en diseño visual
- Sin transcripción de voz, visión artificial ni OCR. El motivo no es solo
  tiempo: sus errores se confundirían con ambigüedad real y arruinarían la
  evaluación

---

## 10. Estado actual

**Hecho**
- Revisión sistemática PRISMA 2020 completa: 159 identificados → 33 incluidos
- Capítulo 1 (Antecedentes, Problema, Objetivos, Justificación, Alcances) redactado
- Capítulo 2 (Marco Teórico) redactado
- Capítulo 3: Producto propuesto, Descripción de la metodología, y **Fase 1**
  del nivel proceso
- Proyecto LaTeX organizado, 42 referencias en IEEE, todas las citas resueltas
- Seis tablas y la figura PRISMA referenciadas desde el texto

**Pendiente de redacción**
- Fases 2 a 5 del nivel proceso (Capítulo 3)
- Introducción, Resumen, Capítulos 4 y 5 (siguen con texto de plantilla)

**Pendiente de desarrollo**
- Repositorio: estructura de directorios
- Frontend: 9 pantallas navegables con datos de prueba
- Backend completo
- Corpus de 15–25 requisitos con su ground truth
- Catálogo de mexicanismos y de vaguedad
- LEL del propio dominio del proyecto

---

## 11. Lo siguiente a construir

**Orden recomendado.** El corpus va primero porque todo lo demás calibra
contra él.

1. **Corpus de 15–25 requisitos** con ground truth en archivo separado.
   Incluir casos sin ambigüedad: son los que revelan si el umbral dispara de más.
2. **Contrato de cada agente** — qué recibe y qué entrega, en JSON. De aquí
   salen los requisitos funcionales, no al revés.
3. **Esquema de MongoDB**, derivado de lo anterior.
4. **Requisitos funcionales y no funcionales.** El NFR central es
   **trazabilidad**: cualquier debate debe poder reconstruirse después. Viene
   directo de KMoS-SSA, que exige un punto explícito de revisión humana.
5. **Tres diagramas, no más:** secuencia (un requisito ambiguo atravesando los
   cuatro agentes), actividad (con el punto de decisión del umbral), y
   componentes (con la frontera local/API).
6. **LEL del propio dominio**, con sus ~15–18 símbolos clasificados.

### Las nueve pantallas

1. Carga de requisitos
2. Cola de requisitos con estado
3. **Detalle del requisito** — la traza completa del proceso. Es la pantalla
   que va como figura en la tesis
4. Vista de debate — ronda por ronda, con la similitud recalculada
5. Validación de artefactos — el humano debe poder **editar**, no solo aceptar
6. LEL acumulado
7. Catálogo de términos regionales
8. Calibración — umbral, rondas, modelos. No es opcional: la Fase 3 los calibra
9. Corpus y evaluación — contra el ground truth

### Máquina de estados (fuente de verdad de la UI)

```
cargado -> extraido -> interpretado
   |
   +-- similitud >= umbral -> aceptado_directo
   +-- similitud <  umbral -> en_debate -> consenso | arbitrado
   |
   v
pendiente_validacion -> validado | rechazado -> formalizado
```

---

## 12. Decisiones y pendientes abiertos

| Asunto | Estado |
|---|---|
| Stack Node vs Python | Recomendado Node. Falta confirmar con la asesora |
| Criterios del Crítico | Deben reescribirse como reglas verificables |
| Umbral 0.75 | Provisional. Se calibra en Fase 3 |
| Validación humana | Solo cuando los agentes no llegan a consenso (arbitraje); lo demás se aprueba solo y queda corregible. Configurable con `VALIDACION_HUMANA` (ADR 0017) |
| Contexto del proyecto | Cada proyecto tiene un contexto general que reciben los agentes; el Modelador concreta lo vago con él y anota sus supuestos (ADR 0017) |
| Referencia de Alotaibi | No verificable. Buscar en el registro PRISMA o retirarla |
| Significado de KMoS-SSA | El artículo de 2024 dice *"Knowledge Management of Strategic options through Soft Systemic Analysis"*; el Capítulo 3 dice *"on a Strategy options"*. Conviene alinear |
| Larbi y Akli | Se citan por nombre en la Justificación pero su párrafo de presentación ya no está en Antecedentes |

---

## 13. Observaciones de los evaluadores que el desarrollo debe atender

- **Asesora:** los tres artefactos de salida; cuando el agente genere una
  versión simplificada, debe haber mezcla entre lo del agente y lo del humano
  mediante otra herramienta → de ahí que la pantalla de validación permita editar.
- **Evaluador 1:** no queda clara la función de los agentes, ni cómo se
  detectarán abstracciones como los modismos mexicanos → se contesta con el
  contrato de cada agente y con el diagrama de secuencia, no con más prosa.
- **Evaluador 2:** justificar la metodología, o bien ponerla desde el título y
  argumentarla → resuelto: KMoS-SSA está en el título y la justificación es por
  elección, no por comparación.

---

## 14. Convenciones del repositorio

- **Prompts en archivos versionados**, nunca incrustados en el código. Son el
  método, y el Capítulo 4 tiene que poder decir qué prompt produjo qué resultado.
- **`divergence/` fuera de los agentes.** No es tarea de ningún agente: es el
  mecanismo que decide si hay debate. Debe estar a la vista.
- **`docs/adr/`** — un archivo por decisión de diseño, con fecha y
  justificación. KMoS-SSA pide ciclos iterativos con reflexión; estos archivos
  son esa evidencia, y son el material de las fases 3, 4 y 5.
- **Parámetros calibrables en configuración**, nunca escritos en el código.
- **Vocabulario consistente.** El propio texto de la tesis usaba cuatro palabras
  para el mismo concepto (*interpretación*, *lectura*, *visión*, *postura*).
  En el código, un concepto = un nombre.
