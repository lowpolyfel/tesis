"""Envío del código de seguridad por correo (SMTP, biblioteca estándar).

Se configura en el `.env` de la raíz (`SMTP_HOST`, `SMTP_PUERTO`, `SMTP_USUARIO`,
`SMTP_CONTRASENA`, `SMTP_REMITENTE`, `SMTP_SEGURIDAD`). Sin `SMTP_HOST` (desarrollo)
el correo no sale: el código se escribe en el registro del backend con nivel WARNING.
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

    def _mensaje(self, destino: str, nombre: str, codigo: str, proposito: str, minutos: int) -> EmailMessage:
        m = EmailMessage()
        m["Subject"] = ASUNTOS[proposito]
        m["From"] = self.s.smtp_remitente or self.s.smtp_usuario or "dudamel@localhost"
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
                    conexion.login(s.smtp_usuario, s.smtp_contrasena or "")
                conexion.send_message(self._mensaje(destino, nombre, codigo, proposito, minutos))
        except (smtplib.SMTPException, OSError) as e:
            log.error("No se pudo enviar el correo a %s por %s:%s (%s: %s)", destino, s.smtp_host, s.smtp_puerto,
                      type(e).__name__, e)
            raise ErrorCorreo("No se pudo enviar el correo con el código. Revisa la configuración SMTP del "
                              "backend (SMTP_HOST, SMTP_USUARIO, SMTP_CONTRASENA).") from e
