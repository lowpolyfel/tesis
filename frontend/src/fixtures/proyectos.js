/*
 * Proyectos de prueba. Cada requisito pertenece a un proyecto y a un ciclo
 * (cada lote analizado es un ciclo del flujo de conocimiento continuo).
 */
export const proyectosSemilla = [
  {
    id: "P-01",
    nombre: "Sistema administrativo",
    descripcion: "Gestión interna: reportes, accesos y respaldos del área administrativa.",
    creadoEn: "2026-09-27T16:00:00",
  },
  {
    id: "P-02",
    nombre: "Portal de clientes y ventas",
    descripcion: "Seguimiento de pedidos, notas de venta y caja.",
    creadoEn: "2026-09-27T16:10:00",
  },
  {
    id: "P-03",
    nombre: "Operación y supervisión",
    descripcion: "Herramientas para supervisores y personal operativo; incluye control escolar heredado.",
    creadoEn: "2026-09-27T16:20:00",
  },
];

/* requisito → [proyecto, ciclo] */
export const asignacionSemilla = {
  "REQ-001": ["P-01", 1],
  "REQ-002": ["P-01", 1],
  "REQ-005": ["P-01", 2],
  "REQ-008": ["P-01", 3],
  "REQ-009": ["P-01", 3],
  "REQ-004": ["P-02", 1],
  "REQ-011": ["P-02", 1],
  "REQ-010": ["P-02", 2],
  "REQ-003": ["P-03", 1],
  "REQ-006": ["P-03", 1],
  "REQ-012": ["P-03", 2],
  "REQ-007": ["P-03", 3],
};
