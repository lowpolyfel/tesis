"""Qué proveedor y qué modelo usa cada agente, por cuenta (ADR 0021).

Se guarda en la colección `perfiles_llm`, un documento por cuenta:

    {usuario_id, agentes: {rol: {proveedor, modelo}},
     proveedores: {id: {base_url, clave_cifrada, final}}, actualizado}

Las claves de API se cifran (Fernet) antes de guardarlas y nunca se devuelven: la API
solo dice si hay una y sus últimos cuatro caracteres. Un agente sin elección usa lo
que dice el .env del servidor.

`ClienteDinamico` es el cliente que reciben los agentes: en cada llamada usa el perfil
de quien está analizando (`con_perfil`, que fija el servicio antes de correr el grafo)
o, si no hay, el cliente por omisión.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .proveedores import NOMBRE_ROL, POR_ID, ROLES, crear_cliente_de

log = logging.getLogger(__name__)

COLECCION = "perfiles_llm"
_PERFIL: ContextVar[dict | None] = ContextVar("perfil_llm", default=None)


def por_omision(s) -> dict[str, dict]:
    """Lo que usa cada agente según el .env (el perfil de quien no eligió nada)."""
    critico = {"proveedor": s.critico_provider, "modelo": s.critico_model}
    return {"extractor": {"proveedor": "ollama", "modelo": s.extractor_model},
            "clasificador": {"proveedor": "ollama", "modelo": s.clasificador_model},
            "critico": critico,
            "modelador": {"proveedor": "ollama", "modelo": s.modelador_model},
            "revisor": {"proveedor": "ollama", "modelo": s.revisor_model}}


class Cifrado:
    def __init__(self, s):
        clave = s.clave_cifrado
        if not clave:
            ruta: Path = s.ruta(s.clave_cifrado_path)
            if ruta.exists():
                clave = ruta.read_text().strip()
            else:
                clave = Fernet.generate_key().decode()
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(clave)
                os.chmod(ruta, 0o600)
                log.warning("Se creó %s para cifrar las claves de API de las cuentas. Si varias máquinas usan "
                            "la misma base, pon esa clave en CLAVE_CIFRADO en todas.", ruta)
        self._f = Fernet(clave.encode() if isinstance(clave, str) else clave)

    def cifrar(self, texto: str) -> str:
        return self._f.encrypt(texto.encode()).decode()

    def descifrar(self, texto: str) -> str | None:
        try:
            return self._f.decrypt(texto.encode()).decode()
        except InvalidToken:  # se cifró con otra CLAVE_CIFRADO
            return None


class PerfilesLLM:
    def __init__(self, repo, settings):
        self.repo, self.s = repo, settings
        self._cifrado: Cifrado | None = None

    @property
    def cifrado(self) -> Cifrado:
        if self._cifrado is None:  # la clave se lee o se crea solo si alguien guarda una
            self._cifrado = Cifrado(self.s)
        return self._cifrado

    def _doc(self, usuario_id: str) -> dict:
        return self.repo.obtener_doc(COLECCION, usuario_id) or {"usuario_id": usuario_id, "agentes": {}, "proveedores": {}}

    def publico(self, usuario_id: str) -> dict:
        """Lo que ve la cuenta: la elección de cada agente (o la del servidor) y de cada proveedor
        su URL y si tiene clave, nunca la clave."""
        doc = self._doc(usuario_id)
        base = por_omision(self.s)
        agentes = []
        for rol in ROLES:
            elegido = doc["agentes"].get(rol)
            agentes.append({"rol": rol, "nombre": NOMBRE_ROL[rol], **(elegido or base[rol]), "propio": bool(elegido),
                            "servidor": base[rol]})
        proveedores = {pid: {"base_url": p.get("base_url"), "tiene_clave": bool(p.get("clave_cifrada")),
                             "final": p.get("final")} for pid, p in doc["proveedores"].items()}
        return {"agentes": agentes, "proveedores": proveedores, "actualizado": doc.get("actualizado")}

    def guardar(self, usuario_id: str, agentes: dict[str, dict | None], proveedores: dict[str, dict]) -> dict:
        """`agentes`: {rol: {proveedor, modelo} | None (volver al del servidor)}.
        `proveedores`: {id: {base_url?, api_key?}}: `api_key` "" o ausente deja la que había; None la borra."""
        doc = self._doc(usuario_id)
        for rol, eleccion in agentes.items():
            if rol not in ROLES:
                raise ValueError(f"agente desconocido: {rol}")
            if eleccion is None:
                doc["agentes"].pop(rol, None)
                continue
            if eleccion["proveedor"] not in POR_ID:
                raise ValueError(f"proveedor desconocido: {eleccion['proveedor']}")
            doc["agentes"][rol] = {"proveedor": eleccion["proveedor"], "modelo": eleccion["modelo"].strip()}
        for pid, datos in proveedores.items():
            if pid not in POR_ID:
                raise ValueError(f"proveedor desconocido: {pid}")
            actual = doc["proveedores"].setdefault(pid, {})
            if "base_url" in datos:
                actual["base_url"] = (datos["base_url"] or "").strip() or None
            if "api_key" in datos:
                clave = datos["api_key"]
                if clave is None:
                    actual.pop("clave_cifrada", None)
                    actual.pop("final", None)
                elif clave.strip():
                    actual["clave_cifrada"] = self.cifrado.cifrar(clave.strip())
                    actual["final"] = clave.strip()[-4:]
        doc["actualizado"] = datetime.now(UTC).isoformat(timespec="seconds")
        self.repo.guardar_doc(COLECCION, usuario_id, doc)
        return self.publico(usuario_id)

    def resuelto(self, usuario_id: str | None) -> dict[str, dict]:
        """{rol: {proveedor, modelo, base_url, api_key}} solo de lo que la cuenta eligió, con la
        clave descifrada (para el cliente; no sale de este proceso)."""
        if not usuario_id:
            return {}
        doc = self.repo.obtener_doc(COLECCION, usuario_id)
        if not doc:
            return {}
        salida = {}
        for rol, e in doc.get("agentes", {}).items():
            datos = doc.get("proveedores", {}).get(e["proveedor"], {})
            cifrada = datos.get("clave_cifrada")
            salida[rol] = {**e, "base_url": datos.get("base_url"),
                           "api_key": self.cifrado.descifrar(cifrada) if cifrada else None}
        return salida

    def eleccion(self, usuario_id: str | None, rol: str) -> dict:
        """La elección efectiva de un agente (la de la cuenta o la del servidor), sin la clave."""
        e = self.resuelto(usuario_id).get(rol)
        if e:
            return {"proveedor": e["proveedor"], "modelo": e["modelo"], "base_url": e.get("base_url"),
                    "tiene_clave": bool(e.get("api_key")), "propio": True}
        base = por_omision(self.s)[rol]
        return {**base, "base_url": None, "tiene_clave": rol == "critico" and bool(self.s.critico_api_key),
                "propio": False}

    def elecciones(self, usuario_id: str | None) -> dict[str, dict]:
        return {rol: self.eleccion(usuario_id, rol) for rol in ROLES}

    def clave_guardada(self, usuario_id: str, proveedor: str) -> str | None:
        datos = (self._doc(usuario_id)["proveedores"].get(proveedor) or {})
        return self.cifrado.descifrar(datos["clave_cifrada"]) if datos.get("clave_cifrada") else None

    def url_guardada(self, usuario_id: str, proveedor: str) -> str | None:
        return (self._doc(usuario_id)["proveedores"].get(proveedor) or {}).get("base_url")

    def url_ollama(self, usuario_id: str | None) -> str | None:
        """La URL de Ollama que escribió la cuenta, si escribió una."""
        doc = self.repo.obtener_doc(COLECCION, usuario_id) if usuario_id else None
        return ((doc or {}).get("proveedores", {}).get("ollama") or {}).get("base_url")


@contextmanager
def con_perfil(perfil: dict | None):
    """Mientras dure, los `ClienteDinamico` usan este perfil (el de `PerfilesLLM.resuelto`)."""
    marca = _PERFIL.set(perfil or None)
    try:
        yield
    finally:
        _PERFIL.reset(marca)


class ClienteDinamico:
    """El cliente de un agente: el del perfil en curso si eligió algo para este rol; si no, el de siempre."""

    def __init__(self, rol: str, defecto, settings):
        self.rol, self.defecto, self.settings = rol, defecto, settings
        self._cache: dict[tuple, object] = {}

    def actual(self):
        e = (_PERFIL.get() or {}).get(self.rol)
        if not e:
            return self.defecto
        clave = (e["proveedor"], e["modelo"], e.get("base_url"), e.get("api_key"))
        if clave not in self._cache:
            self._cache[clave] = crear_cliente_de(e, self.settings)
        return self._cache[clave]

    @property
    def modelo(self) -> str:
        return self.actual().modelo

    def completar(self, prompt, esquema: dict) -> str:
        return self.actual().completar(prompt, esquema)
