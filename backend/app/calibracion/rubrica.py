"""Rúbricas de la revisión humana (ADR 0029): una sola fuente para la pantalla, el Markdown del
apéndice (`docs/rubrica-revision.md`, que una prueba mantiene igual a `markdown()`) y el paquete
para Overleaf.

- **Calidad de una salida del Clasificador** (prueba de modelos): tres criterios booleanos
  independientes, más la cobertura de lecturas esperadas. La detección (si marcó «ambiguo») no
  se revisa aquí: se mide sola contra el banco.
- **Ambigüedad de un término de entrevista** (calibración): sí, no o no sé.
- **Modos de falla** de los falsos negativos: un catálogo corto para clasificarlos a mano.
"""
from __future__ import annotations

CRITERIOS: tuple[dict, ...] = (
    {
        "clave": "fidelidad", "nombre": "Fidelidad", "tecla": "1",
        "oracion": ("La paráfrasis dice lo que decía la cita original con ese sentido del término, sin agregar ni "
                    "quitar información (actores, condiciones, cantidades o momentos)."),
        "pasa": ("Cita «Cada consulta tiene que quedar registrada…»; paráfrasis «Cada atención del médico al paciente "
                 "tiene que quedar registrada…»: cambia solo el término."),
        "no_pasa": ("Paráfrasis «Cada consulta tiene que quedar registrada por la recepcionista en el expediente "
                    "digital…»: agrega quién registra y dónde, que la cita no dice."),
    },
    {
        "clave": "delimitacion", "nombre": "Delimitación", "tecla": "2",
        "oracion": ("El significado está acotado a un sentido y no es circular: no usa el propio término (ni una "
                    "forma suya) para definirse."),
        "pasa": "«corte»: «arqueo del dinero cobrado en el turno».",
        "no_pasa": "«corte»: «el corte que se hace al final del turno» (circular) o «algo del cierre» (vago).",
    },
    {
        "clave": "intencion", "nombre": "Intención", "tecla": "3",
        "oracion": ("La intención dice para qué usa el término quien habla (qué quiere lograr), no vuelve a decir "
                    "qué significa."),
        "pasa": "«consulta»: «llevar el registro de las atenciones a cada paciente».",
        "no_pasa": "«consulta»: «la cita médica con el paciente» (repite el significado en lugar del propósito).",
    },
)
CLAVES = tuple(c["clave"] for c in CRITERIOS)

REGLA_AGREGADO = ("Cada criterio se marca una vez por salida (un término de un modelo). Se cumple si lo cumplen "
                  "todas las intenciones de esa salida: basta una intención que falle para no marcarlo.")

COBERTURA = {
    "nombre": "Cobertura de lecturas esperadas", "teclas": "4, 5, 6",
    "oracion": ("Solo en los términos ambiguos: de las lecturas esperadas que registra el banco, marca las que "
                "aparecen en alguna intención de la salida. La cobertura es cubiertas sobre esperadas."),
    "pasa": ("«caja» (supermercado), lecturas «punto de cobro», «dinero o fondo», «empaque»: la salida da «el lugar "
             "donde se cobra» y «el dinero de la caja» → se marcan las dos primeras (2 de 3)."),
    "no_pasa": ("Que la salida mencione «cobro» de pasada no cubre «el dinero o fondo de caja» si ninguna intención "
                "le da ese sentido. El cotejo es contra la lectura escrita en el banco, no contra palabras sueltas."),
}

ETIQUETA_ENTREVISTA = {
    "oracion": ("¿Este término, en las citas de esta entrevista y en este dominio, admite más de una lectura "
                "razonable para alguien que no estuvo en la entrevista?"),
    "si": "«consultas» en una clínica que también lleva un sistema de búsquedas: cita médica o búsqueda.",
    "no": "«paciente» en la misma clínica: la persona que recibe atención; no hay otra lectura en ese dominio.",
    "no_se": ("Cuando las citas no alcanzan para decidir: queda fuera del ground truth y se cuenta aparte. "
              "No se adivina."),
    "teclas": {"si": "S", "no": "N", "no_se": "X"},
}

MODOS_FALLA: tuple[dict, ...] = (
    {"clave": "documento_hecho", "nombre": "Documento contra el hecho que registra",
     "descripcion": ("El modelo da solo el documento o solo el hecho que el documento registra: factura contra "
                     "venta, acta contra reunión, nómina contra el proceso de pago.")},
    {"clave": "sentido_dominante", "nombre": "Solo el sentido dominante",
     "descripcion": "Da únicamente el sentido más común en el español general y no ve el del oficio."},
    {"clave": "regionalismo", "nombre": "Regionalismo no reconocido",
     "descripcion": "No reconoce el uso del español de trabajo en México (o de otra región) que abre la segunda lectura."},
    {"clave": "contexto_cierra", "nombre": "El contexto lo cierra de más",
     "descripcion": "Usa el dominio del proyecto para descartar una lectura que en la cita sí cabe."},
    {"clave": "formato", "nombre": "Falla de formato",
     "descripcion": ("No dio una salida válida (por ejemplo, un significado más largo que el máximo de palabras) y "
                     "cuenta como no detectado.")},
    {"clave": "otro", "nombre": "Otro", "descripcion": "Ninguno de los anteriores; conviene escribir una nota."},
)
CLAVES_MODOS = tuple(m["clave"] for m in MODOS_FALLA)


def publica() -> dict:
    """Lo que la pantalla muestra en su panel de ayuda."""
    return {"criterios": list(CRITERIOS), "regla_agregado": REGLA_AGREGADO, "cobertura": COBERTURA,
            "etiqueta_entrevista": ETIQUETA_ENTREVISTA, "modos_falla": list(MODOS_FALLA), "markdown": markdown()}


def markdown() -> str:
    """El apéndice en Markdown: lo que se le entrega a un segundo anotador."""
    lineas = [
        "# Rúbrica de revisión",
        "",
        "Generada desde `backend/app/calibracion/rubrica.py` (ADR 0029). No la edites a mano: cambia ese archivo.",
        "",
        "## 1. Calidad de una salida del Clasificador",
        "",
        ("La revisión juzga solo la factura de lo que el modelo escribió. Si detectó o no la ambigüedad ya se mide "
         "contra el banco y no se revisa aquí. La revisión es a ciegas: no se ve qué modelo produjo la salida."),
        "",
        f"{REGLA_AGREGADO}",
        "",
    ]
    for c in CRITERIOS:
        lineas += [f"### {c['nombre']} (tecla {c['tecla']})", "", c["oracion"], "",
                   f"- **Pasa:** {c['pasa']}", f"- **No pasa:** {c['no_pasa']}", ""]
    lineas += [f"### {COBERTURA['nombre']} (teclas {COBERTURA['teclas']})", "", COBERTURA["oracion"], "",
               f"- **Pasa:** {COBERTURA['pasa']}", f"- **No pasa:** {COBERTURA['no_pasa']}", "",
               "Teclas: `Enter` guarda y avanza, `Backspace` regresa, `?` abre esta rúbrica.", "",
               "## 2. Ambigüedad de un término de entrevista", "",
               ETIQUETA_ENTREVISTA["oracion"], "",
               f"- **Sí (S):** {ETIQUETA_ENTREVISTA['si']}",
               f"- **No (N):** {ETIQUETA_ENTREVISTA['no']}",
               f"- **No sé (X):** {ETIQUETA_ENTREVISTA['no_se']}", "",
               "Se etiqueta a ciegas: sin ver la similitud ni la decisión del sistema, y en un orden barajado.", "",
               "## 3. Modos de falla de los falsos negativos", "",
               "Para cada término ambiguo que un modelo marcó como unívoco (o que falló), el modo que mejor lo explica:",
               ""]
    lineas += [f"- **{m['nombre']}** (`{m['clave']}`): {m['descripcion']}" for m in MODOS_FALLA]
    return "\n".join(lineas) + "\n"
