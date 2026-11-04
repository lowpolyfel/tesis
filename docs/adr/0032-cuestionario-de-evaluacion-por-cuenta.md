# 0032. Cuestionario de evaluación por cuenta, abierto al terminar un proyecto

- **Fecha:** 2026-11-04
- **Estado:** Aceptada

## Contexto

La evaluación con usuarios compara hacer el trabajo a mano contra hacerlo con DUDAMEL. Usa el
cuestionario de `docs/cuestionario-evaluacion.md`: 60 preguntas en 7 secciones, con el SUS en
las preguntas 25–34.

**Requisitos:**

- Se llena dentro del sistema, como formulario, y se guarda por usuario.
- Se entra desde el lobby de proyectos.
- Solo se puede contestar después de recorrer el camino completo.

## Decisión

**Cuándo se abre.** Cuando la cuenta con sesión tiene al menos un proyecto propio que llegó a
la quinta fase. Eso quiere decir que existe su documento en `fase_requisitos`; no exige que los
requisitos estén validados. La tarjeta del lobby está siempre a la vista, cerrada con candado
hasta entonces. El backend lo exige también: `PUT` y `POST` responden 403.

**Las preguntas viven en el backend** (`app/cuestionario`), con su tipo:

- opción
- escala 1–5
- número
- casillas, con una opción exclusiva («Ninguno»)
- texto abierto

El frontend las pinta tal cual. Las abiertas son opcionales y lo demás es obligatorio. El SUS
conserva su orden y su redacción.

**Uno por cuenta.** Se guarda en la colección `cuestionarios`, y el id del documento es el de la
cuenta.

- **Borrador:** se guarda solo mientras se contesta.
- **Envío:** exige todas las obligatorias y calcula el SUS (impares valor−1, pares 5−valor, ×2.5).
- **Después del envío:** se puede corregir, pero sin dejar vacía ninguna obligatoria.

**Anonimato.** La presentación dice que es anónimo. La cuenta se guarda solo para que nadie
conteste dos veces. Los resultados y el CSV no la incluyen: cada fila es R01, R02… por orden
de envío.

**Resultados.** Solo los ven los correos de `CUESTIONARIO_ADMINS`; no había un rol de
administración. Siguen el protocolo del md:

- **SUS:** media, mediana y DE.
- **Escalas:** mediana y RIC. En las de comparación (9–20), además el % arriba del punto medio.
- **Conteos:** media, mediana y rango.
- **Opciones y casillas:** frecuencias.
- **Abiertas:** las respuestas, para codificarlas.
- **Fallas de infraestructura:** cuántos dijeron haberlas tenido (pregunta 50).

## Alternativas consideradas

- **Un formulario externo (Google Forms):** no sabría quién terminó un proyecto y no se puede
  condicionar.
- **No guardar la cuenta:** no habría forma de evitar respuestas duplicadas ni de retomar un
  borrador.
- **Abrir el cuestionario cuando los requisitos estén validados:** se descarta. «Llegar a
  requisitos» es lo pedido, y validar todos puede quedar pendiente por detalles.

## Consecuencias

- Quien coordina la evaluación debe poner su correo en `CUESTIONARIO_ADMINS` (Render: variable
  de entorno).
- El anonimato es frente a los resultados, no frente a la base de datos: quien tenga acceso a
  Mongo puede ver qué cuenta contestó qué.
- La versión pasa a **2.7.0**.
