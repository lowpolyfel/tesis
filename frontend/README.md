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
- **En la escena** se divide en cuatro esferas como máximo: el sistema, el agente
  que tiene el turno y las dos intenciones en debate (ADR 0025).

Fuera de las esferas no hay animaciones: el grano es fijo y las pantallas entran
con un fundido corto.

## Las esferas en la versión 2 (ADR 0024)

- Cada fase del proyecto es una sección con su tono: entrevista (rosa durazno), léxico
  (cian), mapa (turquesa a índigo), metas (oro a coral) y requisitos (verde). El camino
  del proyecto (`components/fases/Camino.jsx`) dibuja una esfera pequeña por fase que se
  llena al validarse.
- **Recibe la entrevista**: se suelta el PDF sobre la esfera (`pages/fases/NuevaEntrevista.jsx`).
- **La procesa en escena** (`pages/fases/EscenaEntrevista.jsx`): la misma coreografía de
  la versión 1 con otras estaciones (Entrevista, Intención, Discusión, Léxico) y la
  bitácora de la entrevista por SSE.
- **Aprende**: lo que la persona valida o corrige en el léxico, las metas o los requisitos
  viaja como una esfera pequeña de la tarjeta a la esfera grande
  (`components/fases/vuelo.js`); si el sistema aprendió un acuerdo, la esfera toma el tono
  «aprende» y lo dice.
- **Genera** el mapa, las metas y los requisitos al centro, con los pasos debajo
  (`components/fases/GeneracionFase.jsx`).

## La escena en vivo

Antes de empezar, la esfera grande al centro prepara todo y lo va diciendo
(`escena/Preparacion.jsx`): conecta con el servidor, con la base de datos
(`GET /preparacion`) y con Ollama, y carga en memoria cada modelo del análisis
que no esté cargado (`POST /preparacion/cargar`), para que el primer requisito
no espere a que Ollama lea el modelo del disco. Si falta algo (Ollama apagado,
un modelo sin descargar) lo dice y ofrece reintentar o seguir de todos modos.
Si todos los requisitos ya terminaron, se salta.

`/analisis` sigue cada requisito por SSE (`GET /eventos/{req_id}`) y anima
**los mensajes reales de la traza**, en orden (`escena/coreografia.js`):

- cuatro esferas como máximo (ADR 0025). La principal es el **sistema**, arriba,
  con el cronómetro;
- el **agente** es una sola esfera que viaja por las estaciones del flujo
  (Requisito, Interpretación, Discusión, Validación y Formalización en la v1;
  Entrevista, Intención, Discusión y Léxico en la v2, `escena/Riel.jsx`). Toma el
  tono y el nombre de quien emite cada mensaje («Extractor → Filtros») y dice lo
  esencial en su subtítulo; su viaje es el mensaje;
- el **par**: las dos intenciones más distintas del término en debate
  (`par_minimo` de la divergencia), más cerca cuanto más se parecen. Si una se
  retira vuelve al agente; en el consenso se funden en la propuesta; en el
  arbitraje el Crítico absorbe la otra; lo acordado entra al sistema.

En escritorio los requisitos van en una columna vertical a la derecha (el que
se analiza arriba, con su paso actual, y la lista del lote con su estado) y las
esferas ocupan el resto de la pantalla, más grandes. En móvil, el requisito va
arriba y el paso abajo.

Se lee un paso por mensaje en una frase (`escena/pasoSimple.js`); la
bitácora técnica (`escena/resumenMensaje.js`) va plegada. El ritmo se puede
cambiar y «saltar» aplica los mensajes pendientes sin animarlos. Al terminar, se
ve la versión reescrita de cada requisito y lo que espera revisión.

Un requisito en `pendiente_validacion` no se sigue por SSE: nada cambia hasta
que una persona revise, y el navegador solo abre seis conexiones por servidor.

## Pantallas

| Ruta | Qué hay |
|---|---|
| `/` | Presentación y entrada (sin cuentas: el prototipo es de un solo usuario) |
| `/proyectos` | Todos los proyectos, con su avance por fases; crear uno con su nombre y su contexto general |
| `/proyectos/:id?fase=` | Versión 2: el proyecto y su camino de fases — **Entrevista** (las entrevistas, su ficha y sus turnos), **Léxico** (el LEL interactivo y lo que aprendió el sistema), **Mapa** (el mapa con propósito, editable con React Flow), **Metas** (árbol de tres niveles) y **Requisitos** (con trazabilidad; descarga la especificación en Markdown) |
| `/proyectos/:id/entrevista` | Subir (PDF o .txt) o pegar una entrevista; vista previa de turnos y hablantes |
| `/proyectos/:id/entrevistas/:e` | La escena: los agentes procesan la entrevista (`?escena=1` la repite) |
| `/proyectos/:id/v1` | Versión 1: su contexto (editable) y cuatro vistas (`?vista=`): **Requisitos** (estado de cada uno; elegir varios para su mapa o su especificación), **Especificación** (RF/RNF reescritos con sus supuestos, corregibles, en Markdown), **Léxico** (el LEL, corregible) y **Mapa** (el mapa conceptual que organiza el Modelador, con su pantalla de carga; debajo sus frases, el modelo de metas y el grafo completo; de todos o de los elegidos con `?req=`) |
| `/configuracion` | Proveedor y modelo de cada agente (Ollama, Gemini, OpenAI, Claude…) y sus claves, que se guardan cifradas (ADR 0021) |
| `/proyectos/:id/analizar` | Sube un PDF o .txt o pega el texto; se confirma la separación y el Revisor separa los que se entienden con el contexto de los ambiguos y los poco detallados, que se precisan antes de analizar (ADR 0022). Hasta 200 requisitos por carga y 2000 caracteres por requisito |
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
- `src/pages/fases/`: la versión 2 — el proyecto por fases, la entrevista, su escena, el
  léxico, el mapa, las metas y los requisitos.
- `src/components/fases/`: el camino, el editor del mapa (React Flow), la pantalla de
  generación, las citas y el vuelo de las esferas.
- `src/constants/fases.js`: las fases, sus tonos y los estados en lenguaje claro.
- `src/pages/proyecto/`: el proyecto de la versión 1 y sus cuatro vistas.
- `src/constants/estados.js`: máquina de estados, la misma del backend, y los
  estados en lenguaje claro (`estadoSimple`).
- `src/constants/agentes.js`: nodos del grafo, fases KMoS-SSA, tipos de
  ambigüedad, requisitos funcionales y no funcionales y reglas del Crítico.
- `src/components/sesion.jsx`: la cuenta con sesión (`GET /auth/yo`) y
  `RequiereSesion`, que lleva a «Entrar» las pantallas de la app.
- `src/pages/cuenta/`: entrar, crear cuenta, código del correo y restablecer.
- `src/components/tema.jsx`: modo oscuro o claro (`<html data-tema>`), guardado
  en el navegador; el botón ☀/☾ está en la barra.

Sin datos de ejemplo: todo sale del backend y cada cuenta empieza sin proyectos.
La sesión es una cookie HttpOnly del backend (`credentials: "include"`), así que
el origen del frontend debe estar en `CORS_ORIGENES`.

Rendimiento (ADR 0019 y 0025): lo que se anima en cada cuadro solo cambia `transform`
u `opacity`. No uses `backdrop-filter`, filtros SVG ni `mix-blend-mode` sobre
algo que se mueva o que tenga la esfera detrás: obligan a repintar áreas
grandes en cada cuadro. Las ondas de cada esfera se dibujan en un `<canvas>`
desde un worker (`components/orb/geometry.js`, con `OffscreenCanvas`; sin él,
en el hilo principal). El color del ambiente se interpola solo en `.orb-ambient`:
la raíz recibe el valor final una vez por cambio, porque cada variable escrita en
`<html>` recalcula los estilos de todo el documento. Las vistas previas al pasar
el cursor usan `setMood(m, { ambiente: false })`: cambian la esfera, no el fondo.
