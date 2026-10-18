# Dudamel 2.0: de la entrevista a los requisitos, con agentes LLM

Prototipo de tesis de licenciatura: un sistema multiagente basado en LLM y en el marco
KMoS-SSA que lleva una **entrevista de elicitación** en español de México hasta los
**requisitos de software**, pasando por un Léxico Extendido del Lenguaje (LEL) interactivo
que captura la **intención** de cada término del dominio. Cuando un término admite más de
una interpretación (por ejemplo «consultas»: la cita médica o una búsqueda en la base de
datos) y las interpretaciones divergen, los agentes debaten y un agente árbitro decide; una
persona experta valida cada término y el sistema aprende de sus correcciones.

El flujo de un proyecto (versión 2, ADR 0024). Cada fase se abre cuando la anterior quedó
validada por la persona experta:

1. **Entrevista**: se pega su texto o se sube el PDF/.txt; se lee por turnos y hablantes.
2. **LEL interactivo**: los agentes proponen cada término del dominio con su intención,
   sus citas y, si fue ambiguo, las intenciones que se consideraron. La persona valida,
   corrige, elige otra intención o descarta; lo que corrige se guarda como **acuerdo del
   proyecto** («en este proyecto, «consulta» es la cita médica, no una búsqueda») y los
   agentes lo usan desde entonces.
3. **Mapa conceptual con propósito**: la pregunta de enfoque y los conceptos del LEL unidos
   por proposiciones, editable sobre el propio mapa.
4. **Metas**: de la organización, estratégicas y específicas.
5. **Requisitos**: funcionales y no funcionales, cada uno rastreable a sus metas, sus
   términos del LEL y los turnos de la entrevista; la especificación se descarga en Markdown.

La versión 1 (requisitos ya escritos analizados uno por uno, ADR 0001–0023) se conserva en
`/proyectos/:id/v1` y en «Más»: es la base de la evaluación contra el corpus.

## Agentes

| Agente | En la versión 2 (entrevista → requisitos) | LLM |
|---|---|---|
| Revisor | Lee la entrevista: participantes, objetivo, problemas, necesidades y reglas, con sus turnos | Por cuenta (ADR 0021) |
| Extractor | Separa los términos del dominio de la entrevista | Por cuenta |
| Clasificador | Propone la intención de cada término; si ve más de una interpretación, las da como intenciones candidatas | Por cuenta |
| Crítico | Conduce el debate acotado cuando las intenciones divergen y arbitra si se agotan las rondas | Por cuenta |
| Modelador | Formaliza lo validado: las entradas del LEL, el mapa conceptual, las metas y los requisitos | Por cuenta |

La detección de divergencia (embeddings + similitud coseno + umbral) es un mecanismo
aparte en `backend/app/divergence/`, no un agente; es la misma en las dos versiones.

## Stack

- **Backend:** Python + FastAPI
- **Orquestación:** LangGraph
- **LLMs:** cada cuenta elige proveedor y modelo por agente (Ollama local, Gemini, OpenAI, Claude…; ADR 0021)
- **Embeddings:** `nomic-embed-text` vía Ollama, similitud coseno
- **NLP:** spaCy `es_core_news_sm` + `PhraseMatcher`
- **Base de datos:** MongoDB
- **Frontend:** React + Vite (Dudamel); el mapa conceptual se edita con React Flow
- **Despliegue futuro:** Hostinger

## Estructura

```
tesis/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── config.py           # parámetros calibrables desde variables de entorno
│   │   ├── agents/
│   │   │   ├── extractor/
│   │   │   ├── clasificador/
│   │   │   ├── critico/
│   │   │   ├── modelador/
│   │   │   └── revisor/
│   │   ├── entrevistas/        # versión 2: la entrevista en turnos y su bitácora
│   │   ├── fases/              # versión 2: LEL interactivo, memoria, mapa, metas y requisitos
│   │   ├── orchestration/      # grafos LangGraph (requisito y entrevista), cola, servicio
│   │   ├── divergence/         # embeddings, similitud coseno, umbral
│   │   ├── documentos/         # carga de PDF/.txt y separación en requisitos
│   │   ├── analisis/           # vista por término y análisis del proyecto
│   │   ├── artefactos/         # especificación RF/RNF, modelo de metas y Big Picture
│   │   ├── comparacion/        # comparación entre requisitos (exploratorio)
│   │   ├── calibracion/        # umbral sobre entrevistas, prueba de modelos con banco de términos, Overleaf
│   │   ├── evaluacion/         # corpus y evaluación contra un solo agente
│   │   ├── nlp/                # spaCy, etiquetado, PhraseMatcher
│   │   ├── models/             # esquemas Pydantic
│   │   ├── db/                 # cliente Mongo y repositorios
│   │   ├── api/
│   │   │   └── routes/         # endpoints FastAPI
│   │   └── prompts/            # plantillas versionadas <agente>_v<N>.txt
│   └── tests/                  # replica la estructura de app/
├── frontend/                   # Dudamel (React + Vite), conectado al backend
│   └── src/
│       ├── components/
│       ├── escena/             # la escena en vivo dirigida por los mensajes
│       ├── pages/              # proyectos; fases/ (versión 2: entrevista, léxico, mapa, metas, requisitos); versión 1
│       ├── services/           # http.js, backend.js, eventos.js (SSE)
│       └── hooks/
├── data/
│   ├── corpus/                 # requisitos de prueba + ground truth (separado)
│   ├── catalogos/              # mexicanismos y vaguedad
│   └── resultados/             # salidas por corrida
├── docs/
│   ├── lel/                    # LEL del dominio del proyecto
│   ├── diagramas/              # secuencia, actividad, componentes
│   └── adr/                    # decisiones de diseño (incluye plantilla)
└── scripts/                    # carga y evaluación
```

## Configuración

Copia `.env.example` como `.env` y completa los valores. Parámetros calibrables
principales: `SIMILARITY_THRESHOLD` (0.75 inicial) y `MAX_DEBATE_ROUNDS` (2 inicial).
`VALIDACION_HUMANA` decide cuándo espera el sistema a una persona: `si_hay_arbitraje`
(por omisión), `siempre` o `nunca` (ADR 0017).
Las variables de operación (orígenes CORS del frontend, tiempo máximo de cada
llamada a Ollama) están descritas en [`backend/README.md`](backend/README.md).

Instalación, arranque del backend, sandbox (`/sandbox`) y pruebas: ver
[`backend/README.md`](backend/README.md). La interfaz: [`frontend/README.md`](frontend/README.md)
(`npm install && npm run dev` con el backend corriendo). Decisiones de diseño:
[`docs/adr/`](docs/adr/).
