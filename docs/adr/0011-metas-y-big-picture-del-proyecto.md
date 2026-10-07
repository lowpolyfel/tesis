# 0011. Modelo de metas y Big Picture del proyecto, agregados en código

- **Fecha:** 2026-10-06
- **Estado:** Aceptada — **pendiente de revisar con la asesora** (Dra. Karla
  Olmos Sánchez) el uso de tipos al estilo i* y la forma del Big Picture

## Contexto

CONTEXTO §7 pide tres artefactos de salida: la entrada del LEL, el **modelo de
metas estratégicas** del dominio y el **Big Picture** «como representación
textual estructurada en JSON o grafo de conocimiento», cuya conversión a
gráfico queda fuera del prototipo.

El LEL ya existe y es por proyecto (ADR 0007, 0008). Desde el ADR 0010, el
Modelador formaliza además cada requisito aprobado con `modelador_requisito_v1`:
lo reescribe con las interpretaciones validadas y deriva de 1 a 4 **metas**
(contrato `Meta`: `id` M1…, `enunciado` en infinitivo, `tipo` `meta |
meta_blanda | tarea | recurso`, `actor`, `simbolos`, `contribuye_a`). El
documento queda en la colección `formalizados`, uno por requisito.

Falta el nivel proyecto: las metas están repartidas por requisito con ids que
se repiten (todos tienen un M1), el mismo actor aparece escrito de varias
formas («El sistema», «sistema», «los usuarios») y nada une las metas con los
símbolos del LEL ni los requisitos entre sí. La pregunta es si ese nivel lo
arma otro LLM o el código.

## Decisión

1. **Tipos de meta al estilo i\*** (contrato de ADR 0010): `meta` (estado que
   se quiere lograr), `meta_blanda` (cualidad sin criterio exacto), `tarea`
   (forma concreta de lograr una meta) y `recurso` (entidad que se necesita).
   La meta blanda es el destino natural de las expresiones vagas del catálogo
   («rápido», «ahorita»), que no se debaten (ADR 0003). `contribuye_a` solo
   puede apuntar a otra meta **del mismo requisito**: el Modelador ve un
   requisito a la vez.

2. **El nivel proyecto se agrega en código, sin LLM** (`app/artefactos/`).
   Funciones puras sobre los documentos de `formalizados`, el LEL del proyecto
   y el resumen de las trazas; no leen el repositorio (las rutas leen y
   delegan) y se recalculan en cada petición, como las vistas del ADR 0015.
   Cada nodo y cada arista sale de un campo validado o de una coincidencia de
   texto comprobable: el agregado no puede inventar metas, actores ni
   relaciones.

3. **Qué requisitos entran.** Los `formalizado` con documento. Quedan fuera,
   listados en `requisitos_fuera` con su motivo: `en_proceso`, `rechazado`,
   `error`, `reprocesado` (otro requisito vigente lo vuelve a procesar, mismo
   criterio que la comparación, ADR 0012), `sin_formalizacion` (formalizados
   antes del documento por requisito) y `sin_traza`. Nada se deja fuera en
   silencio. El LEL entra completo: es la memoria del proyecto.

4. **Coincidencia de texto** (`terminos.Comparador`). Cada palabra se compara por
   su forma normalizada (minúsculas, sin acentos) y, si el servicio tiene spaCy,
   también por su lema, con las dos claves a la vez como la memoria del LEL
   (ADR 0003, 0004). Un término *aparece* en un texto si sus palabras están
   contiguas en él; dos términos son *el mismo* si coinciden palabra por
   palabra. Sin spaCy solo se compara la forma.

5. **Modelo de metas** (`GET /proyectos/{id}/metas`, `metas_proyecto`):
   - **id global** `R03.M1` (requisito + id local); `contribuye_a` también en
     global;
   - **actores normalizados**: sin artículo inicial, con minúscula inicial salvo
     siglas; los **sujetos del LEL** abren los grupos (su escritura manda) y
     aparecen aunque ninguna meta los nombre; un actor se une al primer grupo con
     el que es *el mismo* (con spaCy, «los usuarios» y «usuario» se unen). Cada
     meta guarda `actor` (normalizado) y `actor_original`;
   - `por_tipo`, `sin_actor`, y `metas_blandas_desde_vaguedad`: cada expresión
     vaga registrada en el documento, con la meta blanda del mismo requisito que
     ya la recoge (si su enunciado la contiene o la lista en `simbolos`) o `null`.

6. **Big Picture** (`GET /proyectos/{id}/big-picture`, `big_picture_proyecto`):
   grafo de conocimiento con nodos `requisito` (`R03`), metas por su tipo
   (`R03.M1`), `actor` (`actor:usuario`) y `simbolo` (`simbolo:sesion`, con su
   categoría del LEL como `subtipo`), y aristas:

   | Arista | De dónde sale |
   |---|---|
   | actor –persigue→ meta | `actor` de la meta |
   | meta –contribuye_a→ meta | `contribuye_a` |
   | meta –deriva_de→ requisito | documento de la meta |
   | meta –usa→ símbolo | un símbolo (o el término del que salió) *aparece* en un elemento de `simbolos` de la meta |
   | requisito –resuelve→ símbolo | `entradas_lel` del documento o entrada del LEL con ese `req_id` |
   | requisito –menciona→ símbolo | el símbolo o su término *aparece* en el requisito original o reescrito, y no lo resolvió ese requisito |
   | símbolo A –relacionado_con→ símbolo B | B *aparece* en una noción o impacto de A |
   | actor –relacionado_con→ símbolo | el actor es un sujeto del LEL |

   Los símbolos se agrupan por forma normalizada: dos entradas del mismo símbolo
   (la inconsistencia del ADR 0015) son un solo nodo con todos sus requisitos de
   origen. Lo que una meta lista en `simbolos` y no está en el LEL no se vuelve
   símbolo: se reporta en `terminos_sin_simbolo`.

7. **Panorama** para la pantalla de Big Picture: actores; acciones (de metas
   `meta` y `tarea`: la primera palabra es el verbo **si tiene forma de
   infinitivo**, si no `verbo: null` y el enunciado completo como objeto);
   restricciones (metas blandas y expresiones vagas que ninguna meta blanda
   recoge); términos resueltos (de `resoluciones`, con la vía y el `cambio` del
   humano); dependencias `{de, a, por}`: el requisito `de` usa (menciona,
   resuelve o tiene una meta que usa) un símbolo que resolvió la formalización
   del requisito `a`; y el requisito reescrito de cada uno.

8. **Exportaciones de texto deterministas**: Mermaid (`flowchart LR`, formas por
   tipo al estilo i\*, colores por tipo con `classDef`, ids saneados a
   `[A-Za-z0-9_]` sin colisiones ni palabras reservadas, etiquetas siempre entre
   comillas con `"`, `#`, `<`, `>` y el acento grave como entidades) y PlantUML
   (diagrama de clases: un símbolo del LEL por clase con noción e impacto como
   atributos `{field}`, actores que no son sujetos del LEL, relaciones entre
   símbolos y «actor → símbolo : verbo (metas)»). Dibujarlos queda en
   herramientas externas.

9. **Artefactos de un requisito** (`GET /requisitos/{id}/artefactos`): el
   documento formalizado tal cual (o `null`), las entradas del LEL que salieron
   de él y sus metas con id global. 404 si el requisito no existe. Un proyecto
   sin formalizados devuelve estructuras vacías, no un error.

## Justificación

Las metas y el LEL ya pasaron por el método (debate, validación humana,
Modelador con salida estructurada). Un segundo LLM que los «resumiera» en un
modelo de proyecto podría unir actores que no son el mismo, inventar
relaciones o metas de proyecto sin respaldo, y ese resultado ya no tendría
punto de revisión humana. Agregar en código hace el Big Picture reproducible,
explicable arista por arista y probado contra datos exactos; es la misma idea
que R1 y R2 del Crítico (ADR 0004): lo que se puede comprobar sin LLM se
comprueba en código.

## Alternativas consideradas

- **Un LLM que construya el modelo de metas del proyecto:** podría inferir
  metas de alto nivel que ningún requisito dice y unir actores por sentido; se
  descartó por alucinación y por romper la trazabilidad.
- **Unir actores y símbolos por embeddings:** toleraría sinónimos, pero haría
  la vista dependiente de Ollama y no determinista (el mismo argumento del ADR
  0015).
- **Guardar el Big Picture en la base al formalizar cada requisito:** segunda
  fuente de verdad que habría que migrar; recalcular es barato con el volumen
  de la tesis.
- **Fusionar el nodo actor con el nodo símbolo cuando el actor es un sujeto del
  LEL:** simplifica el dibujo, pero mezcla dos artefactos distintos (modelo de
  metas y LEL). En el grafo se unen con `relacionado_con`; en PlantUML, que es
  solo un dibujo, sí se dibujan como una sola clase.
- **Crear nodos símbolo para los términos de las metas que no están en el
  LEL:** metería en el Big Picture vocabulario que nadie validó (ADR 0007).

## Consecuencias

- **El modelo de metas es tan bueno como el Modelador.** Este módulo no corrige
  metas mal derivadas: solo las ordena y las une. Las metas no se validan una
  por una (el humano valida las interpretaciones, ADR 0010).
- **No hay metas entre requisitos.** `contribuye_a` es intra-requisito por
  contrato; las dependencias entre requisitos salen solo del vocabulario
  compartido, y son dependencias de vocabulario, no de orden de proceso.
- **La coincidencia es literal o por lema**: no ve sinónimos («cliente» y
  «usuario» son actores distintos) y puede dar falsos positivos con símbolos
  cortos o genéricos («alta» aparece en «dar de alta»). Sin spaCy, «usuarios» y
  «usuario» son actores distintos. El lema de es_core_news_sm depende del
  contexto; por eso se compara también la forma.
- La normalización del actor quita solo artículos iniciales: «sistema de
  nómina» y «sistema» son actores distintos; «el administrador del sistema» no
  se reduce a nada.
- La detección del verbo es por forma (terminación en -ar, -er, -ir, con
  clíticos): un sustantivo como «lugar» al inicio pasa por verbo, y una
  locución como «dar de alta» queda partida («dar» + «de alta …»).
- Un mismo símbolo con dos entradas toma el tipo y la escritura de la del
  requisito más antiguo; las demás nociones se conservan en PlantUML y en sus
  `req_ids`, pero el nodo muestra la primera noción.
- Cada petición recorre todos los formalizados y, con spaCy, analiza cada texto
  una vez: sirve para decenas de requisitos, no para miles (sin caché).
- Mermaid y PlantUML se validaron a mano con sus intérpretes (mermaid 12 y
  PlantUML 1.2024); las pruebas automáticas comprueban la sintaxis con
  expresiones regulares y, si el entorno tiene Node y el paquete `mermaid` del
  frontend, también con el parser de Mermaid.
