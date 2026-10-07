"""Documentos cargados a un proyecto: extracción, separación y registro en la
colección `documentos` (ADR 0009). No llama a ningún LLM, así que no pasa por la cola."""
from __future__ import annotations

from app.config import Settings
from app.db.repositorio import Repositorio

from .extraccion import leer, nombre_de_archivo
from .modelos import Documento, ResumenDocumento
from .separacion import separar_paginas

COLECCION = "documentos"
# Límite técnico, no calibrable: un documento de Mongo no pasa de 16 MB y los
# requisitos propuestos repiten parte del texto.
MAX_CARACTERES_GUARDADOS = 1_000_000


class Documentos:
    def __init__(self, repo: Repositorio, settings: Settings):
        self.repo = repo
        self.settings = settings

    @property
    def max_bytes(self) -> int:
        return int(self.settings.documento_max_mb * 1024 * 1024)

    def cargar(self, proyecto_id: str, archivo: str | None, contenido: bytes,
               tipo_contenido: str | None = None) -> Documento:
        """Lanza `ErrorDocumento` (tipo, tamaño, sin texto, ilegible) sin guardar nada."""
        nombre = nombre_de_archivo(archivo)
        extraido = leer(nombre, contenido, self.max_bytes, tipo_contenido)
        separacion = separar_paginas(extraido.paginas, con_paginas=extraido.con_paginas,
                                     maquetado=extraido.tipo == "pdf")
        caracteres = sum(len(p) for p in extraido.paginas)
        advertencias = extraido.advertencias + separacion.advertencias
        guardar_texto = caracteres <= MAX_CARACTERES_GUARDADOS
        if not guardar_texto:
            advertencias.append(f"El texto por página no se guardó: {caracteres} caracteres "
                                f"(máximo {MAX_CARACTERES_GUARDADOS}).")
        if not separacion.requisitos_propuestos:
            advertencias.append("No se encontró ninguna oración con verbo de obligación o capacidad: "
                                "revisa los fragmentos descartados.")

        def fabricar(documento_id: str) -> dict:
            return Documento(
                documento_id=documento_id, proyecto_id=proyecto_id, archivo=nombre, tipo=extraido.tipo,
                paginas=len(extraido.paginas), caracteres=caracteres,
                requisitos_propuestos=separacion.requisitos_propuestos,
                fragmentos_descartados=separacion.fragmentos_descartados,
                total_descartados=separacion.total_descartados, advertencias=advertencias,
                texto_por_pagina=extraido.paginas if guardar_texto else None,
            ).model_dump(mode="json")

        return Documento.model_validate(self.repo.crear_doc(COLECCION, "D", fabricar))

    def obtener(self, documento_id: str) -> Documento | None:
        datos = self.repo.obtener_doc(COLECCION, documento_id)
        return Documento.model_validate(datos) if datos else None

    def listar(self, proyecto_id: str) -> list[ResumenDocumento]:
        return [Documento.model_validate(d).resumen() for d in self.repo.listar_docs(COLECCION, proyecto_id=proyecto_id)]
