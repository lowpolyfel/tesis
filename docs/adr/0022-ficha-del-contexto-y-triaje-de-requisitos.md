# 0022. Ficha del contexto y triaje: los requisitos poco detallados se precisan antes de analizar

- **Fecha:** 2026-10-12
- **Estado:** Aceptada

## Contexto

Todo requisito que se cargaba pasaba al grafo, y el Modelador lo reescribía aunque
fuera ambiguo o no tuviera casi detalle: para hacerlo, «concretaba» con supuestos lo
que el texto no decía. Los requisitos deben compararse con el contexto del proyecto,
pero el contexto era texto libre, difícil de leer y de comparar.

## Decisión

1. **Ficha del contexto** (`app/contexto/ficha.py`, colección `fichas_contexto`). Un
   agente nuevo, el **Revisor** (`app/agents/revisor`, prompt `revisor_ficha_v1`),
   ordena el contexto en: resumen, objetivo, actores, conceptos del dominio, procesos,
   reglas, fuera de alcance y lo que el contexto no dice. Se guarda en JSON y en
   Markdown, con la huella del nombre y el contexto: si alguien los edita, la ficha
   deja de estar al día. Se ve y se descarga en el proyecto («ficha del contexto»).
2. **Triaje antes de analizar** (`app/contexto/triaje.py`, prompt `revisor_triaje_v1`).
   Primero una regla en código: lo de menos de 4 palabras es incompleto. Luego el
   Revisor, en tandas de 15, compara cada requisito con la ficha y lo clasifica:
   - **claro**: dice quién, qué y sobre qué, y se entiende con el contexto. Se
     analiza como siempre.
   - **ambiguo**: se entiende qué pide, pero algo admite más de una interpretación o
     es vago. Se analiza, y el grafo se detiene en `humano` aunque los agentes estén
     de acuerdo (`revision_obligatoria`).
   - **incompleto**: no se entiende sin inventar, o no tiene que ver con el
     contexto. No se puede analizar hasta que la persona lo precise (lo reescribe y
     se vuelve a revisar), lo mande así a propósito (va con revisión obligatoria) o
     lo quite.

   Cada veredicto trae su motivo, lo que falta y de 1 a 3 preguntas para la persona.
   Si el Revisor falla, no inventa veredictos: los requisitos quedan «sin revisar» y
   la pantalla lo dice.
3. **El veredicto viaja con el requisito.** `POST /proyectos/{id}/requisitos` lo
   recibe, se guarda en `config.triaje` de la traza (también si se precisó o se forzó)
   y la página de revisión lo muestra.

## Consecuencias

- Lo que antes se reescribía con supuestos ahora lo precisa una persona, que es
  quien sabe lo que quiso decir.
- Antes de analizar hay una llamada más al LLM por cada 15 requisitos, y una para
  armar la ficha cuando el contexto cambió.
- El triaje decide si se pide revisión, pero no reemplaza el análisis de
  ambigüedad léxica del grafo (Clasificador, divergencia y debate).
