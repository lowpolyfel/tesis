/*
 * Entradas adicionales del LEL acumulado (símbolos secundarios que el
 * Modelador registró al formalizar). La entrada principal de cada requisito
 * formalizado se toma de sus artefactos validados.
 */
export const lelAdicional = [
  {
    id: "lel-adm",
    simbolo: "administrador",
    tipo: "sujeto",
    sinonimos: ["admin"],
    nocion: ["Persona del área administrativa con permisos para gestionar usuarios y reportes."],
    impacto: ["Exporta el reporte mensual.", "Consulta la bitácora de sesiones."],
    requisitoId: "REQ-001",
  },
  {
    id: "lel-ped",
    simbolo: "pedido",
    tipo: "objeto",
    sinonimos: ["orden"],
    nocion: ["Solicitud de compra hecha por un cliente."],
    impacto: ["Cambia de estatus conforme avanza su preparación y envío."],
    requisitoId: "REQ-004",
  },
  {
    id: "lel-usr",
    simbolo: "usuario",
    tipo: "sujeto",
    sinonimos: ["cliente"],
    nocion: ["Persona que usa el portal para dar seguimiento a sus pedidos."],
    impacto: ["Consulta el estatus de sus pedidos."],
    requisitoId: "REQ-004",
  },
  {
    id: "lel-cor",
    simbolo: "corte de caja",
    tipo: "objeto",
    sinonimos: ["cierre de caja"],
    nocion: ["Cuadre de las ventas e ingresos de una caja al final del turno."],
    impacto: ["Una vez cerrado, ya no se pueden cancelar ventas del turno."],
    requisitoId: "REQ-011",
  },
  {
    id: "lel-caj",
    simbolo: "cajero",
    tipo: "sujeto",
    sinonimos: [],
    nocion: ["Persona responsable de cobrar y de una caja durante un turno."],
    impacto: ["Puede cancelar ventas antes del corte de caja."],
    requisitoId: "REQ-011",
  },
  {
    id: "lel-can",
    simbolo: "cancelar venta",
    tipo: "verbo",
    sinonimos: ["anular venta"],
    nocion: ["Dejar sin efecto una venta registrada, revirtiendo su importe."],
    impacto: ["La venta se marca como cancelada y no cuenta en el corte de caja."],
    requisitoId: "REQ-011",
  },
  {
    id: "lel-sup",
    simbolo: "supervisor",
    tipo: "sujeto",
    sinonimos: ["jefe de área"],
    nocion: ["Persona que coordina a un equipo de trabajo."],
    impacto: ["Registra la asistencia de su personal."],
    requisitoId: "REQ-012",
  },
  {
    id: "lel-asi",
    simbolo: "asistencia registrada",
    tipo: "estado",
    sinonimos: ["presente"],
    nocion: ["Estado de un empleado cuya llegada quedó registrada en el turno."],
    impacto: ["Cuenta para el cálculo de la nómina."],
    requisitoId: "REQ-012",
  },
];
