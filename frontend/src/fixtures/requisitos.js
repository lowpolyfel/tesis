/*
 * Material de prueba: lo que cada agente "produjo" para cada requisito.
 * La traza que ve la UI (decisión, rondas efectivas, resolución) se arma a
 * partir de este material y de la configuración vigente (umbral, máximo de
 * rondas), igual que lo haría el backend. Así, al calibrar, los requisitos
 * reprocesados cambian de camino.
 *
 * Casos clave:
 *   REQ-001  pasa directo sin debate (similitud 0.91)
 *   REQ-002  se resuelve por consenso en la primera ronda
 *   REQ-003  agota las rondas y termina en arbitraje del Crítico
 *
 * `humano`: eventos posteriores al proceso (validación, rechazo, formalización).
 * `enProcesoHaceSeg`: el requisito sigue procesándose al abrir la app (demo del sondeo).
 * Los que solo traen `texto` se completan con el generador de material simulado.
 */

const BigPicture = (requisito, extra) => ({ requisito, ...extra });

export const requisitosSemilla = [
  /* ------------------------------------------------------------------ */
  {
    id: "REQ-001",
    texto: "El sistema debe permitir al administrador exportar el reporte mensual en PDF.",
    origen: "entrevista_area_admin.txt",
    creadoEn: "2026-09-28T09:12:00",
    extraccion: {
      duracionMs: 2840,
      terminos: [
        { texto: "sistema", categoria: "sujeto", lema: "sistema" },
        { texto: "administrador", categoria: "sujeto", lema: "administrador" },
        { texto: "exportar", categoria: "verbo", lema: "exportar" },
        { texto: "reporte mensual", categoria: "objeto", lema: "reporte mensual" },
        { texto: "PDF", categoria: "restriccion", lema: "pdf" },
      ],
      marcados: [],
    },
    clasificacion: {
      duracionMs: 3610,
      enDisputa: [],
      interpretaciones: {
        A: {
          texto: "El administrador puede generar el reporte del mes y descargarlo como archivo PDF.",
          lecturas: [{ termino: "exportar", significado: "generar y descargar un archivo" }],
        },
        B: {
          texto: "El administrador puede exportar a un archivo PDF el reporte con los datos del mes en curso.",
          lecturas: [{ termino: "exportar", significado: "guardar en un archivo con otro formato" }],
        },
      },
    },
    similitudInicial: 0.91,
    consenso: {
      interpretacion: "El administrador puede generar el reporte mensual y descargarlo como archivo PDF.",
    },
    artefactos: {
      lel: {
        simbolo: "reporte mensual",
        tipo: "objeto",
        sinonimos: ["reporte del mes"],
        nocion: [
          "Documento con el resumen de operaciones de un mes calendario.",
          "Se genera bajo demanda y se descarga en formato PDF.",
        ],
        impacto: [
          "El administrador lo exporta para entregarlo a dirección.",
          "Se genera a partir de las operaciones registradas en el mes.",
        ],
      },
      metas: {
        metaEstrategica: "Facilitar la rendición de cuentas mensual del área administrativa",
        submetas: [
          { id: "M1", descripcion: "Generar el reporte mensual bajo demanda", tipo: "dura" },
          { id: "M2", descripcion: "Descargar el reporte en formato PDF", tipo: "dura" },
          { id: "M3", descripcion: "Presentar la información de forma legible para dirección", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-001", {
        actores: ["administrador"],
        acciones: [{ actor: "administrador", verbo: "exportar", objeto: "reporte mensual", formato: "PDF" }],
        restricciones: ["formato PDF"],
        terminosResueltos: [],
      }),
    },
    humano: [
      { estado: "validado", minutosDespues: 42, editado: false, comentario: "" },
      { estado: "formalizado", minutosDespues: 43 },
    ],
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-002",
    texto: "El sistema debe registrar la sesión del usuario.",
    origen: "entrevista_area_admin.txt",
    creadoEn: "2026-09-28T09:14:00",
    extraccion: {
      duracionMs: 2510,
      terminos: [
        { texto: "sistema", categoria: "sujeto", lema: "sistema" },
        { texto: "registrar", categoria: "verbo", lema: "registrar" },
        { texto: "sesión", categoria: "objeto", lema: "sesión" },
        { texto: "usuario", categoria: "sujeto", lema: "usuario" },
      ],
      marcados: [
        { texto: "registrar", tipo: "polisemia", fuente: "Clasificador" },
        { texto: "sesión", tipo: "polisemia", fuente: "Clasificador" },
      ],
    },
    clasificacion: {
      duracionMs: 4120,
      enDisputa: ["registrar", "sesión"],
      interpretaciones: {
        A: {
          texto: "Guardar en una bitácora cada inicio y cierre de sesión del usuario (fecha, hora, IP) con fines de auditoría.",
          lecturas: [
            { termino: "registrar", significado: "dejar constancia en una bitácora" },
            { termino: "sesión", significado: "periodo en que el usuario está autenticado" },
          ],
        },
        B: {
          texto: "Dar de alta (crear) la sesión de trabajo del usuario al autenticarse, para mantenerlo conectado.",
          lecturas: [
            { termino: "registrar", significado: "dar de alta, crear" },
            { termino: "sesión", significado: "sesión técnica (token) que mantiene al usuario conectado" },
          ],
        },
      },
    },
    similitudInicial: 0.58,
    rondas: [
      {
        intervenciones: [
          {
            postura: "A",
            argumento:
              "En sistemas administrativos «registrar» suele significar «dejar constancia» (registro de asistencia, registro de entradas). El objeto es una sesión que ya existe; el requisito no habla de crearla.",
          },
          {
            postura: "B",
            argumento:
              "Crear la sesión es condición previa: sin ella no hay nada que registrar. Concedo, sin embargo, que el requisito no menciona la autenticación, que sería el contexto natural de «crear».",
          },
          {
            postura: "moderador",
            argumento:
              "Ambas lecturas coinciden en que la sesión es el periodo autenticado. Difieren en si el sistema la crea o deja constancia de ella. B reconoce que la creación pertenece al requisito de autenticación; se pide a B reformular.",
          },
        ],
        ajustes: {
          B: "Dejar constancia del inicio y cierre de la sesión del usuario; la creación de la sesión corresponde al requisito de autenticación.",
        },
        similitudCierre: 0.84,
      },
      {
        intervenciones: [
          { postura: "A", argumento: "Sostengo la lectura de bitácora y propongo incluir fecha, hora e IP." },
          { postura: "B", argumento: "De acuerdo; añado que el cierre por inactividad también debe quedar registrado." },
          { postura: "moderador", argumento: "Lecturas prácticamente equivalentes." },
        ],
        similitudCierre: 0.9,
      },
    ],
    consenso: {
      interpretacion:
        "El sistema debe guardar en una bitácora el inicio y el cierre de cada sesión del usuario (fecha, hora y dirección IP). La creación de la sesión se trata en el requisito de autenticación.",
    },
    arbitraje: {
      eleccion: "A",
      interpretacion:
        "El sistema debe guardar en una bitácora el inicio y el cierre de cada sesión del usuario (fecha, hora y dirección IP).",
      criterios: [
        { criterio: "Separación de responsabilidades", aplicacion: "Crear la sesión pertenece al requisito de autenticación.", favorece: "A" },
        { criterio: "Uso del verbo en el dominio", aplicacion: "«Registrar» en el área administrativa significa dejar constancia.", favorece: "A" },
      ],
      justificacion: "La lectura A no duplica responsabilidades con otros requisitos.",
    },
    artefactos: {
      lel: {
        simbolo: "registrar sesión",
        tipo: "verbo",
        sinonimos: ["registrar acceso", "bitácora de sesión"],
        nocion: [
          "Dejar constancia en la bitácora del inicio y el cierre de una sesión de usuario.",
          "La constancia incluye fecha, hora y dirección IP.",
        ],
        impacto: [
          "Se crea una entrada en la bitácora de accesos.",
          "El administrador puede consultar la bitácora para auditoría.",
        ],
      },
      metas: {
        metaEstrategica: "Garantizar la trazabilidad de los accesos al sistema",
        submetas: [
          { id: "M1", descripcion: "Registrar el inicio de sesión", tipo: "dura" },
          { id: "M2", descripcion: "Registrar el cierre de sesión", tipo: "dura" },
          { id: "M3", descripcion: "Permitir al administrador consultar la bitácora", tipo: "dura" },
          { id: "M4", descripcion: "Conservar la bitácora el tiempo suficiente para auditoría", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-002", {
        actores: ["usuario", "administrador"],
        acciones: [
          { actor: "sistema", verbo: "registrar", objeto: "inicio de sesión", datos: ["fecha", "hora", "ip"] },
          { actor: "sistema", verbo: "registrar", objeto: "cierre de sesión", datos: ["fecha", "hora", "ip"] },
        ],
        restricciones: [],
        terminosResueltos: [
          { termino: "registrar", significado: "dejar constancia en bitácora" },
          { termino: "sesión", significado: "periodo autenticado del usuario" },
        ],
        dependencias: ["requisito de autenticación"],
      }),
    },
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-003",
    texto: "El sistema debe jalar los datos del servidor de manera rápida.",
    origen: "entrevista_area_operativa.txt",
    creadoEn: "2026-09-28T09:20:00",
    extraccion: {
      duracionMs: 3020,
      terminos: [
        { texto: "sistema", categoria: "sujeto", lema: "sistema" },
        { texto: "jalar", categoria: "verbo", lema: "jalar" },
        { texto: "datos", categoria: "objeto", lema: "dato" },
        { texto: "servidor", categoria: "objeto", lema: "servidor" },
        { texto: "rápida", categoria: "restriccion", lema: "rápido" },
      ],
      marcados: [
        { texto: "jalar", tipo: "mexicanismo", fuente: "Catálogo de mexicanismos (mx-01)" },
        { texto: "rápida", tipo: "vaguedad", fuente: "Catálogo de vaguedad (vg-02)" },
      ],
    },
    clasificacion: {
      duracionMs: 4870,
      enDisputa: ["jalar", "rápida"],
      interpretaciones: {
        A: {
          texto: "Descargar los datos del servidor central al dispositivo con un tiempo de respuesta máximo definido por consulta.",
          lecturas: [
            { termino: "jalar", significado: "traer / descargar datos" },
            { termino: "rápida", significado: "tiempo de respuesta técnico acotado (p. ej., ≤ 2 s)" },
          ],
        },
        B: {
          texto: "Que la consulta de datos al servidor funcione («jale») sin errores y tarde menos que el proceso manual actual.",
          lecturas: [
            { termino: "jalar", significado: "funcionar correctamente" },
            { termino: "rápida", significado: "más rápido que el proceso manual" },
          ],
        },
      },
    },
    similitudInicial: 0.41,
    rondas: [
      {
        intervenciones: [
          {
            postura: "A",
            argumento:
              "En «jalar los datos del servidor», el complemento directo («los datos») y el origen («del servidor») indican movimiento de información: traer. La lectura «funcionar» exigiría que el sujeto sea lo que funciona («el sistema jala»), no que tenga un objeto.",
          },
          {
            postura: "B",
            argumento:
              "En el habla del área operativa «que jale» se usa para quejarse de que algo no funciona. El requisito viene de una entrevista en la que se pidió que la consulta dejara de fallar; la intención es confiabilidad.",
          },
          {
            postura: "moderador",
            argumento:
              "La sintaxis favorece «traer», pero B aporta evidencia del origen del requisito. «Rápida» sigue sin métrica en ambas lecturas.",
          },
        ],
        similitudCierre: 0.52,
      },
      {
        intervenciones: [
          {
            postura: "A",
            argumento:
              "Aun aceptando el origen coloquial, la construcción transitiva «jalar X de Y» corresponde en el catálogo regional a la lectura «traer/descargar» (mx-01). Propongo fijar «rápida» como ≤ 2 s por consulta.",
          },
          {
            postura: "B",
            argumento:
              "Acepto que el verbo describe obtener datos, pero la necesidad real es que no falle, y «rápida» debe medirse contra el proceso actual (≈ 5 min), no contra un umbral técnico.",
          },
          {
            postura: "moderador",
            argumento:
              "Hay acercamiento en el verbo; persiste el desacuerdo en la métrica de «rápida»: técnica (≤ 2 s) contra comparativa (más rápido que lo manual).",
          },
        ],
        ajustes: {
          B: "Obtener los datos del servidor sin errores y en menos tiempo que el proceso manual actual (≈ 5 min).",
        },
        similitudCierre: 0.63,
      },
      {
        intervenciones: [
          { postura: "A", argumento: "Mantengo ≤ 2 s: es verificable sin una línea base externa." },
          { postura: "B", argumento: "Mantengo la comparación con el proceso actual; es lo que el interesado pidió." },
          { postura: "moderador", argumento: "Sin cambios sustantivos respecto a la ronda anterior." },
        ],
        similitudCierre: 0.66,
      },
    ],
    consenso: {
      interpretacion: "El sistema debe obtener los datos del servidor en un tiempo máximo de 2 segundos por consulta.",
    },
    arbitraje: {
      eleccion: "A",
      interpretacion:
        "El sistema debe obtener (descargar) los datos del servidor central en un tiempo máximo de 2 segundos por consulta.",
      criterios: [
        {
          criterio: "Evidencia sintáctica",
          aplicacion: "«Jalar» lleva complemento directo («los datos») y origen («del servidor»): verbo de movimiento de información.",
          favorece: "A",
        },
        {
          criterio: "Catálogo regional",
          aplicacion: "La entrada mx-01 registra «traer / descargar datos» como primera lectura de «jalar» en contexto transitivo.",
          favorece: "A",
        },
        {
          criterio: "Verificabilidad",
          aplicacion: "«≤ 2 s por consulta» puede probarse; «más rápido que lo manual» depende de una línea base no documentada.",
          favorece: "A",
        },
        {
          criterio: "Intención del interesado",
          aplicacion: "El origen coloquial sugiere preocupación por fallas; se conserva como requisito derivado de confiabilidad.",
          favorece: "B",
        },
      ],
      justificacion:
        "Tres de cuatro criterios favorecen la lectura A. La preocupación de B por la confiabilidad no se descarta: se registra como requisito derivado para no perder la intención del interesado.",
    },
    artefactos: {
      lel: {
        simbolo: "jalar datos",
        tipo: "verbo",
        sinonimos: ["obtener datos", "descargar datos"],
        nocion: [
          "Obtener (descargar) datos desde el servidor central hacia el sistema cliente.",
          "Regionalismo: en el área operativa también se usa «jalar» por «funcionar».",
        ],
        impacto: [
          "Cada consulta debe responder en un máximo de 2 segundos.",
          "Si la consulta falla, el sistema notifica al usuario (requisito derivado de confiabilidad).",
        ],
      },
      metas: {
        metaEstrategica: "Disponer de la información del servidor de forma oportuna",
        submetas: [
          { id: "M1", descripcion: "Obtener los datos del servidor en ≤ 2 s por consulta", tipo: "dura" },
          { id: "M2", descripcion: "Notificar al usuario cuando la consulta falle", tipo: "dura" },
          { id: "M3", descripcion: "Mantener la consulta confiable en la operación diaria", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-003", {
        actores: ["usuario operativo"],
        acciones: [{ actor: "sistema", verbo: "obtener", objeto: "datos", origen: "servidor central" }],
        restricciones: [{ tipo: "desempeño", metrica: "tiempo de respuesta", maximo: "2 s" }],
        terminosResueltos: [
          { termino: "jalar", significado: "obtener / descargar datos", via: "arbitraje" },
          { termino: "rápida", significado: "≤ 2 s por consulta", via: "arbitraje" },
        ],
        requisitosDerivados: ["Notificar al usuario cuando la consulta al servidor falle"],
      }),
    },
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-004",
    texto: "El usuario podrá checar el estatus de su pedido en todo momento.",
    origen: "entrevista_clientes.txt",
    creadoEn: "2026-09-28T09:31:00",
    extraccion: {
      duracionMs: 2700,
      terminos: [
        { texto: "usuario", categoria: "sujeto", lema: "usuario" },
        { texto: "checar", categoria: "verbo", lema: "checar" },
        { texto: "estatus", categoria: "estado", lema: "estatus" },
        { texto: "pedido", categoria: "objeto", lema: "pedido" },
        { texto: "en todo momento", categoria: "restriccion", lema: "en todo momento" },
      ],
      marcados: [
        { texto: "checar", tipo: "mexicanismo", fuente: "Catálogo de mexicanismos (mx-02)" },
        { texto: "en todo momento", tipo: "vaguedad", fuente: "Catálogo de vaguedad (vg-04)" },
      ],
    },
    clasificacion: {
      duracionMs: 3980,
      enDisputa: ["checar", "en todo momento"],
      interpretaciones: {
        A: {
          texto: "El usuario puede consultar el estado de su pedido a cualquier hora (disponibilidad 24/7).",
          lecturas: [
            { termino: "checar", significado: "consultar" },
            { termino: "en todo momento", significado: "24/7" },
          ],
        },
        B: {
          texto: "El usuario puede verificar que su pedido cumpla las condiciones acordadas durante el horario de servicio.",
          lecturas: [
            { termino: "checar", significado: "verificar contra una regla" },
            { termino: "en todo momento", significado: "durante el horario de servicio" },
          ],
        },
      },
    },
    similitudInicial: 0.62,
    rondas: [
      {
        intervenciones: [
          { postura: "A", argumento: "«Checar el estatus» es consulta: el objeto es un estado, no una condición a verificar." },
          { postura: "B", argumento: "Acepto «consultar»; sobre «en todo momento», el portal de clientes ya opera 24/7, así que no hay conflicto." },
          { postura: "moderador", argumento: "Convergencia en ambos términos." },
        ],
        similitudCierre: 0.88,
      },
    ],
    consenso: { interpretacion: "El usuario puede consultar el estado de su pedido en cualquier momento (24/7) desde el portal." },
    artefactos: {
      lel: {
        simbolo: "estatus del pedido",
        tipo: "estado",
        sinonimos: ["estado del pedido"],
        nocion: ["Etapa en la que se encuentra un pedido: recibido, en preparación, enviado o entregado."],
        impacto: ["El usuario lo consulta desde el portal en cualquier momento."],
      },
      metas: {
        metaEstrategica: "Dar visibilidad al cliente sobre sus pedidos",
        submetas: [
          { id: "M1", descripcion: "Consultar el estado del pedido", tipo: "dura" },
          { id: "M2", descripcion: "Mantener el portal disponible 24/7", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-004", {
        actores: ["usuario"],
        acciones: [{ actor: "usuario", verbo: "consultar", objeto: "estatus del pedido" }],
        restricciones: [{ tipo: "disponibilidad", valor: "24/7" }],
        terminosResueltos: [
          { termino: "checar", significado: "consultar" },
          { termino: "en todo momento", significado: "24/7" },
        ],
      }),
    },
    humano: [
      { estado: "validado", minutosDespues: 55, editado: true, comentario: "Se agregó la lista de etapas a la noción." },
      { estado: "formalizado", minutosDespues: 56 },
    ],
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-006",
    texto: "La aplicación debe cargar la información del alumno al inicio.",
    origen: "requisitos_control_escolar.pdf",
    creadoEn: "2026-09-28T10:02:00",
    extraccion: {
      duracionMs: 2650,
      terminos: [
        { texto: "aplicación", categoria: "sujeto", lema: "aplicación" },
        { texto: "cargar", categoria: "verbo", lema: "cargar" },
        { texto: "información del alumno", categoria: "objeto", lema: "información del alumno" },
        { texto: "al inicio", categoria: "restriccion", lema: "al inicio" },
      ],
      marcados: [
        { texto: "cargar", tipo: "mexicanismo", fuente: "Catálogo de mexicanismos (mx-08)" },
        { texto: "al inicio", tipo: "vaguedad", fuente: "Clasificador" },
      ],
    },
    clasificacion: {
      duracionMs: 4300,
      enDisputa: ["cargar", "al inicio"],
      interpretaciones: {
        A: {
          texto: "La aplicación debe subir (importar) la información del alumno al iniciar el ciclo escolar.",
          lecturas: [
            { termino: "cargar", significado: "subir / importar" },
            { termino: "al inicio", significado: "inicio del ciclo escolar" },
          ],
        },
        B: {
          texto: "La aplicación debe mostrar el expediente del alumno en la pantalla de inicio.",
          lecturas: [
            { termino: "cargar", significado: "mostrar / desplegar" },
            { termino: "al inicio", significado: "pantalla de inicio" },
          ],
        },
      },
    },
    similitudInicial: 0.37,
    rondas: [
      {
        intervenciones: [
          { postura: "A", argumento: "Control escolar suele «cargar» alumnos por lotes al iniciar el ciclo." },
          { postura: "B", argumento: "«La aplicación» es la interfaz; una interfaz carga lo que muestra." },
          { postura: "moderador", argumento: "Ambos argumentos dependen de contexto que el requisito no da." },
        ],
        similitudCierre: 0.44,
      },
      {
        intervenciones: [
          { postura: "A", argumento: "El documento de origen es de control escolar, no de la app de alumnos." },
          { postura: "B", argumento: "El documento incluye pantallas de la app; el requisito está en esa sección." },
          { postura: "moderador", argumento: "Sin convergencia." },
        ],
        similitudCierre: 0.47,
      },
    ],
    arbitraje: {
      eleccion: "A",
      interpretacion: "La aplicación debe importar la información de los alumnos al iniciar el ciclo escolar.",
      criterios: [
        { criterio: "Origen del documento", aplicacion: "El documento pertenece a control escolar.", favorece: "A" },
        { criterio: "Catálogo regional", aplicacion: "mx-08 lista «subir información» como primera lectura.", favorece: "A" },
        { criterio: "Ubicación en el documento", aplicacion: "El requisito aparece en la sección de pantallas.", favorece: "B" },
      ],
      justificacion: "Dos de tres criterios favorecen A.",
    },
    artefactos: {
      lel: {
        simbolo: "cargar información del alumno",
        tipo: "verbo",
        sinonimos: ["importar alumnos"],
        nocion: ["Importar los datos de los alumnos al sistema al iniciar el ciclo escolar."],
        impacto: ["Los alumnos quedan disponibles para inscripción."],
      },
      metas: {
        metaEstrategica: "Tener los datos de alumnos al día al iniciar el ciclo",
        submetas: [{ id: "M1", descripcion: "Importar alumnos por lote", tipo: "dura" }],
      },
      bigPicture: BigPicture("REQ-006", {
        actores: ["control escolar"],
        acciones: [{ actor: "aplicación", verbo: "importar", objeto: "información del alumno" }],
        restricciones: [],
        terminosResueltos: [{ termino: "cargar", significado: "importar", via: "arbitraje" }],
      }),
    },
    humano: [
      {
        estado: "rechazado",
        minutosDespues: 70,
        comentario: "El árbitro eligió mal: el requisito está en la sección de pantallas y se refiere a mostrar el expediente. Reprocesar con más contexto.",
      },
    ],
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-007",
    texto: "El sistema debe mostrar los pendientes del supervisor de forma amigable.",
    origen: "entrevista_supervisores.txt",
    creadoEn: "2026-09-29T11:40:00",
    enProcesoHaceSeg: 11,
    extraccion: {
      duracionMs: 2900,
      terminos: [
        { texto: "sistema", categoria: "sujeto", lema: "sistema" },
        { texto: "mostrar", categoria: "verbo", lema: "mostrar" },
        { texto: "pendientes", categoria: "objeto", lema: "pendiente" },
        { texto: "supervisor", categoria: "sujeto", lema: "supervisor" },
        { texto: "amigable", categoria: "restriccion", lema: "amigable" },
      ],
      marcados: [
        { texto: "pendientes", tipo: "mexicanismo", fuente: "Catálogo de mexicanismos (mx-05)" },
        { texto: "amigable", tipo: "vaguedad", fuente: "Catálogo de vaguedad (vg-03)" },
      ],
    },
    clasificacion: {
      duracionMs: 4100,
      enDisputa: ["pendientes", "amigable"],
      interpretaciones: {
        A: {
          texto: "Mostrar al supervisor la lista de tareas por realizar, ordenada por prioridad.",
          lecturas: [
            { termino: "pendientes", significado: "tareas por realizar" },
            { termino: "amigable", significado: "ordenada y legible" },
          ],
        },
        B: {
          texto: "Mostrar al supervisor los adeudos de su equipo con una interfaz agradable.",
          lecturas: [
            { termino: "pendientes", significado: "adeudos / cuentas por pagar" },
            { termino: "amigable", significado: "agradable a juicio del usuario" },
          ],
        },
      },
    },
    similitudInicial: 0.47,
    rondas: [
      {
        intervenciones: [
          { postura: "A", argumento: "Un supervisor coordina trabajo; sus «pendientes» son tareas del equipo." },
          { postura: "B", argumento: "En el área de cobranza los supervisores dan seguimiento a adeudos." },
          { postura: "moderador", argumento: "El origen (entrevista a supervisores generales) no menciona cobranza." },
        ],
        similitudCierre: 0.79,
      },
    ],
    consenso: { interpretacion: "El sistema debe mostrar al supervisor la lista de tareas por realizar de su equipo, ordenada por prioridad." },
    artefactos: {
      lel: {
        simbolo: "pendientes del supervisor",
        tipo: "objeto",
        sinonimos: ["tareas pendientes"],
        nocion: ["Tareas asignadas al equipo del supervisor que aún no se completan."],
        impacto: ["El supervisor las prioriza y reasigna."],
      },
      metas: {
        metaEstrategica: "Que el supervisor conozca el trabajo pendiente de su equipo",
        submetas: [
          { id: "M1", descripcion: "Listar tareas pendientes", tipo: "dura" },
          { id: "M2", descripcion: "Ordenarlas por prioridad", tipo: "dura" },
          { id: "M3", descripcion: "Presentarlas de forma clara", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-007", {
        actores: ["supervisor"],
        acciones: [{ actor: "sistema", verbo: "mostrar", objeto: "tareas pendientes", orden: "prioridad" }],
        restricciones: [],
        terminosResueltos: [{ termino: "pendientes", significado: "tareas por realizar" }],
      }),
    },
  },

  /* ------------------------------------------------------------------ */
  {
    id: "REQ-010",
    texto: "El vendedor debe poder aplicar un descuento a la nota.",
    origen: "entrevista_ventas.txt",
    creadoEn: "2026-09-29T10:05:00",
    extraccion: {
      duracionMs: 2400,
      terminos: [
        { texto: "vendedor", categoria: "sujeto", lema: "vendedor" },
        { texto: "aplicar", categoria: "verbo", lema: "aplicar" },
        { texto: "descuento", categoria: "objeto", lema: "descuento" },
        { texto: "nota", categoria: "objeto", lema: "nota" },
      ],
      marcados: [{ texto: "nota", tipo: "mexicanismo", fuente: "Catálogo de mexicanismos (mx-03)" }],
    },
    clasificacion: {
      duracionMs: 3500,
      enDisputa: ["nota"],
      interpretaciones: {
        A: {
          texto: "El vendedor puede aplicar un descuento al comprobante de venta (ticket o remisión).",
          lecturas: [{ termino: "nota", significado: "comprobante de venta" }],
        },
        B: {
          texto: "El vendedor puede anotar un descuento en una nota interna del pedido.",
          lecturas: [{ termino: "nota", significado: "anotación libre" }],
        },
      },
    },
    similitudInicial: 0.55,
    rondas: [
      {
        intervenciones: [
          { postura: "A", argumento: "«Aplicar un descuento» modifica un importe; solo un comprobante de venta tiene importe." },
          { postura: "B", argumento: "Concedo: una anotación no se «aplica»." },
          { postura: "moderador", argumento: "Convergencia hacia «comprobante de venta»." },
        ],
        similitudCierre: 0.86,
      },
    ],
    consenso: { interpretacion: "El vendedor puede aplicar un descuento al importe del comprobante de venta (nota de venta)." },
    artefactos: {
      lel: {
        simbolo: "nota",
        tipo: "objeto",
        sinonimos: ["nota de venta", "comprobante de venta", "remisión"],
        nocion: ["Comprobante que detalla los productos e importes de una venta."],
        impacto: ["El vendedor puede aplicarle descuentos antes de cerrarla."],
      },
      metas: {
        metaEstrategica: "Dar flexibilidad comercial al vendedor",
        submetas: [
          { id: "M1", descripcion: "Aplicar descuento al comprobante", tipo: "dura" },
          { id: "M2", descripcion: "Limitar el descuento máximo permitido", tipo: "blanda" },
        ],
      },
      bigPicture: BigPicture("REQ-010", {
        actores: ["vendedor"],
        acciones: [{ actor: "vendedor", verbo: "aplicar", objeto: "descuento", destino: "nota de venta" }],
        restricciones: [],
        terminosResueltos: [{ termino: "nota", significado: "comprobante de venta" }],
      }),
    },
  },

  /* ---------------- Completados con el generador simulado ------------ */
  {
    id: "REQ-005",
    texto: "El sistema debe enviar un correo al cliente cuando su trámite esté listo.",
    origen: "entrevista_clientes.txt",
    creadoEn: "2026-09-28T09:33:00",
    humano: [{ estado: "validado", minutosDespues: 60, editado: false, comentario: "" }],
  },
  {
    id: "REQ-008",
    texto: "El administrador podrá dar de baja a los usuarios inactivos.",
    origen: "entrevista_area_admin.txt",
    creadoEn: "2026-09-29T11:41:00",
    enProcesoHaceSeg: 4,
  },
  {
    id: "REQ-009",
    texto: "El sistema debe respaldar la base de datos todos los días a las 23:00 horas.",
    origen: "entrevista_area_admin.txt",
    creadoEn: "2026-09-29T11:42:00",
    enProcesoHaceSeg: 0,
  },
  {
    id: "REQ-011",
    texto: "El cajero debe poder cancelar una venta antes de cerrar el corte de caja.",
    origen: "entrevista_ventas.txt",
    creadoEn: "2026-09-28T10:20:00",
    humano: [
      { estado: "validado", minutosDespues: 30, editado: false, comentario: "" },
      { estado: "formalizado", minutosDespues: 31 },
    ],
  },
  {
    id: "REQ-012",
    texto: "El supervisor debe checar la asistencia del personal ahorita que llegue.",
    origen: "entrevista_supervisores.txt",
    creadoEn: "2026-09-28T10:25:00",
    humano: [
      { estado: "validado", minutosDespues: 35, editado: true, comentario: "Se precisó «ahorita» como «al momento de su llegada»." },
      { estado: "formalizado", minutosDespues: 36 },
    ],
  },
];
