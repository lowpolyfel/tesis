"""Prueba la configuración de correo (SMTP_* del .env) sin abrir la app.

Uso (desde la raíz del repo, con el venv del backend activo):

    python scripts/probar_correo.py                    # el correo de prueba va a SMTP_USUARIO
    python scripts/probar_correo.py otra@ejemplo.com

Muestra la configuración que leyó y de dónde salió (nunca la contraseña) y envía un
correo de prueba por el mismo camino que los códigos de seguridad. Si falla, dice
qué respondió el servidor de correo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth import Correo, ErrorCorreo  # noqa: E402
from app.config import fuente_de, get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    correo = Correo(s)
    contrasena = correo._contrasena()
    print("Configuración de correo que lee el backend:")
    for nombre, valor in (("SMTP_HOST", s.smtp_host), ("SMTP_PUERTO", s.smtp_puerto),
                          ("SMTP_SEGURIDAD", s.smtp_seguridad), ("SMTP_USUARIO", s.smtp_usuario),
                          ("SMTP_CONTRASENA", f"configurada ({len(contrasena)} caracteres)" if contrasena else None),
                          ("SMTP_REMITENTE", s.smtp_remitente)):
        print(f"  {nombre:<16} {valor or '(vacío)'}   ← {fuente_de(nombre)}")

    destino = sys.argv[1] if len(sys.argv) > 1 else s.smtp_usuario
    if not s.smtp_host:
        print("\nFalta SMTP_HOST en el .env de la raíz: el backend escribe los códigos en su consola.")
        return 1
    if not destino:
        print("\nIndica a qué correo mandar la prueba: python scripts/probar_correo.py tu@correo.com")
        return 1
    try:
        correo.enviar_prueba(destino)
    except ErrorCorreo as e:
        causa = e.__cause__
        print(f"\nNo se pudo enviar: {e}")
        if causa is not None:
            print(f"Respuesta del servidor: {type(causa).__name__}: {causa}")
        return 1
    print(f"\nListo: se envió un correo de prueba a {destino}. Si no está en la bandeja de entrada, revisa spam.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
