"""Hash de contraseñas con scrypt (biblioteca estándar) y sal propia.

Parámetros de OWASP para scrypt: N=2^14, r=8, p=5 (unos 16 MiB por cálculo). El
esquema y los parámetros van en el texto guardado, así que se pueden subir después
sin invalidar las contraseñas existentes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P, LARGO = 2**14, 8, 5, 32
_MAXMEM = 64 * 1024 * 1024


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _de_b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def cifrar(contrasena: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=N, r=R, p=P, dklen=LARGO, maxmem=_MAXMEM)
    return f"scrypt${N}${R}${P}${_b64(sal)}${_b64(h)}"


def verificar(contrasena: str, cifrada: str) -> bool:
    try:
        esquema, n, r, p, sal, esperado = cifrada.split("$")
        if esquema != "scrypt":
            return False
        esperado_b = _de_b64(esperado)
        calculado = hashlib.scrypt(contrasena.encode("utf-8"), salt=_de_b64(sal), n=int(n), r=int(r), p=int(p),
                                   dklen=len(esperado_b), maxmem=_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, esperado_b)


# Para gastar el mismo tiempo cuando el correo no existe (no revela qué cuentas hay)
CIFRADA_FICTICIA = cifrar(secrets.token_urlsafe(16))


def huella(texto: str) -> str:
    """sha256 en hexadecimal: tokens de sesión y códigos (que ya son aleatorios)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
