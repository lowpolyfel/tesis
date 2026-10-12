"""Envío del código de seguridad por correo (SMTP, biblioteca estándar).

Se configura en el `.env` de la raíz (`SMTP_HOST`, `SMTP_PUERTO`, `SMTP_USUARIO`,
`SMTP_CONTRASENA`, `SMTP_REMITENTE`, `SMTP_SEGURIDAD`). Sin `SMTP_HOST` (desarrollo)
el correo no sale: el código se escribe en el registro del backend con nivel WARNING.
`scripts/probar_correo.py` prueba la configuración sin abrir la app.

Gmail: `smtp.gmail.com`, puerto 587, `starttls` y una contraseña de aplicación de la
cuenta (requiere la verificación en dos pasos); la contraseña normal no sirve.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger(__name__)

ASUNTOS = {
    "registro": "Confirma tu cuenta de Dudamel",
    "entrar": "Tu código para entrar a Dudamel",
    "restablecer": "Restablece tu contraseña de Dudamel",
}
PARA_QUE = {
    "registro": "confirmar tu cuenta",
    "entrar": "entrar a tu cuenta",
    "restablecer": "elegir una contraseña nueva",
}


class ErrorCorreo(Exception):
    """El servidor SMTP no aceptó el correo (configuración o red)."""


class Correo:
    def __init__(self, settings: Settings):
        self.s = settings

    @property
    def configurado(self) -> bool:
        return bool(self.s.smtp_host)

    @property
    def remitente(self) -> str:
        return self.s.smtp_remitente or self.s.smtp_usuario or "dudamel@localhost"

    def _contrasena(self) -> str:
        """Google muestra la contraseña de aplicación en grupos («abcd efgh ijkl mnop»):
        se acepta pegada con o sin espacios."""
        c = self.s.smtp_contrasena or ""
        return c.replace(" ", "") if (self.s.smtp_host or "").strip().lower().endswith("gmail.com") else c

    def _mensaje(self, destino: str, nombre: str, codigo: str, proposito: str, minutos: int) -> EmailMessage:
        m = EmailMessage()
        m["Subject"] = ASUNTOS[proposito]
        m["From"] = self.remitente
        m["To"] = destino
        m.set_content(
            f"Hola, {nombre}:\n\n"
            f"Tu código para {PARA_QUE[proposito]} es:\n\n    {codigo}\n\n"
            f"Vence en {minutos} minutos. Si no lo pediste, ignora este correo: nadie puede entrar sin él.\n\n"
            "Dudamel\n")
        return m

    def enviar_codigo(self, destino: str, nombre: str, codigo: str, proposito: str, minutos: int) -> None:
        if not self.configurado:
            log.warning("SMTP_HOST no está configurado: el correo no se envía. Código de %s para %s: %s",
                        proposito, destino, codigo)
            return
        self._enviar(self._mensaje(destino, nombre, codigo, proposito, minutos))

    def enviar_prueba(self, destino: str) -> None:
        """Un correo de prueba por el mismo camino que los códigos (scripts/probar_correo.py)."""
        if not self.configurado:
            raise ErrorCorreo("SMTP_HOST no está configurado: el backend no envía correos.")
        m = EmailMessage()
        m["Subject"] = "Prueba de correo de Dudamel"
        m["From"] = self.remitente
        m["To"] = destino
        m.set_content("Si lees esto, el backend ya puede enviar los códigos de seguridad.\n\nDudamel\n")
        self._enviar(m)

    def _enviar(self, mensaje: EmailMessage) -> None:
        s = self.s
        contexto = ssl.create_default_context()
        try:
            if s.smtp_seguridad == "ssl":
                conexion = smtplib.SMTP_SSL(s.smtp_host, s.smtp_puerto, context=contexto, timeout=20)
            else:
                conexion = smtplib.SMTP(s.smtp_host, s.smtp_puerto, timeout=20)
            with conexion:
                if s.smtp_seguridad == "starttls":
                    conexion.starttls(context=contexto)
                if s.smtp_usuario:
                    conexion.login(s.smtp_usuario, self._contrasena())
                conexion.send_message(mensaje)
        except smtplib.SMTPAuthenticationError as e:
            log.error("El servidor de correo %s rechazó a %s (%s: %s)", s.smtp_host, s.smtp_usuario, type(e).__name__, e)
            raise ErrorCorreo("El servidor de correo rechazó SMTP_USUARIO o SMTP_CONTRASENA. En Gmail se usa una "
                              "contraseña de aplicación, no la contraseña normal de la cuenta.") from e
        except (smtplib.SMTPException, OSError) as e:
            log.error("No se pudo enviar el correo a %s por %s:%s (%s: %s)", mensaje["To"], s.smtp_host, s.smtp_puerto,
                      type(e).__name__, e)
            raise ErrorCorreo("No se pudo enviar el correo con el código. Revisa la configuración SMTP del "
                              "backend (SMTP_HOST, SMTP_USUARIO, SMTP_CONTRASENA).") from e
