"""Documentos cargados a un proyecto: extracción, separación y registro en la
colección `documentos` (ADR 0009). No llama a ningún LLM, así que no pasa por la cola."""
from __future__ import annotations

from app.config import Settings
from app.db.repositorio import Repositorio

from .extraccion import DemasiadoGrande, leer, nombre_de_archivo
from .modelos import Documento, ResumenDocumento
from .separacion import separar_paginas

COLECCION = "documentos"
# Límites técnicos, no calibrables: un documento de Mongo no pasa de 16 MiB de BSON y
# los requisitos propuestos repiten parte del texto. Se mide el JSON, que pesa casi lo
# mismo que el BSON (este repite la clave de cada elemento de una lista): la mitad deja margen.
MAX_CARACTERES_GUARDADOS = 1_000_000
MAX_BYTES_GUARDADOS = 8 * 1024 * 1024


def _bytes(documento: Documento) -> int:
    return len(documento.model_dump_json().encode("utf-8"))


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

        documento = Documento(
            documento_id="D0000", proyecto_id=proyecto_id, archivo=nombre, tipo=extraido.tipo,
            paginas=len(extraido.paginas), caracteres=caracteres,
            requisitos_propuestos=separacion.requisitos_propuestos,
            fragmentos_descartados=separacion.fragmentos_descartados,
            total_descartados=separacion.total_descartados, advertencias=advertencias,
            texto_por_pagina=extraido.paginas if guardar_texto else None)
        tamano = _bytes(documento)
        if tamano > MAX_BYTES_GUARDADOS and documento.texto_por_pagina is not None:
            documento.advertencias.append(f"El texto por página no se guardó: el documento pasaba de "
                                          f"{MAX_BYTES_GUARDADOS / 2**20:g} MB.")
            documento.texto_por_pagina = None
            tamano = _bytes(documento)
        if tamano > MAX_BYTES_GUARDADOS:
            raise DemasiadoGrande(
                f"Lo que se propone de este documento ({len(documento.requisitos_propuestos)} requisitos) ocuparía "
                f"{tamano / 2**20:.1f} MB guardado, y el máximo es {MAX_BYTES_GUARDADOS / 2**20:g} MB por documento "
                "(límite de MongoDB): divide el archivo en partes más pequeñas.")

        def fabricar(documento_id: str) -> dict:
            return documento.model_copy(update={"documento_id": documento_id}).model_dump(mode="json")

        return Documento.model_validate(self.repo.crear_doc(COLECCION, "D", fabricar))

    def obtener(self, documento_id: str) -> Documento | None:
        datos = self.repo.obtener_doc(COLECCION, documento_id)
        return Documento.model_validate(datos) if datos else None

    def listar(self, proyecto_id: str) -> list[ResumenDocumento]:
        return [Documento.model_validate(d).resumen() for d in self.repo.listar_docs(COLECCION, proyecto_id=proyecto_id)]
