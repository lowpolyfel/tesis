"""Documento de muestra: tres páginas con encabezado y pie repetidos, numeración
RF-01 / RNF-3 / REQ-12 / 3.2, párrafos partidos en renglones, una palabra cortada
con guion, un párrafo que cruza de página y oraciones sin verbo de obligación."""
from tests.documentos.pdf_prueba import pdf

ENCABEZADO = "Sistema de Nómina ACME — Especificación de requisitos v1.2"


def pie(n: int) -> str:
    return f"Página {n} de 3"


PAGINAS_SRS = [
    [ENCABEZADO,
     "3.2 Requisitos funcionales",
     "RF-01: El sistema deberá calcular la nómina quincenal de cada empleado con base en",
     "los días trabajados y las percepciones registradas en el periodo. Esto reduce errores",
     "de captura en el área de recursos humanos de la compañía.",
     "RF-02 El sistema debe permitir que el administrador dé de alta a los empleados y les",
     "asigne su número de seguridad social, su RFC y la cuenta bancaria para el depósito de",
     "la nómina.",
     pie(1)],
    [ENCABEZADO,
     "RNF-3 La aplicación tendrá que responder en menos de dos segundos a cualquier consul-",
     "ta del catálogo de empleados cuando haya hasta quinientos usuarios conectados al",
     "mismo tiempo.",
     "Alcance del módulo",
     "Este documento describe el módulo de nómina del sistema.",
     "RF-05 El sistema deberá conservar la bitácora de cambios de cada empleado durante",
     pie(2)],
    [ENCABEZADO,
     "cinco años contados a partir de su baja.",
     "REQ-12 El usuario podrá descargar su constancia en PDF, p. ej. la constancia anual del año.",
     pie(3)],
]

# (marca, página, texto) esperados
REQUISITOS_SRS = [
    ("RF-01", 1, ("El sistema deberá calcular la nómina quincenal de cada empleado con base en los días "
                  "trabajados y las percepciones registradas en el periodo.")),
    ("RF-02", 1, ("El sistema debe permitir que el administrador dé de alta a los empleados y les asigne su "
                  "número de seguridad social, su RFC y la cuenta bancaria para el depósito de la nómina.")),
    ("RNF-3", 2, ("La aplicación tendrá que responder en menos de dos segundos a cualquier consulta del "
                  "catálogo de empleados cuando haya hasta quinientos usuarios conectados al mismo tiempo.")),
    ("RF-05", 2, ("El sistema deberá conservar la bitácora de cambios de cada empleado durante cinco años "
                  "contados a partir de su baja.")),
    ("REQ-12", 3, "El usuario podrá descargar su constancia en PDF, p. ej. la constancia anual del año."),
]

# (texto, página, marca, motivo) esperados
DESCARTADOS_SRS = [
    ("Requisitos funcionales", 1, "3.2", "titulo"),
    ("Esto reduce errores de captura en el área de recursos humanos de la compañía.", 1, "RF-01",
     "sin_verbo_obligacion"),
    ("Alcance del módulo", 2, None, "titulo"),
    ("Este documento describe el módulo de nómina del sistema.", 2, None, "sin_verbo_obligacion"),
]


def pdf_srs() -> bytes:
    return pdf(PAGINAS_SRS)
