"""Cuentas: registro con código por correo, entrar, sesiones y restablecer la contraseña.

- Registro: la cuenta nace sin verificar y recibe un código de 6 dígitos; con el
  código queda verificada y abre sesión. Sin verificar no se puede entrar.
- Entrar: correo y contraseña. Con `AUTH_CODIGO_AL_ENTRAR=true` además pide un
  código por correo cada vez (segundo factor).
- Restablecer: un código por correo y la contraseña nueva; cierra todas las sesiones.
- Sesión: la cookie lleva `<usuario_id>.<token>`; se guarda solo el sha256 del token.

Los códigos vencen (`CODIGO_MINUTOS`), admiten pocos intentos (`CODIGO_INTENTOS`) y
no se reenvían antes de `CODIGO_REENVIO_S`. Tras varias contraseñas incorrectas
seguidas la cuenta se bloquea unos minutos.
"""
from __future__ import annotations

import hmac
import re
import secrets
import threading
from datetime import timedelta

from app.config import Settings
from app.db.repositorio import Repositorio
from app.models import ahora

from .contrasenas import CIFRADA_FICTICIA, cifrar, huella, verificar
from .correo import Correo
from .modelos import Codigo, Proposito, Sesion, Usuario

COLECCION = "usuarios"
MAX_SESIONES = 10
FALLOS_PARA_BLOQUEO = 8
BLOQUEO = timedelta(minutes=5)
_PATRON_ID = re.compile(r"^U\d+$")


class ErrorCuenta(Exception):
    """Error que la API devuelve tal cual: `estado` HTTP y `codigo` para el frontend."""
    estado = 400
    codigo = "error"


class CorreoEnUso(ErrorCuenta):
    estado, codigo = 409, "correo_en_uso"


class CredencialesInvalidas(ErrorCuenta):
    estado, codigo = 401, "credenciales"


class SinVerificar(ErrorCuenta):
    estado, codigo = 403, "sin_verificar"


class CodigoInvalido(ErrorCuenta):
    estado, codigo = 400, "codigo_invalido"


class EsperaReenvio(ErrorCuenta):
    estado, codigo = 429, "espera"

    def __init__(self, segundos: int):
        super().__init__(f"Espera {segundos} s para pedir otro código.")
        self.segundos = segundos


class CuentaBloqueada(ErrorCuenta):
    estado, codigo = 429, "bloqueada"


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def _huella_codigo(usuario_id: str, proposito: str, codigo: str) -> str:
    return huella(f"{usuario_id}:{proposito}:{codigo}")


class Cuentas:
    def __init__(self, repo: Repositorio, settings: Settings, correo: Correo | None = None):
        self.repo = repo
        self.s = settings
        self.correo = correo or Correo(settings)
        # leer y reescribir el documento de una cuenta sin carreras dentro del proceso;
        # el envío del correo (red) va fuera del candado
        self._candado = threading.RLock()

    # ------------------------------------------------------------ lectura y escritura

    def obtener(self, usuario_id: str) -> Usuario | None:
        if not _PATRON_ID.match(usuario_id or ""):
            return None
        d = self.repo.obtener_doc(COLECCION, usuario_id)
        return Usuario.model_validate(d) if d else None

    def por_correo(self, correo: str) -> Usuario | None:
        docs = [Usuario.model_validate(d) for d in self.repo.listar_docs(COLECCION, correo=normalizar_correo(correo))]
        return next((u for u in docs if u.verificado), docs[0] if docs else None)

    def _guardar(self, u: Usuario) -> None:
        self.repo.guardar_doc(COLECCION, u.usuario_id, u.model_dump(mode="json"))

    # ------------------------------------------------------------ códigos

    def _segundos_para_reenviar(self, u: Usuario, proposito: str) -> int:
        c = u.codigo
        if c is None or c.proposito != proposito:
            return 0
        pasados = (ahora() - c.enviado).total_seconds()
        return max(0, int(self.s.codigo_reenvio_s - pasados + 0.999))

    def _enviar_codigo(self, u: Usuario, proposito: Proposito, *, exigir_espera: bool = False) -> Usuario:
        """Manda un código nuevo y lo guarda (primero se envía: si el correo falla, no queda
        un código que nadie recibió). Si hay uno del mismo propósito enviado hace muy poco,
        no se manda otro; con `exigir_espera` eso es un error (botón «reenviar»)."""
        espera = self._segundos_para_reenviar(u, proposito)
        if espera:
            if exigir_espera:
                raise EsperaReenvio(espera)
            return u
        codigo = f"{secrets.randbelow(10**6):06d}"
        self.correo.enviar_codigo(u.correo, u.nombre, codigo, proposito, self.s.codigo_minutos)
        with self._candado:
            actual = self.obtener(u.usuario_id) or u
            actual.codigo = Codigo(proposito=proposito, hash=_huella_codigo(u.usuario_id, proposito, codigo),
                                   expira=ahora() + timedelta(minutes=self.s.codigo_minutos))
            self._guardar(actual)
            return actual

    def _consumir_codigo(self, correo: str, codigo: str, propositos: tuple[str, ...]) -> Usuario:
        """La cuenta con el código ya consumido (sin guardar): quien llama la completa y la guarda."""
        codigo = codigo.strip()
        with self._candado:
            u = self.por_correo(correo)
            c = u.codigo if u else None
            if u is None or c is None or c.proposito not in propositos:
                raise CodigoInvalido("No hay un código pendiente para ese correo. Pide uno nuevo.")
            if ahora() > c.expira:
                u.codigo = None
                self._guardar(u)
                raise CodigoInvalido("El código venció. Pide uno nuevo.")
            if not hmac.compare_digest(_huella_codigo(u.usuario_id, c.proposito, codigo), c.hash):
                c.intentos += 1
                restantes = self.s.codigo_intentos - c.intentos
                if restantes <= 0:
                    u.codigo = None
                self._guardar(u)
                raise CodigoInvalido(f"Código incorrecto. Te quedan {restantes} intentos." if restantes > 0
                                     else "Código incorrecto. Pide uno nuevo.")
            u.codigo = None
            return u

    # ------------------------------------------------------------ registro

    def registrar(self, nombre: str, correo: str, contrasena: str) -> Usuario:
        """Crea la cuenta sin verificar y le manda el código. Un registro que no se terminó
        (correo sin verificar) se puede repetir: cambia nombre y contraseña."""
        correo = normalizar_correo(correo)
        cifrada = cifrar(contrasena)
        with self._candado:
            u = self.por_correo(correo)
            if u and u.verificado:
                raise CorreoEnUso("Ya hay una cuenta con ese correo. Entra o restablece tu contraseña.")
            if u:
                u.nombre, u.contrasena = nombre, cifrada
                self._guardar(u)
            else:
                u = Usuario.model_validate(self.repo.crear_doc(COLECCION, "U", lambda uid: Usuario(
                    usuario_id=uid, nombre=nombre, correo=correo, contrasena=cifrada).model_dump(mode="json")))
        return self._enviar_codigo(u, "registro")

    def verificar(self, correo: str, codigo: str) -> Usuario:
        """Código de registro (confirma el correo) o de entrar (segundo factor)."""
        with self._candado:
            u = self._consumir_codigo(correo, codigo, ("registro", "entrar"))
            u.verificado, u.fallos, u.bloqueado_hasta = True, 0, None
            self._guardar(u)
            return u

    def reenviar(self, correo: str) -> None:
        """Otro código para lo que la cuenta tenga pendiente. No dice si el correo existe."""
        u = self.por_correo(correo)
        if u is None:
            return
        proposito = u.codigo.proposito if u.codigo else ("registro" if not u.verificado else None)
        if proposito:
            self._enviar_codigo(u, proposito, exigir_espera=True)

    # ------------------------------------------------------------ entrar

    def entrar(self, correo: str, contrasena: str) -> tuple[Usuario, bool]:
        """(cuenta, falta_codigo). `falta_codigo` es True si se le mandó un código para entrar."""
        with self._candado:
            u = self.por_correo(correo)
            if u is None:
                verificar(contrasena, CIFRADA_FICTICIA)  # mismo tiempo que con una cuenta real
                raise CredencialesInvalidas("Correo o contraseña incorrectos.")
            ya = ahora()
            if u.bloqueado_hasta and ya < u.bloqueado_hasta:
                minutos = max(1, int((u.bloqueado_hasta - ya).total_seconds() // 60) + 1)
                raise CuentaBloqueada(f"Demasiados intentos. Espera {minutos} min o restablece tu contraseña.")
            if not verificar(contrasena, u.contrasena):
                u.fallos += 1
                if u.fallos >= FALLOS_PARA_BLOQUEO:
                    u.fallos, u.bloqueado_hasta = 0, ya + BLOQUEO
                self._guardar(u)
                raise CredencialesInvalidas("Correo o contraseña incorrectos.")
            u.fallos, u.bloqueado_hasta = 0, None
            self._guardar(u)
        if not u.verificado:
            self._enviar_codigo(u, "registro")
            raise SinVerificar("Confirma tu correo: te enviamos un código.")
        if self.s.auth_codigo_al_entrar:
            self._enviar_codigo(u, "entrar")
            return u, True
        return u, False

    # ------------------------------------------------------------ restablecer

    def recuperar(self, correo: str) -> None:
        """Manda un código para elegir otra contraseña. No dice si el correo existe."""
        u = self.por_correo(correo)
        if u is not None:
            self._enviar_codigo(u, "restablecer")

    def restablecer(self, correo: str, codigo: str, contrasena: str) -> Usuario:
        cifrada = cifrar(contrasena)
        with self._candado:
            u = self._consumir_codigo(correo, codigo, ("restablecer",))
            u.contrasena, u.verificado, u.sesiones = cifrada, True, []  # las sesiones abiertas se cierran
            u.fallos, u.bloqueado_hasta = 0, None
            self._guardar(u)
            return u

    # ------------------------------------------------------------ sesiones

    def abrir_sesion(self, u: Usuario) -> str:
        """El valor de la cookie: `<usuario_id>.<token>`."""
        token = secrets.token_urlsafe(32)
        with self._candado:
            actual = self.obtener(u.usuario_id) or u
            ya = ahora()
            vigentes = [x for x in actual.sesiones if x.expira > ya][-(MAX_SESIONES - 1):]
            actual.sesiones = vigentes + [Sesion(hash=huella(token), expira=ya + timedelta(days=self.s.sesion_dias))]
            self._guardar(actual)
        return f"{u.usuario_id}.{token}"

    def sesion(self, valor: str | None) -> Usuario | None:
        """La cuenta de una cookie vigente, o None."""
        usuario_id, _, token = (valor or "").partition(".")
        if not token:
            return None
        u = self.obtener(usuario_id)
        if u is None or not u.verificado:
            return None
        h, ya = huella(token), ahora()
        return u if any(hmac.compare_digest(x.hash, h) and x.expira > ya for x in u.sesiones) else None

    def cerrar_sesion(self, valor: str | None) -> None:
        usuario_id, _, token = (valor or "").partition(".")
        with self._candado:
            u = self.obtener(usuario_id) if token else None
            if u is None:
                return
            h = huella(token)
            quedan = [x for x in u.sesiones if not hmac.compare_digest(x.hash, h)]
            if len(quedan) != len(u.sesiones):
                u.sesiones = quedan
                self._guardar(u)
