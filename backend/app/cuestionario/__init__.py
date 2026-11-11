"""Cuestionario de evaluación de DUDAMEL (instrumento del proyecto de titulación, UACJ).

Las 60 preguntas de `docs/cuestionario-evaluacion.md`, en el mismo orden y con la misma
redacción: la System Usability Scale (25–34) solo vale si no se toca. Cada cuenta tiene una
respuesta (colección `cuestionarios`, con el id de la cuenta): se guarda mientras se llena
(borrador) y se envía cuando todo lo obligatorio está contestado.

**Quién lo contesta.** Se abre cuando la cuenta tiene al menos un proyecto que ya llegó a la
quinta fase (sus requisitos están generados): antes no hay con qué comparar el trabajo a mano.

**Anónimo para el análisis.** El id de la cuenta solo sirve para que cada quien tenga una
respuesta y pueda retomarla; los resultados y el CSV no lo incluyen (cada fila es «R01», «R02»…
por orden de envío). Solo las cuentas de CUESTIONARIO_ADMINS ven los resultados.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime

COLECCION = "cuestionarios"
VERSION = "cuestionario-v1"

PRESENTACION = (
    "Gracias por probar el sistema. Ya hiciste este trabajo a mano y ahora lo hiciste con DUDAMEL. Lo que más nos "
    "interesa es que compares las dos experiencias.\n\nSon unos 12 minutos. Es anónimo: no se pide tu nombre ni tu "
    "correo. Las respuestas se usan únicamente como parte de la evaluación de un proyecto de titulación de la UACJ.\n\n"
    "No hay respuestas correctas. Lo que más sirve es que seas franco, sobre todo en lo que salió peor con el sistema "
    "que a mano.")

TIEMPOS = ["Menos de 1 hora", "Entre 1 y 2 horas", "Entre 2 y 4 horas", "Entre 4 y 8 horas", "Más de 8 horas"]
ENCONTRADOS = ["No, ninguno", "Sí, uno o dos", "Sí, varios", "Sí, muchos"]
COMPARACION = ["Mucho mejor a mano", "Algo mejor a mano", "Igual", "Algo mejor con DUDAMEL", "Mucho mejor con DUDAMEL"]
ACUERDO = ["Totalmente en desacuerdo", "", "", "", "Totalmente de acuerdo"]


def _op(n, texto, opciones):
    return {"id": f"q{n}", "n": n, "tipo": "opcion", "texto": texto, "opciones": opciones, "obligatoria": True}


def _esc(n, texto, etiquetas):
    return {"id": f"q{n}", "n": n, "tipo": "escala", "texto": texto, "etiquetas": etiquetas, "obligatoria": True}


def _num(n, texto, ayuda):
    return {"id": f"q{n}", "n": n, "tipo": "numero", "texto": texto, "ayuda": ayuda, "obligatoria": True}


def _txt(n, texto):
    return {"id": f"q{n}", "n": n, "tipo": "texto", "texto": texto, "obligatoria": False}


def _cas(n, texto, opciones, exclusiva):
    return {"id": f"q{n}", "n": n, "tipo": "casillas", "texto": texto, "opciones": opciones, "exclusiva": exclusiva,
            "obligatoria": True}


SECCIONES = [
    {"id": "s1", "titulo": "Antes de empezar", "instruccion": None, "preguntas": [
        _op(1, "¿Cuánta experiencia tienes en ingeniería de requisitos?",
            ["Ninguna, es la primera vez que trabajo con requisitos", "Solo lo que vi en clase",
             "Lo de clase y algún proyecto escolar", "He trabajado con requisitos fuera de la escuela"]),
        _op(2, "¿Habías usado antes alguna herramienta de IA para trabajar con requisitos?",
            ["No", "Sí, un asistente de propósito general (ChatGPT, Claude, Gemini)",
             "Sí, una herramienta hecha para ingeniería de requisitos"]),
        _op(3, "¿En qué orden hiciste el trabajo?",
            ["Primero a mano y después con DUDAMEL", "Primero con DUDAMEL y después a mano", "Los hice en paralelo"]),
        _op(4, "¿Trabajaste sobre la misma entrevista en los dos casos?", ["Sí, la misma", "No, fueron entrevistas distintas"]),
        _op(5, "¿Cuánto tiempo te llevó hacerlo a mano, aproximadamente?", TIEMPOS),
        _op(6, "¿Cuánto tiempo te llevó hacerlo con DUDAMEL, contando el tiempo de validar cada etapa?", TIEMPOS),
        _num(7, "¿Cuántos requisitos obtuviste trabajando a mano?", "Un número"),
        _num(8, "¿Cuántos requisitos obtuviste con DUDAMEL, después de validar?", "Un número"),
    ]},
    {"id": "s2", "titulo": "Comparación con el trabajo manual",
     "instruccion": ("En esta sección, el punto medio significa que no hubo diferencia. Hacia la izquierda, que a mano "
                     "salió mejor. Hacia la derecha, que con DUDAMEL salió mejor."),
     "preguntas": [
        *[_esc(n, t, COMPARACION) for n, t in (
            (9, "El tiempo total que me tomó llegar a los requisitos"),
            (10, "El esfuerzo mental que me costó"),
            (11, "La cantidad de requisitos que encontré"),
            (12, "Qué tan bien redactados quedaron los requisitos"),
            (13, "Qué tan completos quedaron respecto a lo que se dijo en la entrevista"),
            (14, "Qué tan libres de ambigüedad quedaron"),
            (15, "Qué tan fácil es rastrear de dónde salió cada requisito"),
            (16, "Qué tanto entendí el dominio del cliente al terminar"),
            (17, "La confianza que tengo en el resultado final"),
            (18, "Qué tan bien quedaron separados los funcionales de los no funcionales"),
            (19, "Qué tan razonables quedaron las prioridades"),
            (20, "Qué tan presentable quedó el documento final"))],
        _op(21, "Si tuvieras que entregarle una sola de las dos versiones al cliente, ¿cuál entregarías?",
            ["La que hice a mano, sin dudarlo", "La que hice a mano, pero fue parejo", "Me da igual, son equivalentes",
             "La de DUDAMEL, pero fue parejo", "La de DUDAMEL, sin dudarlo"]),
        _op(22, "¿Encontraste con DUDAMEL algún requisito que a mano se te había pasado?", ENCONTRADOS),
        _op(23, "¿Encontraste a mano algún requisito que DUDAMEL no sacó?", ENCONTRADOS),
        _txt(24, "¿Cuál dirías que es la diferencia más importante entre las dos versiones?"),
    ]},
    {"id": "s3", "titulo": "Facilidad de uso",
     "instruccion": ("Diez afirmaciones sobre el sistema. Marca qué tan de acuerdo estás con cada una, donde 1 es "
                     "totalmente en desacuerdo y 5 totalmente de acuerdo. Contesta rápido y con lo primero que pienses. "
                     "Fíjate en que algunas están escritas al revés a propósito."),
     "preguntas": [_esc(n, t, ACUERDO) for n, t in (
         (25, "Creo que me gustaría usar este sistema con frecuencia."),
         (26, "Encontré el sistema innecesariamente complejo."),
         (27, "Pensé que el sistema era fácil de usar."),
         (28, "Creo que necesitaría el apoyo de una persona con conocimientos técnicos para poder usar este sistema."),
         (29, "Encontré que las distintas funciones del sistema estaban bien integradas entre sí."),
         (30, "Pensé que había demasiada inconsistencia en este sistema."),
         (31, "Imagino que la mayoría de la gente aprendería a usar este sistema muy rápido."),
         (32, "Encontré el sistema muy incómodo de usar."),
         (33, "Me sentí seguro usando el sistema."),
         (34, "Necesité aprender muchas cosas antes de poder empezar a usar este sistema."))]},
    {"id": "s4", "titulo": "Las etapas intermedias",
     "instruccion": ("Trabajando a mano probablemente no construiste un léxico ni un mapa conceptual ni metas. Esta "
                     "sección pregunta si valió la pena que el sistema te obligara a hacerlo."),
     "preguntas": [
        *[_esc(n, t, ACUERDO) for n, t in (
            (35, "El léxico me hizo entender cosas del dominio que trabajando a mano no había notado."),
            (36, "El mapa conceptual me ayudó a ver relaciones que a mano no había visto."),
            (37, "Las metas me ayudaron a entender para qué sirve cada requisito."),
            (38, "Tener que validar cada etapa antes de seguir me pareció útil y no una molestia."),
            (39, "El tiempo extra que me costaron las etapas intermedias valió la pena."))],
        _op(40, "Si pudieras saltarte una etapa, ¿cuál te saltarías?",
            ["Ninguna, las cuatro sirven", "El léxico", "El mapa conceptual", "Las metas",
             "Todas: preferiría ir de la entrevista a los requisitos directo"]),
        _cas(41, "¿Volverías a usar alguno de estos artefactos aunque trabajaras a mano?",
             ["El léxico", "El mapa conceptual", "Las metas", "Ninguno"], "Ninguno"),
    ]},
    {"id": "s5", "titulo": "La detección de ambigüedad",
     "instruccion": ("Esta es la parte central del sistema: cuando un término se podía entender de varias formas, el "
                     "sistema te lo señaló y te pidió elegir."),
     "preguntas": [
        *[_esc(n, t, ACUERDO) for n, t in (
            (42, "El sistema señaló términos ambiguos que trabajando a mano no había notado."),
            (43, "Cuando el sistema marcó un término como ambiguo, casi siempre tenía razón."),
            (44, "Las interpretaciones que propuso para cada término estaban bien planteadas."),
            (45, "Me quedó claro qué hacer cuando un término tenía más de una interpretación."),
            (46, "El sistema dejó pasar términos ambiguos que yo sí había notado a mano."),
            (47, "Me resultó fácil corregir un término cuando ninguna interpretación era la correcta."))],
        _num(48, "¿Cuántos términos ambiguos detectaste tú trabajando a mano?", "Un número, 0 si ninguno"),
        _txt(49, "Si recuerdas algún término donde el sistema se equivocó, escríbelo con lo que debió entender."),
    ]},
    {"id": "s6", "titulo": "Problemas durante la prueba",
     "instruccion": ("Esta sección separa los problemas de infraestructura de los problemas de diseño. Si el servicio "
                     "de Google se cayó mientras probabas, eso no dice nada sobre si el sistema está bien hecho, pero sí "
                     "afecta cómo lo viviste."),
     "preguntas": [
        _cas(50, "¿Te topaste con alguno de estos problemas?",
             ["Error 503: el modelo de Gemini estaba saturado", "Se me agotó la cuota de mi clave de API",
              "Tuve que sacar una clave nueva con otra cuenta", "El análisis se quedó colgado sin terminar",
              "La entrevista quedó mal separada en turnos", "Una etapa no se desbloqueó cuando esperaba que lo hiciera",
              "El sistema se puso lento", "No tuve ningún problema"], "No tuve ningún problema"),
        _esc(51, "¿Qué tanto afectaron esos problemas tu opinión del sistema?", ["Nada", "", "", "", "Muchísimo"]),
        _op(52, "¿Cuántas veces tuviste que volver a procesar algo por un error?",
            ["Ninguna", "Una o dos", "Entre tres y cinco", "Más de cinco"]),
        _op(53, "Sin contar esos problemas técnicos, ¿tu comparación entre las dos formas de trabajar cambiaría?",
            ["No, mi opinión es la misma", "Sí, DUDAMEL saldría mejor parado", "Sí, DUDAMEL saldría peor parado"]),
    ]},
    {"id": "s7", "titulo": "Respuestas abiertas",
     "instruccion": "Esta es la parte que más sirve. Escribe lo que se te ocurra, aunque sea corto.",
     "preguntas": [
        _txt(54, "¿Qué hizo mejor el sistema que tú a mano?"),
        _txt(55, "¿Qué hiciste tú mejor a mano que el sistema?"),
        _txt(56, "¿Qué fue lo más frustrante de usar el sistema?"),
        _txt(57, "Si pudieras agregarle una sola cosa, ¿cuál sería?"),
        _txt(58, "¿Hubo algo que no entendiste cómo usar? ¿Qué parte de la guía faltó explicar mejor?"),
        _op(59, "¿Usarías este sistema en un proyecto real tuyo, en lugar de hacerlo a mano?",
            ["Sí, tal como está", "Sí, pero solo si le arreglan algunas cosas",
             "Lo usaría como apoyo, pero revisando todo a mano", "No, prefiero hacerlo a mano"]),
        _txt(60, "¿Por qué?"),
    ]},
]
PREGUNTAS = {p["id"]: p for s in SECCIONES for p in s["preguntas"]}

# Las escalas que se grafican juntas (barras apiladas al 100 %). En el SUS los pares están redactados
# en negativo: «de acuerdo» en un par es malo.
_ACUERDO_NIVELES = ["Totalmente en desacuerdo", "En desacuerdo", "Ni de acuerdo ni en desacuerdo", "De acuerdo",
                    "Totalmente de acuerdo"]
GRUPOS_ESCALA = [
    {"id": "comparacion", "titulo": "Comparación con el trabajo manual", "niveles": COMPARACION,
     "preguntas": [f"q{n}" for n in range(9, 21)]},
    {"id": "sus", "titulo": "Facilidad de uso (SUS)", "niveles": _ACUERDO_NIVELES,
     "preguntas": [f"q{n}" for n in range(25, 35)]},
    {"id": "etapas", "titulo": "Las etapas intermedias", "niveles": _ACUERDO_NIVELES,
     "preguntas": [f"q{n}" for n in range(35, 40)]},
    {"id": "ambiguedad", "titulo": "La detección de ambigüedad", "niveles": _ACUERDO_NIVELES,
     "preguntas": [f"q{n}" for n in range(42, 48)]},
]
ORDEN = [p["id"] for s in SECCIONES for p in s["preguntas"]]
SUS = [f"q{n}" for n in range(25, 35)]
MAX_TEXTO = 4000
MAX_NUMERO = 10000


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def publico() -> dict:
    return {"version": VERSION, "presentacion": PRESENTACION, "secciones": SECCIONES, "total": len(ORDEN),
            "obligatorias": sum(1 for p in PREGUNTAS.values() if p["obligatoria"])}


# ---------------------------------------------------------------- validación

def limpiar(respuestas: dict) -> tuple[dict, list[dict]]:
    """Las respuestas válidas (las vacías se quitan) y los errores [{id, motivo}] de las que no lo son."""
    limpias, errores = {}, []
    for qid, v in (respuestas or {}).items():
        p = PREGUNTAS.get(qid)
        if p is None:
            errores.append({"id": qid, "motivo": "pregunta desconocida"})
            continue
        if v is None or v == "" or v == []:
            continue
        t = p["tipo"]
        if t == "opcion":
            if v not in p["opciones"]:
                errores.append({"id": qid, "motivo": "opción desconocida"})
                continue
        elif t == "escala":
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                errores.append({"id": qid, "motivo": "tiene que ser un número del 1 al 5"})
                continue
        elif t == "numero":
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= MAX_NUMERO:
                errores.append({"id": qid, "motivo": f"tiene que ser un número entero entre 0 y {MAX_NUMERO}"})
                continue
        elif t == "texto":
            if not isinstance(v, str):
                errores.append({"id": qid, "motivo": "tiene que ser texto"})
                continue
            v = v.strip()[:MAX_TEXTO]
            if not v:
                continue
        elif t == "casillas":
            if not isinstance(v, list) or any(x not in p["opciones"] for x in v):
                errores.append({"id": qid, "motivo": "opción desconocida"})
                continue
            v = [x for x in p["opciones"] if x in v]  # en el orden del cuestionario, sin repetir
            if p["exclusiva"] in v and len(v) > 1:
                errores.append({"id": qid, "motivo": f"«{p['exclusiva']}» no va con otras opciones"})
                continue
        limpias[qid] = v
    return limpias, errores


def faltantes(respuestas: dict) -> list[str]:
    return [q for q in ORDEN if PREGUNTAS[q]["obligatoria"] and q not in respuestas]


def puntaje_sus(respuestas: dict) -> float | None:
    """System Usability Scale (Brooke, 1996): impares valor−1, pares 5−valor, suma × 2.5 (0–100;
    no es un porcentaje). None si falta alguno de los diez."""
    if any(q not in respuestas for q in SUS):
        return None
    total = sum((respuestas[q] - 1) if int(q[1:]) % 2 else (5 - respuestas[q]) for q in SUS)
    return total * 2.5


def nuevo(usuario_id: str) -> dict:
    return {"usuario_id": usuario_id, "version": VERSION, "respuestas": {}, "estado": "borrador", "sus": None,
            "creado": ahora(), "actualizado": ahora(), "enviado": None}


# ---------------------------------------------------------------- resultados (anónimos)

def _cuartiles(xs: list[float]) -> tuple[float, float]:
    if len(xs) < 2:
        return (xs[0], xs[0]) if xs else (None, None)
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[0], q[2]


def resultados(docs: list[dict]) -> dict:
    """Lo que pide el protocolo para cada tipo de pregunta, solo con los cuestionarios enviados:
    SUS con media, mediana y desviación; escalas con mediana y rango intercuartílico (y cuántos
    quedaron arriba del punto medio en la comparación); conteos con media, mediana y rango;
    opciones y casillas con frecuencias; abiertas, las respuestas (sin la cuenta)."""
    enviados = sorted((d for d in docs if d.get("estado") == "enviado"), key=lambda d: d.get("enviado") or "")
    n = len(enviados)
    sus = [d["sus"] for d in enviados if d.get("sus") is not None]
    salida = {"version": VERSION, "enviados": n, "borradores": sum(1 for d in docs if d.get("estado") != "enviado"),
              "sus": {"n": len(sus), "media": statistics.fmean(sus) if sus else None,
                      "mediana": statistics.median(sus) if sus else None,
                      "de": statistics.stdev(sus) if len(sus) > 1 else None,
                      "valores": sorted(sus)},  # ordenados: sin el orden de envío, no se ligan a nadie
              "preguntas": {}}
    for qid in ORDEN:
        p = PREGUNTAS[qid]
        vals = [d["respuestas"][qid] for d in enviados if qid in d["respuestas"]]
        r: dict = {"n": len(vals)}
        if p["tipo"] == "escala" and vals:
            q1, q3 = _cuartiles(vals)
            r.update(mediana=statistics.median(vals), q1=q1, q3=q3, frecuencias={str(k): vals.count(k) for k in range(1, 6)})
            if qid in [f"q{k}" for k in range(9, 21)]:
                r["arriba_del_medio"] = sum(1 for v in vals if v > 3) / len(vals)
        elif p["tipo"] == "numero" and vals:
            r.update(media=statistics.fmean(vals), mediana=statistics.median(vals), minimo=min(vals), maximo=max(vals),
                     valores=sorted(vals))
        elif p["tipo"] == "opcion":
            r["frecuencias"] = {o: vals.count(o) for o in p["opciones"]}
        elif p["tipo"] == "casillas":
            r["frecuencias"] = {o: sum(1 for v in vals if o in v) for o in p["opciones"]}
        elif p["tipo"] == "texto":
            r["respuestas"] = vals
        salida["preguntas"][qid] = r
    # el protocolo: declarar cuántos vivieron fallas de infraestructura antes de concluir sobre usabilidad
    con_fallas = [d for d in enviados if d["respuestas"].get("q50") and "No tuve ningún problema" not in d["respuestas"]["q50"]]
    salida["con_fallas_de_infraestructura"] = len(con_fallas)
    return salida


def filas_csv(docs: list[dict]) -> list[list]:
    """Una fila por cuestionario enviado, sin la cuenta: R01, R02… por orden de envío."""
    enviados = sorted((d for d in docs if d.get("estado") == "enviado"), key=lambda d: d.get("enviado") or "")
    filas = [["respuesta", "enviado", "sus", *[f"P{PREGUNTAS[q]['n']}" for q in ORDEN]]]
    for k, d in enumerate(enviados, 1):
        valores = []
        for q in ORDEN:
            v = d["respuestas"].get(q)
            valores.append("; ".join(v) if isinstance(v, list) else ("" if v is None else v))
        filas.append([f"R{k:02d}", (d.get("enviado") or "")[:10], d.get("sus"), *valores])
    return filas
