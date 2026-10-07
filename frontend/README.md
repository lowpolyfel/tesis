# frontend

Interfaz en React + Vite + React Router + Tailwind de **Dudamel**. Tiene dos
trabajos: dejar ver qué hace cada agente mientras procesa un requisito y
permitir que una persona valide sus interpretaciones. Todo lo que muestra viene
del backend (FastAPI): no hay datos simulados (ADR 0016).

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
(`useOrb()`). Puede dividirse en varias esferas (mitosis) y volver a fundirse.

## La escena en vivo

`/analisis` sigue cada requisito por SSE (`GET /eventos/{req_id}`) y anima
**los mensajes reales de la traza**, en orden (`escena/coreografia.js`):

- una esfera por nodo del grafo: Extractor, Filtros, Clasificador, Divergencia,
  Crítico, Humano y Modelador; la esfera principal es el sistema;
- cada mensaje viaja como una partícula del emisor al receptor;
- las interpretaciones de cada término nacen por mitosis del Clasificador y se
  agrupan bajo la Divergencia, más cerca cuanto más se parecen;
- retirar una interpretación la devuelve al Clasificador; en el consenso se
  funden; en el arbitraje el Crítico absorbe las demás.

La bitácora al lado resume cada mensaje. El ritmo se puede cambiar, y
«saltar» aplica los mensajes pendientes sin animarlos: la escena queda como
dice la traza. «Ver la escena otra vez» la repite desde la traza. El texto del
requisito se marca con las marcas de la vista del backend (`marcados`), al paso
de la animación.

Un requisito en `pendiente_validacion` no se sigue por SSE: nada cambia hasta
que una persona valide, y el navegador solo abre seis conexiones por servidor
(una por pestaña agotaría las demás). La traza y la validación vuelven a
seguirlo al enviar la validación.

## Pantallas

| Ruta | Qué hay |
|---|---|
| `/` | Presentación y entrada (sin cuentas: el prototipo es de un solo usuario) |
| `/inicio` | Sube un PDF o .txt (el backend extrae el texto y separa los requisitos, con página y marca) o pega el texto; confirmas o editas la separación (con los fragmentos descartados y lo que quitó la limpieza a la vista) y eliges el proyecto. Un documento subido queda en el proyecto elegido al subirlo. Hasta 200 requisitos por carga y 2000 caracteres por requisito |
| `/analisis?proyecto=&ids=` | La escena en vivo del lote, la bitácora y los requisitos que esperan validación |
| `/requisitos/:id` | Traza por fases KMoS-SSA: extracción, filtros, interpretaciones por término, matriz de similitud por pares, rondas del debate con las reglas del Crítico, arbitraje, validación y formalización (`?figura=1` versión clara para la tesis) |
| `/requisitos/:id/validacion` | Validación: por término se elige otra interpretación o se reescribe; la decisión (aprobar o rechazar) es una sola para todo el requisito |
| `/proyectos`, `/proyectos/:id` | Proyectos con sus contadores; un proyecto agrupa requisitos por ciclo, sus documentos y su LEL |
| `/historial` | Todos los requisitos, la cola de trabajo y filtros por proyecto y estado |
| `/lel` | El LEL de cada proyecto |
| Análisis ▸ `/ambiguedades` | Términos ambiguos del proyecto por tipo y vía, significados validados, inconsistencias, alcance y anáfora, vaguedad y regionalismos |
| Análisis ▸ `/comparaciones` | **Exploratorio** (ADR 0012): contradicción, redundancia, casi duplicados e inconsistencias de vocabulario entre requisitos, con matriz de similitud |
| Análisis ▸ `/big-picture` | Modelo de metas, panorama y grafo del proyecto (exporta PNG, SVG, Mermaid y PlantUML) |
| Análisis ▸ `/flujo` | Espiral KMoS-SSA: anillos = ciclos, sectores = las cinco fases, mensajes por agente |
| Ajustes ▸ `/catalogos/:tipo` | Catálogos regionales y de vaguedad (solo lectura) |
| Ajustes ▸ `/calibracion` | Sensibilidad del umbral y contraste con el ground truth (solo lectura) |
| Ajustes ▸ `/evaluacion` | Corpus, corridas y comparación con la línea base de un solo agente |

Las vistas de análisis guardan el proyecto en `?proyecto=`, así un enlace se
puede compartir.

## Dónde está cada cosa

- `src/services/http.js`: transporte (URL base, errores `{detail}` → `Error`).
- `src/services/backend.js`: una función por endpoint; ninguna pantalla llama a
  `fetch` directamente.
- `src/services/eventos.js`: SSE de un requisito (mensaje, estado, fin).
- `src/escena/`: coreografía de la escena y la cola de animación (`useEnVivo`).
- `src/constants/estados.js`: máquina de estados, la misma del backend
  (estados, transiciones, etiquetas y colores).
- `src/constants/agentes.js`: nodos del grafo, fases KMoS-SSA, tipos de
  ambigüedad y reglas del Crítico.
- `src/fixtures/documentoEjemplo.js`: el único texto de ejemplo, para probar la
  carga desde `/inicio`.
