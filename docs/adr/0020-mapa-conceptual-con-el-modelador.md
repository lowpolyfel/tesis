# 0020. Mapa conceptual organizado por el Modelador sobre un protocolo previo en código

- **Fecha:** 2026-10-12
- **Estado:** Aceptada

## Contexto

La vista **Mapa** del proyecto dibujaba el Big Picture (ADR 0011): el grafo
completo de lo validado, con un nodo por requisito (con todo su texto), por meta,
por actor y por término del léxico, y todas sus aristas (`persigue`, `usa`,
`resuelve`, `menciona`, `relacionado_con`…). Sirve para rastrear, pero no para
leer: con 11 requisitos ya tiene 48 nodos y 115 relaciones. Además repetía
conceptos («usuario» y «usuarios»), trataba a «el sistema» como un actor más y
convertía los verbos del léxico («dar de alta») en conceptos.

## Decisión

1. **Un artefacto nuevo, el mapa conceptual** (`app/artefactos/mapa_conceptual.py`),
   al lado del Big Picture, que se conserva tal cual como «Grafo completo». El mapa
   es un concepto central y a lo más 14 conceptos unidos por, a lo más, 16
   proposiciones «concepto — enlace → concepto», agrupados en ramas.
2. **Protocolo previo en código** (funciones puras, sin LLM), sobre el Big Picture:
   - *conceptos*: actores, términos del léxico (no los verbos, que pasan a ser
     enlaces), objetos de las metas, recursos y cualidades (metas blandas). Los
     repetidos se unen por su forma sin acentos, sin artículo y en singular; «el
     sistema» es el concepto central.
   - *relaciones*: actor —verbo de su meta, en presente→ objeto; objeto —debe
     cumplir→ cualidad; actor —necesita→ recurso; objeto —se avisa a→ actor;
     término —se relaciona con→ término. Cada una con los requisitos que la
     respaldan y un peso.
   - *recorte*: los conceptos y relaciones de más peso, con un máximo de
     relaciones por concepto (`MAX_GRADO`) para que nada se vuelva un nudo.
3. **El Modelador organiza** (`Modelador.mapear`, prompt `modelador_mapa_v1`).
   Recibe los candidatos con su peso y las relaciones candidatas. Elige los
   conceptos, acorta sus etiquetas, los agrupa en ramas y nombra las relaciones.
   Solo puede usar ids candidatos: `verificar_mapa` rechaza cualquier otro, y la
   salida se reintenta una vez con el error (ADR 0001).
4. **Revisión en código**. Una relación nueva del Modelador solo se queda si sus
   dos conceptos comparten un requisito, o si uno es el central; así cada
   proposición se rastrea a lo validado. Se quitan las repetidas y los conceptos
   sueltos. Si el Modelador falla o no responde, queda el mapa del protocolo en
   código, con un aviso.
5. **Se guarda** en `mapas_conceptuales`: uno por proyecto y selección, con la
   huella de lo validado (el Big Picture, el nombre y el contexto del proyecto, el
   modelo y la versión del protocolo). Si la huella cambia, el guardado ya no se
   usa. «Volver a generar» lo rehace. Al borrar el proyecto se borran sus mapas.
6. **Progreso en vivo.** `POST /proyectos/{id}/mapa-conceptual` responde una línea
   JSON por evento (NDJSON): cada paso al empezar y al terminar, y al final el
   mapa. La interfaz cubre el proyecto con un velo, sube la esfera al centro con el
   color del mapa (turquesa a índigo; la sección ya no es amarilla) y escribe
   debajo el paso en curso. Al terminar la esfera vuelve a su lugar en el margen y
   aparece el mapa.
7. **Dibujo**: Mermaid de arriba abajo, sin cajas por rama (obligaban a cruzar
   las líneas de una caja a otra). Las ramas van como leyenda, encima.

## Consecuencias

- El mapa ya no es del todo determinista: depende del Modelador. Lo acotan el
  protocolo (solo candidatos con respaldo) y el guardado (el mismo mapa mientras
  no cambie lo validado). El grafo completo sigue disponible para rastrear.
- Generarlo tarda lo que tarde el Modelador (una llamada). Se ve en la pantalla
  de carga y solo ocurre cuando algo cambió.
- `GET /proyectos/{id}/big-picture` no cambia.
