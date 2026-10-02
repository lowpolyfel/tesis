/* Catálogos de términos regionales. Columnas: expresión, clasificación, lecturas, tratamiento. */
export const mexicanismos = [
  { id: "mx-01", expresion: "jalar", clasificacion: "Regionalismo léxico", lecturas: ["Traer / descargar datos", "Funcionar (\"ya jala\")", "Tirar de algo"], tratamiento: "Debatir; sustituir por «obtener» o «sincronizar» según contexto" },
  { id: "mx-02", expresion: "checar", clasificacion: "Regionalismo léxico", lecturas: ["Consultar / revisar", "Registrar asistencia", "Verificar contra una regla"], tratamiento: "Debatir; preferir «consultar» o «verificar»" },
  { id: "mx-03", expresion: "nota", clasificacion: "Polisemia regional", lecturas: ["Comprobante de venta (ticket, remisión)", "Anotación libre"], tratamiento: "Debatir; usar «comprobante de venta» si hay transacción" },
  { id: "mx-04", expresion: "ahorita", clasificacion: "Temporal coloquial", lecturas: ["Inmediatamente", "En un momento indeterminado"], tratamiento: "Preguntar al usuario; exigir plazo explícito" },
  { id: "mx-05", expresion: "pendientes", clasificacion: "Polisemia regional", lecturas: ["Tareas por realizar", "Adeudos o cuentas por pagar"], tratamiento: "Debatir" },
  { id: "mx-06", expresion: "dar de baja", clasificacion: "Coloquialismo administrativo", lecturas: ["Eliminar el registro", "Desactivar sin borrar"], tratamiento: "Debatir; precisar si es borrado lógico o físico" },
  { id: "mx-07", expresion: "estatus", clasificacion: "Anglicismo adaptado", lecturas: ["Estado del proceso"], tratamiento: "Aceptar; sinónimo de «estado»" },
  { id: "mx-08", expresion: "cargar", clasificacion: "Polisemia regional", lecturas: ["Subir información al sistema", "Mostrar / desplegar en pantalla", "Cobrar a una cuenta"], tratamiento: "Debatir" },
];

export const vaguedad = [
  { id: "vg-01", expresion: "rápido", clasificacion: "Adjetivo de desempeño", lecturas: ["Tiempo de respuesta < 1 s", "Más rápido que el proceso manual actual"], tratamiento: "Exigir métrica (tiempo máximo)" },
  { id: "vg-02", expresion: "rápida", clasificacion: "Adjetivo de desempeño", lecturas: ["Tiempo de respuesta < 1 s", "Más rápido que el proceso manual actual"], tratamiento: "Exigir métrica (tiempo máximo)" },
  { id: "vg-03", expresion: "amigable", clasificacion: "Adjetivo evaluativo", lecturas: ["Cumple una guía de usabilidad", "Agradable a juicio del usuario"], tratamiento: "Exigir criterio verificable" },
  { id: "vg-04", expresion: "en todo momento", clasificacion: "Cuantificador temporal impreciso", lecturas: ["Disponibilidad 24/7", "Durante el horario de servicio"], tratamiento: "Preguntar al usuario; fijar disponibilidad" },
  { id: "vg-05", expresion: "inactivos", clasificacion: "Estado sin criterio", lecturas: ["Sin iniciar sesión en N días", "Marcados manualmente como inactivos"], tratamiento: "Exigir regla de inactividad" },
  { id: "vg-06", expresion: "adecuado", clasificacion: "Adjetivo evaluativo", lecturas: ["Conforme a una norma", "Suficiente a juicio del evaluador"], tratamiento: "Exigir criterio verificable" },
  { id: "vg-07", expresion: "lo antes posible", clasificacion: "Temporal impreciso", lecturas: ["Inmediato", "Sin plazo definido"], tratamiento: "Exigir plazo" },
  { id: "vg-08", expresion: "intuitivo", clasificacion: "Adjetivo evaluativo", lecturas: ["Sin capacitación previa", "Similar a otra aplicación conocida"], tratamiento: "Exigir criterio verificable" },
];
