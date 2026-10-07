# frontend

Interfaz en React + Vite + React Router + Tailwind de **Dudamel**. Se pegan los
requisitos de un proyecto, los agentes los analizan a la vista y lo que no tiene
conflicto queda listo solo: requisitos reescritos (funcionales y no
funcionales), léxico y mapa. Una persona revisa solo cuando los agentes no
llegan a un acuerdo y puede corregir cualquier resultado. Todo lo que muestra
viene del backend (FastAPI): no hay datos simulados (ADR 0016, 0017, 0018).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

El backend debe estar corriendo (por omisión en `http://localhost:8000`; ver
`backend/README.md`). Para apuntar a otro servidor, crea `frontend/.env.local`
con `VITE_API_URL=http://otra-maquina:8000`. Si el backend no responde, cada
pantalla lo dice.

El navegador solo deja llamar al backend desde los orígenes que este permite
(CORS). Por omisión acepta `localhost` y `127.0.0.1` en cualquier puerto
(`CORS_ORIGENES_REGEX`), así que da igual si Vite arranca en 5173, 5174 o
`npm run preview` en 4173. Si abres la interfaz desde otra máquina o dominio,
agrega ese origen a `CORS_ORIGENES` en `backend/.env` (separados por coma); si
no, todas las pantallas dirán «No hay conexión con el backend» aunque uvicorn
esté corriendo.

## La esfera

La esfera está montada una sola vez en `App.jsx` (`components/orb/OrbField.jsx`)
y nunca se desmonta: cada pantalla solo le dice dónde estar y qué hacer
(`useOrb()`). Es el centro de la interfaz (ADR 0018):

- **Por sección.** Fuera de la escena vive enorme en el margen de la sección, con
  su centro más allá del borde, y toma el color de la sección. Las secciones
  vecinas alternan de lado, así que al cambiar de sección cruza la pantalla; en
  reposo deriva despacio a lo largo del borde (`components/orb/secciones.js`).
- **Responde a la interfaz.** Al pasar por una pestaña toma su color; al pasar
  por un requisito, el de su estado.
- **Es el menú.** Tocarla (o «Menú») la lleva al centro y la divide en una esfera
  por destino (`components/orb/Orbita.jsx`); Esc o un clic fuera las vuelve a
  fundir.
- **En la escena** se divide en los agentes conforme intervienen.

Fuera de las esferas no hay animaciones: el grano es fijo y las pantallas entran
con un fundido corto.

## La escena en vivo

`/analisis` sigue cada requisito por SSE (`GET /eventos/{req_id}`) y anima
**los mensajes reales de la traza**, en orden (`escena/coreografia.js`):

- una esfera por nodo del grafo (Extractor, Filtros, Clasificador, Divergencia,
  Crítico, Humano y Modelador) que nace por mitosis la primera vez que
  interviene; la esfera principal es el sistema;
- cada mensaje viaja como una partícula del emisor al receptor;
- las interpretaciones de cada término nacen por mitosis del Clasificador y se
  agrupan bajo la Divergencia, más cerca cuanto más se parecen;
- retirar una interpretación la devuelve al Clasificador; en el consenso se
  funden; en el arbitraje el Crítico absorbe las demás; si la validación fue
  automática (ADR 0017) lo acordado pasa directo al Modelador.

Abajo se lee un paso por mensaje en una frase (`escena/pasoSimple.js`); la
bitácora técnica (`escena/resumenMensaje.js`) va plegada. El ritmo se puede
cambiar y «saltar» aplica los mensajes pendientes sin animarlos. Al terminar, se
ve la versión reescrita de cada requisito y lo que espera revisión.

Un requisito en `pendiente_validacion` no se sigue por SSE: nada cambia hasta
que una persona revise, y el navegador solo abre seis conexiones por servidor.

## Pantallas

| Ruta | Qué hay |
|---|---|
| `/` | Presentación y entrada (sin cuentas: el prototipo es de un solo usuario) |
| `/proyectos` | Todos los proyectos; crear uno con su nombre y su contexto general |
| `/proyectos/:id` | Un proyecto: su contexto (editable) y cuatro vistas (`?vista=`): **Requisitos** (estado de cada uno; elegir varios para su mapa o su especificación), **Especificación** (RF/RNF reescritos con sus supuestos, corregibles, en Markdown), **Léxico** (el LEL, corregible) y **Mapa** (Big Picture y modelo de metas, de todos o de los elegidos con `?req=`) |
| `/proyectos/:id/analizar` | Sube un PDF o .txt o pega el texto; se confirma la separación y todo sigue solo. Hasta 200 requisitos por carga y 2000 caracteres por requisito |
| `/analisis?proyecto=&ids=` | La escena en vivo del lote y, al terminar, los resultados |
| `/requisitos/:id` | El resultado (original → versión completa, corregible; qué significado quedó para cada término) y, plegada, la traza por fases KMoS-SSA (`?figura=1`: versión clara para la tesis) |
| `/requisitos/:id/validacion` | Revisión: solo cuando los agentes no llegaron a un acuerdo. Por término se confirma la propuesta, se elige otra o se escribe otra |
| `/mas` | Herramientas fuera del trabajo diario, cada una con una línea |
| `/ambiguedades`, `/comparaciones`, `/flujo`, `/historial`, `/lel` | Análisis del proyecto (desde «Más»); comparaciones es **exploratorio** (ADR 0012) |
| `/catalogos/:tipo`, `/calibracion`, `/evaluacion` | Experimentación (desde «Más») |

Las rutas anteriores (`/inicio`, `/cargar`, `/big-picture`) redirigen a su lugar
nuevo. Las vistas de análisis guardan el proyecto en `?proyecto=`.

## Dónde está cada cosa

- `src/services/http.js`: transporte (URL base, errores `{detail}` → `Error`).
- `src/services/backend.js`: una función por endpoint; ninguna pantalla llama a
  `fetch` directamente.
- `src/services/eventos.js`: SSE de un requisito (mensaje, estado, fin).
- `src/components/ui.jsx`: piezas comunes (volver, encabezado, pestañas, estado
  en lenguaje claro, plegables, avisos).
- `src/components/orb/`: la esfera, sus poses por sección y el menú.
- `src/escena/`: coreografía de la escena, cola de animación (`useEnVivo`) y los
  pasos en lenguaje claro.
- `src/pages/proyecto/`: el proyecto y sus cuatro vistas.
- `src/constants/estados.js`: máquina de estados, la misma del backend, y los
  estados en lenguaje claro (`estadoSimple`).
- `src/constants/agentes.js`: nodos del grafo, fases KMoS-SSA, tipos de
  ambigüedad, requisitos funcionales y no funcionales y reglas del Crítico.
- `src/fixtures/documentoEjemplo.js`: el único texto de ejemplo, para probar la
  carga.
