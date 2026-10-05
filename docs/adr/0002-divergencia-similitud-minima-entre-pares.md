# 0002. Divergencia: similitud mínima entre pares y varios términos por requisito

- **Fecha:** 2026-10-05
- **Estado:** Aceptada (el umbral es provisional)

## Contexto

El mecanismo de divergencia es el núcleo de la aportación y no es un agente:
decide si un término se acepta directo o pasa a debate. La especificación pide
embeddings de cada `parafrasis_del_requisito`, similitud coseno implementada a
mano y la regla `similitud >= SIMILARITY_THRESHOLD`. Quedaban abiertos dos
puntos: qué hacer con más de dos interpretaciones y con varios términos ambiguos
en un mismo requisito.

## Decisión

1. **Coseno a mano** con numpy (`a·b / (‖a‖‖b‖)`), en `app/divergence/similitud.py`,
   como función pura. Un vector nulo es un error, no un cero silencioso.
2. **Más de dos interpretaciones → similitud mínima entre pares.** Se registra el
   par que la produce y la matriz completa de pares.
3. **Umbral inclusivo:** `similitud >= umbral` acepta. El valor exacto, el umbral
   usado y el modelo de embeddings se registran en cada mensaje `similitud`.
4. **Varios términos por requisito.** Cada término con interpretaciones tiene su
   propia similitud. La similitud del requisito es la del **peor término** (la
   mínima). Si algún término queda bajo el umbral, el requisito pasa a
   `en_debate` y se debaten **solo** los términos bajo el umbral, todos en las
   mismas rondas. Si al menos un término termina por arbitraje, el requisito
   queda `arbitrado`; si todos alcanzan el umbral o se quedan con una sola
   interpretación válida, queda `consenso`.
5. **Sin términos ambiguos** (todos unívocos, vaguedad o resueltos por el LEL):
   no hay nada que comparar; el requisito pasa a `aceptado_directo` y el mensaje
   `similitud` lo dice explícitamente (`similitud: null`, motivo
   `sin_interpretaciones`).

## Justificación

El mínimo es la lectura conservadora: basta un par divergente para que dos
lectores entiendan distinto (ambigüedad nociva en el sentido de Chantree et al.).
Tomar el peor término por requisito mantiene la máquina de estados por
requisito, que es la unidad que valida el humano.

## Alternativas consideradas

- Promedio de pares: diluye un par divergente entre pares parecidos.
- Similitud contra un centroide: introduce una interpretación artificial que
  nadie propuso.
- Un requisito por término: multiplicaría los requisitos y rompería la unidad de
  validación.

## Consecuencias

- El umbral 0.75 es provisional y se calibra en la Fase 3; no se ajusta para que
  los casos de prueba "salgan bien". Si no separa los casos, es un hallazgo.
- Un requisito con un término claro y otro divergente se debate entero en la
  máquina de estados, aunque solo el término divergente entre al debate.
