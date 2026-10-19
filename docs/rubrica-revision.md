# Rúbrica de revisión

Generada desde `backend/app/calibracion/rubrica.py` (ADR 0029). No la edites a mano: cambia ese archivo.

## 1. Calidad de una salida del Clasificador

La revisión juzga solo la factura de lo que el modelo escribió. Si detectó o no la ambigüedad ya se mide contra el banco y no se revisa aquí. La revisión es a ciegas: no se ve qué modelo produjo la salida.

Cada criterio se marca una vez por salida (un término de un modelo). Se cumple si lo cumplen todas las intenciones de esa salida: basta una intención que falle para no marcarlo.

### Fidelidad (tecla 1)

La paráfrasis dice lo que decía la cita original con ese sentido del término, sin agregar ni quitar información (actores, condiciones, cantidades o momentos).

- **Pasa:** Cita «Cada consulta tiene que quedar registrada…»; paráfrasis «Cada atención del médico al paciente tiene que quedar registrada…»: cambia solo el término.
- **No pasa:** Paráfrasis «Cada consulta tiene que quedar registrada por la recepcionista en el expediente digital…»: agrega quién registra y dónde, que la cita no dice.

### Delimitación (tecla 2)

El significado está acotado a un sentido y no es circular: no usa el propio término (ni una forma suya) para definirse.

- **Pasa:** «corte»: «arqueo del dinero cobrado en el turno».
- **No pasa:** «corte»: «el corte que se hace al final del turno» (circular) o «algo del cierre» (vago).

### Intención (tecla 3)

La intención dice para qué usa el término quien habla (qué quiere lograr), no vuelve a decir qué significa.

- **Pasa:** «consulta»: «llevar el registro de las atenciones a cada paciente».
- **No pasa:** «consulta»: «la cita médica con el paciente» (repite el significado en lugar del propósito).

### Cobertura de lecturas esperadas (teclas 4, 5, 6)

Solo en los términos ambiguos: de las lecturas esperadas que registra el banco, marca las que aparecen en alguna intención de la salida. La cobertura es cubiertas sobre esperadas.

- **Pasa:** «caja» (supermercado), lecturas «punto de cobro», «dinero o fondo», «empaque»: la salida da «el lugar donde se cobra» y «el dinero de la caja» → se marcan las dos primeras (2 de 3).
- **No pasa:** Que la salida mencione «cobro» de pasada no cubre «el dinero o fondo de caja» si ninguna intención le da ese sentido. El cotejo es contra la lectura escrita en el banco, no contra palabras sueltas.

### Casos frecuentes

- **Fidelidad.** Si la paráfrasis deja el término (o una forma suya) o copia la cita tal cual, no pasa: no dice qué sentido eligió. Cambiarlo por un sinónimo sí cuenta.
- **Fidelidad.** No juzga si el sentido es el correcto ni si es el más probable en la cita: solo si la paráfrasis dice lo mismo que la cita con ese sentido.
- **Delimitación.** Una «o» que junta dos sentidos distintos no pasa («mantenimiento preventivo o correctivo»); una «o» que enumera quién o qué ocupa el mismo papel sí pasa («persona o empresa que surte mercancía»).
- **Delimitación.** Un significado tan general que pierde lo que distingue al término no pasa («pago realizado por el cliente» para «abono», que es un pago parcial).
- **Delimitación.** Desarrollar unas siglas no es definir: «CURP: Clave Única de Registro de Población» es circular.
- **Delimitación.** No cuenta cuántos sentidos dio el modelo: uno solo, bien acotado, pasa.
- **Intención.** El significado convertido en verbo no pasa («registrar el historial» para «documento que registra el historial»); tampoco una intención que no va con la cita.
- **Cobertura.** Lo impreciso de un significado se castiga en la delimitación y no otra vez aquí: si el sentido es el de la lectura esperada, se marca.

Teclas: `Enter` guarda y avanza, `Backspace` regresa, `?` abre esta rúbrica.

## 2. Ambigüedad de un término de entrevista

¿Este término, en las citas de esta entrevista y en este dominio, admite más de una lectura razonable para alguien que no estuvo en la entrevista?

- **Sí (S):** «consultas» en una clínica que también lleva un sistema de búsquedas: cita médica o búsqueda.
- **No (N):** «paciente» en la misma clínica: la persona que recibe atención; no hay otra lectura en ese dominio.
- **No sé (X):** Cuando las citas no alcanzan para decidir: queda fuera del ground truth y se cuenta aparte. No se adivina.

Se etiqueta a ciegas: sin ver la similitud ni la decisión del sistema, y en un orden barajado.

## 3. Modos de falla de los falsos negativos

Para cada término ambiguo que un modelo marcó como unívoco (o que falló), el modo que mejor lo explica:

- **Documento contra el hecho que registra** (`documento_hecho`): El modelo da solo el documento o solo el hecho que el documento registra: factura contra venta, acta contra reunión, nómina contra el proceso de pago.
- **Solo el sentido dominante** (`sentido_dominante`): Da únicamente el sentido más común en el español general y no ve el del oficio.
- **Regionalismo no reconocido** (`regionalismo`): No reconoce el uso del español de trabajo en México (o de otra región) que abre la segunda lectura.
- **El contexto lo cierra de más** (`contexto_cierra`): Usa el dominio del proyecto para descartar una lectura que en la cita sí cabe.
- **Falla de formato** (`formato`): No dio una salida válida (por ejemplo, un significado más largo que el máximo de palabras) y cuenta como no detectado.
- **Otro** (`otro`): Ninguno de los anteriores; conviene escribir una nota.
