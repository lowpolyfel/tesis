# 0025. La escena con cuatro esferas como máximo y un motor de esferas sin lag

- **Fecha:** 2026-10-15
- **Estado:** Aceptada (reemplaza la forma de la escena de ADR 0016 §2, 0018 §5 y 0024 §9)

## Contexto

En la escena en vivo (ADR 0016) la esfera principal se dividía en una esfera por nodo del
grafo (Revisor, Extractor, Filtros, Clasificador, Divergencia, Crítico, Modelador), una por
intención de cada término ambiguo y una partícula por mensaje. Con una entrevista real la
escena llegaba a 16 esferas, y a 37 con una bitácora larga. La persona usuaria lo dijo así:
«se ve muy saturada; entiendo el porqué de cada esfera, pero menos es más: son muchos globos
flotando; que sean máximo 4».

Además, la interfaz «daba lag»: el menú de las esferas y casi todas las secciones. Se midió
con el protocolo de DevTools en Chromium, con la CPU limitada a 4× (una laptop), a 1920×1080
y en tema claro, con ablaciones para aislar cada causa:

- **Una sola esfera grande** ocupaba ~12–17 ms del hilo principal por cuadro. Cada esfera
  reescribía 7 `<path>` SVG de 64 segmentos (`setAttribute('d')`: estilo y caja del SVG en
  cada cuadro) y 3 degradados.
- **Cada cambio de ánimo** escribía `--bg`, `--c1`, `--c2`, `--glow`, `--glowSoft` y `--fog`
  en `<html>` a 30 Hz durante 2–5 s. Cada escritura recalcula los estilos de todo el
  documento: ~87 ms con 4×, ~19 ms sin limitar. Era la causa del lag al navegar y al pasar
  el cursor por el camino de fases.
- **El menú** (8 esferas) costaba ~55–68 ms por cuadro. Sus hijas nacían a 0.7× la escala de
  la esfera de sección: capas de ~730 px con el brillo desenfocado.
- **La escena** (11–16 esferas, más la membrana a pantalla completa en cada mitosis) iba a
  3–5 fps.
- **Al entrar al Mapa**, el diagrama Mermaid de «Exportar» se dibujaba aunque el desplegable
  estuviera cerrado: una tarea larga de 0,8–0,9 s.

## Decisión

### 1. La escena: el relevo (`escena/coreografia.js`, `escena/Riel.jsx`)

Cuatro esferas como máximo, con ids fijos, así que el máximo se cumple por construcción:

- **El sistema** (`core`), arriba, con el cronómetro y el estado.
- **El agente** (`agente`), una sola esfera que viaja por las **estaciones** del flujo:
  - en la versión 2: Entrevista (Revisor, Extractor, Filtros), Intención (Clasificador),
    Discusión (Divergencia, Crítico) y Léxico (Modelador);
  - en la versión 1: Requisito, Interpretación, Discusión, Validación (la persona) y
    Formalización.

  En cada mensaje toma el tono y el nombre del emisor; su rótulo dice «Emisor → Receptor» y
  su subtítulo, lo esencial del mensaje. Su viaje sustituye a las partículas.
- **El par** (`par:1`, `par:2`): las dos intenciones más distintas del término en debate
  (`par_minimo` de la divergencia, ADR 0002), más cerca cuanto más se parecen. Cada intención
  conserva su esfera:
  - si una se retira, vuelve al agente;
  - en el consenso, la otra se funde en la propuesta;
  - en el arbitraje, el Crítico absorbe la descartada;
  - lo acordado entra al sistema.

Un **riel** de texto tenue y fijo (sin animación) nombra las estaciones y resalta la del
turno; en teléfonos bajos, donde no cabe, se oculta. La membrana solo aparece en el montaje.
Los pasos diferidos se escalan con el ritmo de la animación. La escena sigue animando
**solo los mensajes reales de la bitácora** (ADR 0016).

### 2. Un motor de esferas que no carga la página (`components/orb/`)

- **Las ondas en un `<canvas>`, dibujado por un worker.** `geometry.js` corre como worker con
  `OffscreenCanvas` y dibuja los mismos contornos con `bezierCurveTo`, sin armar cadenas. Si
  no hay `OffscreenCanvas`, o el worker no carga, se dibujan en el hilo principal. El búfer
  sigue la escala con que se ve la esfera, en escalones con histéresis. Las esferas chicas,
  atenuadas o en reposo se redibujan a 30 Hz.
- **El color del ambiente se interpola solo en `.orb-ambient`**, que pinta el fondo. La raíz
  recibe el valor final una sola vez por cambio de ánimo o de tema.
- **Las vistas previas al pasar el cursor** usan `setMood(m, { ambiente: false })`: cambian
  la esfera, no el fondo. El regreso de la esfera y el del ambiente van por separado.
- **Las variables de color de cada esfera** se escriben a ~20 Hz mientras cambian.
- **Las hijas del menú nacen chicas**, con la clase `es-chica` desde el primer cuadro.
- **React solo vuelve a pintar una esfera** cuando cambian sus rótulos (`rev`).

### 3. Las páginas

- «Exportar» del mapa se monta al abrirlo (`Plegable` con `diferido`).
- Hay un solo sondeo de `/fases`.
- `useApi` recarga en silencio y un cambio local gana a una respuesta más vieja.
- Una caché con revalidación (`hooks/useCache.js`) sirve el léxico y las citas al cambiar de
  fase.
- `memo` en el Léxico y en el editor del mapa.

## Justificación

- **Menos es más, sin perder el método.** Se sigue viendo cada mensaje real: quién habla, a
  quién, qué dijo. Y la divergencia —el corazón de la tesis— sigue siendo dos esferas que se
  acercan o se alejan según la similitud que decidió el debate.
- **El rendimiento se midió antes y después** con el mismo arnés (CPU 4×, 1920×1080, tema
  claro, ms del hilo principal por cuadro):

  | Escenario | Antes | Después |
  |---|---|---|
  | Reposo en una sección | 17 ms | 6 ms |
  | Abrir y cerrar el menú | 68 ms (51 tareas largas) | 24 ms (3) |
  | Cambiar de fase (Léxico → Mapa) | 183 ms | 19 ms |
  | Escena de la entrevista | 296 ms, 3,4 fps | 15 ms, 48 fps |
  | Recálculos de todo el documento al navegar | 24 | 1 |

  El entorno de medición no tiene GPU (el compositor dibuja por software), así que la fluidez
  real con GPU es mejor que la que reflejan estos fps.

## Alternativas consideradas

- **Cuatro esferas fijas, una por fase, con las intenciones como ondas de colores dentro de
  la de Discusión.** Es más quieta, pero la divergencia quedaba en trazos de 1–2 px que casi
  no se leen y obligaba a cambiar el motor.
- **Dos tiempos: flujo y debate**, fundiendo y renaciendo esferas para no pasar de cuatro. Se
  descartó porque las esferas aparecerían y desaparecerían por el límite, no por un mensaje
  (contradice ADR 0018 §6: se mueve solo lo que significa algo), y por ser la más difícil de
  mantener.
- **Seguir con SVG y solo aligerarlo** (menos puntos, sin `toFixed`). Ayudaba, pero cada
  `d` nuevo sigue costando estilo y caja del SVG en el hilo principal.

## Consecuencias

- Ya no se ve una esfera por agente a la vez. El agente que tiene el turno, el riel y la
  columna lateral dicen quién trabaja.
- Las ondas dependen de `OffscreenCanvas` y de workers de módulo, con respaldo en el hilo
  principal (más lento, pero visible).
- Durante el cambio de ánimo (~1–2 s), la barra y las tarjetas toman el tinte nuevo de
  golpe, mientras el fondo lo interpola.
- La versión del sistema pasa a **2.1.0** (frontend y API).
