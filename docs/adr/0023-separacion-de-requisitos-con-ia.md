# 0023. Separación de requisitos con IA, con los patrones como respaldo

- **Fecha:** 2026-10-12
- **Estado:** Aceptada (amplía ADR 0009)

## Contexto

La separación del texto pegado o de un documento (ADR 0009) solo proponía oraciones con
un verbo de obligación o capacidad («debe», «podrá», «permitirá»…). Los requisitos que
llegan de otra forma quedaban descartados: en presente («La caja imprime el ticket»),
en infinitivo («Registrar ventas»), como historia de usuario («Como gerente quiero…»),
como necesidad («Necesitamos que avise…») o como frase nominal («Registro de
proveedores con su teléfono»).

## Decisión

1. **La limpieza no cambia** (renglones, guiones de corte, encabezados, páginas). Sobre
   los párrafos limpios, el **Revisor** (prompt `revisor_separacion_v1`, con el contexto
   del proyecto: su ficha si está al día) dice qué requisitos hay y de qué párrafos
   salen (`app/documentos/separacion_ia.py`). Va en tandas de hasta 6000 caracteres o
   60 párrafos.
2. **Fidelidad, comprobada en código.** El Revisor copia, no reescribe. Solo puede
   quitar la numeración, unir renglones, componer una frase introductoria con cada
   elemento de su lista y partir un párrafo que pide dos cosas. Si un requisito trae
   palabras que no están en sus párrafos (menos del 80 % de sus palabras), se rechaza
   y se reintenta con el error. Si pide párrafos que no existen, también.
3. **Trazabilidad y nada se pierde.** La página, la marca y el texto original salen de
   los párrafos. Un párrafo que no entró en ningún requisito va a los descartados
   (`no_es_requisito`, con el motivo que dio el Revisor). Las advertencias de largo y
   de repetidos son las mismas que con los patrones (`armar_separacion`).
4. **Respaldo.** Si el Revisor falla, o el texto pasa de 600 párrafos, se separa por
   patrones como antes y se avisa. `metodo` («ia» o «patrones») y `modelo` quedan en
   la separación y en el documento. `SEPARACION_IA=false` o `con_ia: false` usan solo
   patrones.
5. Usa los modelos de la cuenta (ADR 0021): los del dueño del proyecto o, en
   `/requisitos/separar` sin proyecto, los de quien pega el texto.

## Consecuencias

- Se reconocen requisitos en cualquier redacción. La persona sigue confirmando la
  separación y después pasa el triaje (ADR 0022).
- Separar ya no es instantáneo: hay una llamada al LLM por tanda.
- La separación por patrones sigue siendo reproducible y explicable, y es la que usan
  las pruebas de ADR 0009.
