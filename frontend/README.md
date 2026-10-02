# frontend

Interfaz en React + Vite + React Router + Tailwind de **Dudamel**. Tiene dos
trabajos: observar cómo negocian los agentes y permitir que una persona valide
los artefactos. Todavía **no está conectada al backend**: todo funciona con
datos de prueba.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

## La esfera

La esfera está montada una sola vez en `App.jsx` (`components/orb/OrbField.jsx`)
y nunca se desmonta: cada pantalla solo le dice dónde estar y qué hacer
(`useOrb()`). Puede dividirse en varias esferas (mitosis) y volver a fundirse;
una membrana las une mientras se separan.

## Flujo principal

| Ruta | Qué pasa |
|---|---|
| `/` | Carga en blanco, nace la esfera, clic para empezar, login/registro (sin validar) |
| `/inicio` | «¿Qué analizamos hoy?»: suelta el archivo sobre la esfera o pega el texto; confirmas la separación |
| `/analisis?ids=` | La esfera se divide en Extractor, Clasificador, Crítico y Modelador. Si hay debate, el Clasificador se divide en Lectura A y B, que se acercan según la similitud; al consenso se funden, en arbitraje las absorbe el Crítico. Al final todo vuelve a una esfera y aparecen los resultados |
| `/lel/generar?ids=` | El Modelador redacta el LEL; editas y apruebas |
| `/big-picture?ids=` | Panorama del lote (JSON) y modelo conceptual UML (Mermaid; exporta PNG, SVG, .mmd y .puml) |
| `/flujo?proyecto=` | Flujo de conocimiento continuo en espiral (adaptado de KMoS-SSA / SysM2): anillos = ciclos, sectores = fases, conteo de interacciones por agente |

## Herramientas (menú superior)

| Ruta | Pantalla |
|---|---|
| `/proyectos`, `/proyectos/:id` | Cada proyecto con sus requisitos por ciclo, su LEL, su Big Picture y su modelo conceptual |
| `/ambiguedades` | Cada término ambiguo, dónde aparece, qué lectura se adoptó; señala resoluciones distintas y compara requisitos |
| `/historial` | Todos los requisitos con filtro por estado |
| `/requisitos/:id` | Traza completa por etapas y debate (`?figura=1` versión clara para la tesis) |
| `/requisitos/:id/validacion` | Validación detallada de LEL, metas y Big Picture |
| `/lel` | Léxico acumulado |
| `/catalogos/:tipo` | Mexicanismos y vaguedad |
| `/calibracion` | Umbral, rondas y modelo por agente |
| `/evaluacion` | Corpus contra ground truth |

## Dónde está cada cosa

- `src/constants/estados.js`: máquina de estados, **única fuente de verdad**
  (estados, transiciones, etiquetas y colores).
- `src/services/api.js`: **todas** las llamadas al backend. Hoy son stubs; cada
  función indica el endpoint previsto. Al conectar FastAPI solo cambia este archivo.
- `src/services/polling.js`: sondeo del estado (el proceso tarda segundos).
- `src/services/mockDb.js` y `simulacion.js`: base y proceso simulados; solo los
  usa `api.js` y desaparecen con el backend.
- `src/fixtures/`: datos de prueba. Casos clave: REQ-001 (directo),
  REQ-002 (consenso en ronda 1), REQ-003 (arbitraje).

Los cambios hechos en la interfaz se guardan en localStorage. «Restaurar datos
de prueba» (al pie de Calibración) vuelve al estado inicial y relanza los requisitos que
se ven procesándose en vivo.
