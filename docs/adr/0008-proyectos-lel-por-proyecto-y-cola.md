# 0008. Proyectos, LEL por proyecto y cola de un solo trabajador

- **Fecha:** 2026-10-06
- **Estado:** Aceptada

## Contexto

Hasta ahora el sistema procesaba un requisito suelto a la vez y el LEL era
global. Para cargar un documento (PDF) con muchos requisitos, compararlos entre
sí y evaluar contra un corpus hace falta agruparlos. Además, Ollama local atiende
una generación a la vez: lanzar varios grafos en paralelo solo los hace competir
por la GPU, y la validación humana debe seguir siendo por requisito (punto de
revisión explícito de KMoS-SSA).

## Decisión

1. **Proyecto** (`P01`, `P02`…): agrupa requisitos de un mismo dominio. Siempre
   existe `P00 General`, donde quedan los requisitos sin proyecto (y los
   procesados antes de esta decisión, que no tienen el campo).
2. **El LEL es por proyecto.** La memoria del sistema no se mezcla entre
   dominios: *sesión* puede significar una cosa en banca y otra en un expediente
   clínico. El nodo `cargado` fija el LEL del proyecto del requisito. Cada
   entrada formalizada guarda su `proyecto_id`.
3. **Origen del requisito** en la traza (`origen`: documento, archivo, página,
   índice, texto original): trazabilidad hasta el documento del que salió.
4. **Cola con un solo trabajador** (`app/orchestration/cola.py`). Todo lo que
   llama a un LLM pasa por ella. Prioridades: reanudar una validación (el humano
   está esperando) > continuar un grafo interrumpido > ejecutar un requisito
   nuevo > análisis de proyecto. Dentro de la misma prioridad, orden de llegada.
5. **Validación uno por uno**: cada requisito pausa en `pendiente_validacion` y
   espera su propia validación; no hay aprobación en bloque.
6. **Recuperación al arrancar:** los requisitos en `cargado` se vuelven a
   encolar; los que quedaron a mitad del grafo continúan desde su último
   checkpoint (`invoke(None)`); los que esperan validación siguen esperando.
7. **Almacén genérico** en el repositorio (`crear_doc`, `guardar_doc`,
   `obtener_doc`, `listar_docs` por colección) para proyectos, documentos,
   comparaciones y evaluaciones, con ids consecutivos por prefijo. Cada módulo
   valida sus datos con su propio modelo Pydantic.

## Alternativas consideradas

- **LEL global:** más simple, pero mezcla dominios y hace que un significado
  validado en un proyecto se imponga en otro.
- **Varios trabajadores:** con Ollama local no acelera; con un proveedor externo
  podría, y bastaría con subir el número de hilos.
- **Aprobación en bloque de los requisitos sin ambigüedad:** más rápida, pero
  debilita el punto de revisión humana; se descartó.

## Consecuencias

- Al continuar un grafo interrumpido a mitad de un nodo, los mensajes que ese
  nodo ya había emitido pueden quedar repetidos en la traza (el nodo se reejecuta
  completo). Se acepta: la traza conserva ambos y el orden lo dice `secuencia`.
- Las pruebas y los scripts pueden seguir corriendo el grafo en el mismo hilo
  (`procesar`, `validar`); la API siempre encola.
