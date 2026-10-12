"""Envío por SMTP con un servidor falso: Gmail, errores de autenticación y la prueba."""
import smtplib

import pytest

import app.auth.correo as modulo
from app.auth import Correo, ErrorCorreo
from app.config import Settings


class SMTPFalso:
    """Registra lo que haría smtplib.SMTP; `rechazar` simula una contraseña incorrecta."""
    ultimo = None
    rechazar = False

    def __init__(self, host, puerto, timeout=None):
        self.host, self.puerto, self.tls, self.credenciales, self.enviados = host, puerto, False, None, []
        SMTPFalso.ultimo = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, usuario, contrasena):
        if SMTPFalso.rechazar:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        self.credenciales = (usuario, contrasena)

    def send_message(self, mensaje):
        self.enviados.append(mensaje)


@pytest.fixture
def smtp(monkeypatch):
    SMTPFalso.ultimo, SMTPFalso.rechazar = None, False
    monkeypatch.setattr(modulo.smtplib, "SMTP", SMTPFalso)
    return SMTPFalso


def _gmail(**ajustes):
    return Settings(_env_file=None, smtp_host="smtp.gmail.com", smtp_puerto=587, smtp_seguridad="starttls",
                    smtp_usuario="remitente@gmail.com", smtp_contrasena="abcd efgh ijkl mnop", **ajustes)


def test_gmail_con_contrasena_de_aplicacion_pegada_con_espacios(smtp):
    Correo(_gmail(smtp_remitente="Dudamel <remitente@gmail.com>")).enviar_codigo(
        "ana@ejemplo.mx", "Ana", "123456", "registro", 15)
    c = smtp.ultimo
    assert (c.host, c.puerto, c.tls) == ("smtp.gmail.com", 587, True)
    assert c.credenciales == ("remitente@gmail.com", "abcdefghijklmnop")
    m = c.enviados[0]
    assert (m["From"], m["To"], m["Subject"]) == ("Dudamel <remitente@gmail.com>", "ana@ejemplo.mx",
                                                  "Confirma tu cuenta de Dudamel")
    assert "123456" in m.get_content()


def test_otro_servidor_conserva_los_espacios_de_la_contrasena(smtp):
    s = Settings(_env_file=None, smtp_host="correo.ejemplo.mx", smtp_usuario="u", smtp_contrasena="con espacio")
    Correo(s).enviar_prueba("ana@ejemplo.mx")
    assert smtp.ultimo.credenciales == ("u", "con espacio")
    assert smtp.ultimo.enviados[0]["From"] == "u"  # sin SMTP_REMITENTE, el usuario


def test_contrasena_rechazada_dice_que_use_una_de_aplicacion(smtp):
    smtp.rechazar = True
    with pytest.raises(ErrorCorreo, match="contraseña de aplicación") as e:
        Correo(_gmail()).enviar_prueba("ana@ejemplo.mx")
    assert isinstance(e.value.__cause__, smtplib.SMTPAuthenticationError)


def test_sin_smtp_la_prueba_falla_y_el_codigo_va_a_la_consola(smtp, caplog):
    correo = Correo(Settings(_env_file=None))
    with pytest.raises(ErrorCorreo, match="SMTP_HOST"):
        correo.enviar_prueba("ana@ejemplo.mx")
    correo.enviar_codigo("ana@ejemplo.mx", "Ana", "654321", "registro", 15)
    assert smtp.ultimo is None and "654321" in caplog.text
