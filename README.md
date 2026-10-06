# Detección de ambigüedad en requisitos con agentes LLM

Prototipo de tesis de licenciatura: un sistema de cuatro agentes basados en LLM que
detecta ambigüedad en requisitos de software escritos en español de México. Cuando dos
interpretaciones de un mismo requisito divergen, se activa un debate acotado y un agente
árbitro decide. El resultado se formaliza como entrada de un Léxico Extendido del
Lenguaje (LEL).

## Agentes

| Agente | Rol | LLM |
|---|---|---|
| Extractor | Separa el vocabulario del dominio del requisito crudo | Ollama local |
| Clasificador | Genera interpretaciones candidatas de términos con más de una lectura | Ollama local |
| Crítico | Conduce el debate acotado y arbitra si se agotan las rondas | API externa |
| Modelador | Genera los artefactos desde la interpretación validada | Ollama local |

La detección de divergencia (embeddings + similitud coseno + umbral) es un mecanismo
aparte en `backend/app/divergence/`, no un agente.

## Stack

- **Backend:** Python + FastAPI
- **Orquestación:** LangGraph
- **LLMs:** Ollama local (Extractor, Clasificador, Modelador); modelo por API (Crítico)
- **Embeddings:** `nomic-embed-text` vía Ollama, similitud coseno
- **NLP:** spaCy `es_core_news_sm` + `PhraseMatcher`
- **Base de datos:** MongoDB
- **Frontend:** React (mínimo, para observar y validar)
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
│   │   │   └── modelador/
│   │   ├── orchestration/      # grafo LangGraph, estado compartido, nodos
│   │   ├── divergence/         # embeddings, similitud coseno, umbral
│   │   ├── documentos/         # carga de PDF/.txt y separación en requisitos
│   │   ├── analisis/           # vista por término y análisis del proyecto
│   │   ├── artefactos/         # modelo de metas y Big Picture del proyecto
│   │   ├── comparacion/        # comparación entre requisitos (exploratorio)
│   │   ├── calibracion/        # sensibilidad del umbral
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
│       ├── pages/
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

Instalación, arranque del backend, sandbox (`/sandbox`) y pruebas: ver
[`backend/README.md`](backend/README.md). La interfaz: [`frontend/README.md`](frontend/README.md)
(`npm install && npm run dev` con el backend corriendo). Decisiones de diseño:
[`docs/adr/`](docs/adr/).
