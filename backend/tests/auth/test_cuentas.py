"""Cuentas sin HTTP: registro con código, entrar, bloqueo, restablecer y sesiones."""
from datetime import timedelta

import pytest

from app.auth import (
    CodigoInvalido,
    CorreoEnUso,
    CredencialesInvalidas,
    CuentaBloqueada,
    Cuentas,
    EsperaReenvio,
    SinVerificar,
)
from app.auth.contrasenas import cifrar, verificar
from app.auth.cuentas import FALLOS_PARA_BLOQUEO
from app.config import Settings
from app.db import RepositorioJson
from app.models import ahora
from tests.fakes import CorreoFalso

CORREO = "ana@ejemplo.mx"
CLAVE = "una-clave-larga"


@pytest.fixture
def cuentas(tmp_path):
    s = Settings(_env_file=None, codigo_reenvio_s=60, codigo_intentos=3)
    return Cuentas(RepositorioJson(tmp_path), s, CorreoFalso())


def _registrar(cuentas, correo=CORREO):
    cuentas.registrar("Ana", f"  {correo.upper()} ", CLAVE)
    return cuentas.correo.ultimo(correo)


def test_contrasena_con_sal_y_verificacion():
    a, b = cifrar(CLAVE), cifrar(CLAVE)
    assert a != b and a.startswith("scrypt$") and CLAVE not in a
    assert verificar(CLAVE, a) and not verificar("otra-clave", a) and not verificar(CLAVE, "basura")


def test_registro_pide_codigo_y_lo_verifica(cuentas):
    codigo = _registrar(cuentas)
    u = cuentas.por_correo(CORREO)
    assert (u.correo, u.verificado) == (CORREO, False) and u.codigo.proposito == "registro"
    assert codigo not in u.model_dump_json()  # solo se guarda el hash
    with pytest.raises(SinVerificar):
        cuentas.entrar(CORREO, CLAVE)
    u = cuentas.verificar(CORREO, codigo)
    assert u.verificado and u.codigo is None
    assert cuentas.entrar(CORREO, CLAVE)[0].usuario_id == u.usuario_id
    with pytest.raises(CorreoEnUso):
        cuentas.registrar("Otra", CORREO, CLAVE)


def test_codigo_incorrecto_vencido_y_con_intentos_limitados(cuentas):
    codigo = _registrar(cuentas)
    otro = "000000" if codigo != "000000" else "111111"
    with pytest.raises(CodigoInvalido, match="Te quedan 2"):
        cuentas.verificar(CORREO, otro)
    with pytest.raises(CodigoInvalido, match="Te quedan 1"):
        cuentas.verificar(CORREO, otro)
    with pytest.raises(CodigoInvalido, match="Pide uno nuevo"):
        cuentas.verificar(CORREO, otro)
    with pytest.raises(CodigoInvalido, match="No hay un código"):  # se agotaron: ya ni el correcto sirve
        cuentas.verificar(CORREO, codigo)

    u = cuentas.por_correo(CORREO)
    u.codigo = None
    cuentas._guardar(u)
    codigo = _registrar(cuentas)
    u = cuentas.por_correo(CORREO)
    u.codigo.expira = ahora() - timedelta(seconds=1)
    cuentas._guardar(u)
    with pytest.raises(CodigoInvalido, match="venció"):
        cuentas.verificar(CORREO, codigo)


def test_reenviar_espera_entre_codigos(cuentas):
    _registrar(cuentas)
    with pytest.raises(EsperaReenvio) as e:
        cuentas.reenviar(CORREO)
    assert 0 < e.value.segundos <= 60
    u = cuentas.por_correo(CORREO)
    u.codigo.enviado = ahora() - timedelta(seconds=61)
    cuentas._guardar(u)
    cuentas.reenviar(CORREO)
    assert len(cuentas.correo.enviados) == 2
    cuentas.reenviar("nadie@ejemplo.mx")  # no revela si existe
    assert len(cuentas.correo.enviados) == 2


def test_contrasena_incorrecta_y_bloqueo(cuentas):
    cuentas.verificar(CORREO, _registrar(cuentas))
    with pytest.raises(CredencialesInvalidas):
        cuentas.entrar("nadie@ejemplo.mx", CLAVE)
    for _ in range(FALLOS_PARA_BLOQUEO):
        with pytest.raises(CredencialesInvalidas):
            cuentas.entrar(CORREO, "incorrecta")
    with pytest.raises(CuentaBloqueada):
        cuentas.entrar(CORREO, CLAVE)


def test_restablecer_cambia_la_contrasena_y_cierra_las_sesiones(cuentas):
    u = cuentas.verificar(CORREO, _registrar(cuentas))
    cookie = cuentas.abrir_sesion(u)
    assert cuentas.sesion(cookie).usuario_id == u.usuario_id
    cuentas.recuperar(CORREO)
    cuentas.recuperar("nadie@ejemplo.mx")
    codigo = cuentas.correo.ultimo(CORREO)
    cuentas.restablecer(CORREO, codigo, "clave-nueva-123")
    assert cuentas.sesion(cookie) is None
    with pytest.raises(CredencialesInvalidas):
        cuentas.entrar(CORREO, CLAVE)
    assert cuentas.entrar(CORREO, "clave-nueva-123")[0].usuario_id == u.usuario_id


def test_sesiones_se_cierran_y_no_aceptan_tokens_falsos(cuentas):
    u = cuentas.verificar(CORREO, _registrar(cuentas))
    a, b = cuentas.abrir_sesion(u), cuentas.abrir_sesion(u)
    assert cuentas.sesion(a) and cuentas.sesion(b)
    for falsa in (None, "", "U01", "U01.", f"{u.usuario_id}.otro", "../U01.x", a + "x"):
        assert cuentas.sesion(falsa) is None
    cuentas.cerrar_sesion(a)
    assert cuentas.sesion(a) is None and cuentas.sesion(b)
    assert all(a.split(".", 1)[1] not in s.hash for s in cuentas.obtener(u.usuario_id).sesiones)


def test_codigo_al_entrar(tmp_path):
    cuentas = Cuentas(RepositorioJson(tmp_path), Settings(_env_file=None, auth_codigo_al_entrar=True), CorreoFalso())
    cuentas.verificar(CORREO, _registrar(cuentas))
    u, falta = cuentas.entrar(CORREO, CLAVE)
    assert falta and cuentas.correo.enviados[-1]["proposito"] == "entrar"
    assert cuentas.verificar(CORREO, cuentas.correo.ultimo(CORREO)).usuario_id == u.usuario_id
