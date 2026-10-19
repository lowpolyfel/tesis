# 0030. Revisión de calidad fuera del sistema: un archivo a ciegas que contesta una persona o una IA

- **Fecha:** 2026-10-19
- **Estado:** Aceptada (completa ADR 0029; no cambia sus criterios ni sus métricas)

## Contexto

La revisión de calidad del ADR 0029 se hace en la pantalla, salida por salida. Una prueba con dos
modelos y el banco v2 tiene unas 143 salidas, más los falsos negativos por clasificar. En la primera
revisión real se fue mucho tiempo en eso. Además se quería:

- que una segunda persona pudiera revisar sin entrar al sistema;
- poder pedirle la revisión a una IA y comparar su juicio con el humano.

En esa misma revisión salieron varios casos que la rúbrica no decía de forma explícita: una
paráfrasis que deja el término, una «o» que junta dos sentidos o solo enumera, unas siglas
desarrolladas, un significado demasiado general. Se decidieron una vez y había que poder aplicarlos
igual después, se revise en la pantalla o fuera de ella.

## Decisión

### 1. Exportar un archivo a ciegas

`GET /pruebas-modelos/{id}/revision-calidad/exportar?formato=md|json&pendientes=` devuelve un
archivo con:

- las instrucciones;
- la rúbrica con sus casos frecuentes y el catálogo de modos de falla;
- cada salida revisable con su término, dominio, contexto, cita, lecturas esperadas (solo en los
  ambiguos) e intenciones;
- los falsos negativos con la respuesta del modelo;
- una plantilla JSON para contestar.

El Markdown se pega en el chat de una IA o se le da a una persona; el JSON sirve para procesarlo con
un programa.

**A ciegas.** El archivo no trae proveedor, modelo ni el id interno del modelo:

- Cada salida se llama `S015`, que es su lugar en el orden barajado de la revisión. Es el mismo
  número que muestra la pantalla («salida 15 de 143»).
- Cada falso negativo se llama `F07`, en un orden barajado aparte con una semilla derivada.

**Exportar no crea la revisión.** Si todavía no hay revisión, el orden sale de una semilla nueva que
viaja en el archivo. Con `pendientes=true` solo van las salidas sin marcar y los falsos negativos sin
modo.

### 2. Importar lo contestado, con su origen

`POST /pruebas-modelos/{id}/revision-calidad/importar` recibe `{contenido, tipo: persona|ia, quien,
sobrescribir}`.

**Qué acepta.** Toma el archivo tal cual o la respuesta de un chat: busca el último bloque ` ```json `
o, si no hay, el texto entre la primera llave y la última.

**Qué valida antes de tocar nada:**

- **El formato y el código de la prueba.**
- **La huella del orden.** El servidor rehace el orden con la semilla del archivo (o usa el de la
  revisión) y compara un hash de los pares (ítem, modelo). Si no coincide, la prueba cambió o el
  archivo es de otra revisión: se rechaza con 422 y se pide exportar de nuevo. Lo mismo vale para
  los falsos negativos.

**Respuestas que no se aplican:**

- Una respuesta con un criterio en `null` cuenta como «sin contestar».
- Un id que no existe, lecturas fuera de rango o un modo que no está en el catálogo son errores de
  ese id, y no detienen el resto.

**Lo que guarda:**

- Cada marca y cada modo importados llevan `origen: {tipo, quien, importacion}`.
- La revisión guarda cada importación: quién la hizo, cuántas marcas aplicó y conservó, el acuerdo y
  las respuestas tal como llegaron, incluidas las que no se aplicaron. Con eso se puede rehacer el
  cálculo.
- Si no había revisión, se crea con la semilla del archivo y `revisor_tipo`.

**Por omisión no se pisa lo ya marcado.** Lo que se conserva sirve para medir el acuerdo entre quien
contestó el archivo y la revisión que ya había: kappa de Cohen por criterio, y cuántas veces
coinciden exactamente las lecturas. Con `sobrescribir` se pisa.

### 3. Lo que hizo una IA se dice

`resumen` avisa cuántas marcas de calidad puso una IA y quién fue. Lo llama una evaluación con un LLM
como juez, no una revisión humana, y pide reportarla así y validarla contra marcas humanas. También
avisa de las marcas que una persona contestó fuera del sistema.

El paquete para Overleaf dice de dónde salieron las marcas (en pantalla, por archivo, de IA como
juez) en la línea de la revisión y en los avisos.

Las métricas no cambian. Los tres criterios y la cobertura se calculan igual que en ADR 0029, sobre
todas las marcas, venga cada una de donde venga.

### 4. Casos frecuentes en la rúbrica

`rubrica.ACLARACIONES` precisa cómo se aplican los mismos tres criterios. Son los casos decididos en
la primera revisión real:

- **Fidelidad:**
  - Una paráfrasis que deja el término o copia la cita no pasa.
  - La fidelidad no juzga si el sentido es el correcto.
- **Delimitación:**
  - Una «o» que junta dos sentidos distintos no pasa; una que enumera quién ocupa el mismo papel sí
    pasa.
  - Un significado demasiado general no pasa.
  - Unas siglas desarrolladas son circulares.
  - No importa cuántos sentidos dio el modelo.
- **Intención:** el significado convertido en verbo no pasa.
- **Cobertura:** lo impreciso no se castiga otra vez en la cobertura.

Los casos van en la pantalla, en `docs/rubrica-revision.md`, en el apéndice del paquete y en el
archivo que se exporta. **El criterio sigue siendo `calidad-v1`:** no cambia qué se mide, solo deja
escrito cómo se decidió.

## Justificación

- **Velocidad sin perder lo ciego.** El archivo lleva lo mismo que la pantalla y nada más. Los ids
  opacos y la huella evitan que una respuesta caiga en la salida equivocada.
- **No se mezclan sin decirlo.** Un juicio de IA y uno humano no valen lo mismo para la tesis. Por eso
  el origen queda en cada marca, el resumen y el paquete lo dicen, y el acuerdo con las marcas
  humanas se mide en la misma importación.
- **El acuerdo sale gratis.** Si una parte se revisa a mano y el resto lo contesta una IA sin pisar
  lo humano, la kappa de cada criterio dice si la IA aplica la rúbrica igual. Si la kappa es baja,
  esas marcas no se pueden reportar como si fueran humanas.

## Alternativas consideradas

- **Que el sistema llame a la IA directamente.** Se descarta por ahora. Sería otro LLM dentro del
  aparato de evaluación, con su prompt y su configuración por versionar, y la revisión dejaría de
  ser algo que una persona puede hacer igual con el mismo archivo. El archivo funciona igual para
  una persona y para cualquier IA.
- **Una revisión separada por cada revisor.** Sería lo más limpio para el acuerdo entre varias
  personas, pero cambia de qué revisión salen las métricas y el paquete. Por ahora la revisión es
  una sola, con el origen de cada marca, y las respuestas que no se aplicaron quedan guardadas en la
  importación.
- **Un formato propio de texto en lugar de JSON.** Se descarta: las IA devuelven JSON con
  confiabilidad, una persona lo llena en cualquier editor, y la validación es estricta.

## Consecuencias

- Una prueba puede tener marcas de tres orígenes. Si se cita la calidad, hay que decir cuántas marcas
  puso una IA y con qué acuerdo respecto a las humanas.
- Un archivo exportado deja de servir si la prueba gana salidas antes de que se cree la revisión (por
  ejemplo, al reintentar errores). Hay que exportarlo de nuevo.
- La versión del sistema pasa a **2.5.0**.
