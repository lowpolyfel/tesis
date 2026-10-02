/*
 * Corpus de prueba con ground truth (anotación humana, separada del sistema).
 *  - verdad.ambiguo / verdad.terminos: lo que la persona anotó
 *  - sistema.terminos: términos que el sistema marcó como ambiguos
 *  - sistema.similitud: similitud coseno entre interpretaciones candidatas
 * El debate se activa cuando sistema.similitud < umbral, así que los
 * resultados cambian al calibrar.
 */
export const corpus = [
  { id: "C-01", texto: "El sistema debe jalar los datos del servidor de manera rápida.", verdad: { ambiguo: true, terminos: ["jalar", "rápida"] }, sistema: { terminos: ["jalar", "rápida"], similitud: 0.41 } },
  { id: "C-02", texto: "El sistema debe registrar la sesión del usuario.", verdad: { ambiguo: true, terminos: ["registrar", "sesión"] }, sistema: { terminos: ["registrar", "sesión"], similitud: 0.58 } },
  { id: "C-03", texto: "El administrador debe exportar el reporte mensual en PDF.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: [], similitud: 0.91 } },
  { id: "C-04", texto: "El usuario podrá checar el estatus de su pedido en todo momento.", verdad: { ambiguo: true, terminos: ["checar", "en todo momento"] }, sistema: { terminos: ["checar", "en todo momento"], similitud: 0.62 } },
  { id: "C-05", texto: "El sistema debe enviar un correo al cliente cuando su trámite esté listo.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: ["trámite"], similitud: 0.79 } },
  { id: "C-06", texto: "La aplicación debe cargar la información del alumno al inicio.", verdad: { ambiguo: true, terminos: ["cargar", "al inicio"] }, sistema: { terminos: ["cargar"], similitud: 0.37 } },
  { id: "C-07", texto: "El sistema debe mostrar los pendientes del supervisor de forma amigable.", verdad: { ambiguo: true, terminos: ["pendientes", "amigable"] }, sistema: { terminos: ["pendientes", "amigable"], similitud: 0.47 } },
  { id: "C-08", texto: "El administrador podrá dar de baja a los usuarios inactivos.", verdad: { ambiguo: true, terminos: ["dar de baja", "inactivos"] }, sistema: { terminos: ["dar de baja", "inactivos"], similitud: 0.6 } },
  { id: "C-09", texto: "El sistema debe respaldar la base de datos todos los días a las 23:00 horas.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: [], similitud: 0.93 } },
  { id: "C-10", texto: "El vendedor debe poder aplicar un descuento a la nota.", verdad: { ambiguo: true, terminos: ["nota"] }, sistema: { terminos: ["nota"], similitud: 0.55 } },
  { id: "C-11", texto: "El cajero debe poder cancelar una venta antes de cerrar el corte de caja.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: [], similitud: 0.86 } },
  { id: "C-12", texto: "El supervisor debe checar la asistencia del personal ahorita que llegue.", verdad: { ambiguo: true, terminos: ["checar", "ahorita"] }, sistema: { terminos: ["checar", "ahorita"], similitud: 0.52 } },
  { id: "C-13", texto: "El sistema debe generar la factura con los datos fiscales del cliente.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: [], similitud: 0.74 } },
  { id: "C-14", texto: "La pantalla de captura debe ser intuitiva para el personal de ventanilla.", verdad: { ambiguo: true, terminos: ["intuitiva"] }, sistema: { terminos: [], similitud: 0.81 } },
  { id: "C-15", texto: "El sistema debe notificar al alumno su calificación final.", verdad: { ambiguo: false, terminos: [] }, sistema: { terminos: ["notificar"], similitud: 0.71 } },
  { id: "C-16", texto: "El portal debe responder de forma adecuada ante muchos usuarios.", verdad: { ambiguo: true, terminos: ["adecuada", "muchos"] }, sistema: { terminos: ["adecuada"], similitud: 0.49 } },
];
