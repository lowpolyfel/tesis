"""Cuentas por HTTP con la cookie de verdad: registro, código, sesión, salir, y que cada
cuenta solo vea y borre lo suyo."""
import pytest
from fastapi.testclient import TestClient

from app.api.dependencias import COOKIE_SESION
from app.api.main import create_app
from tests.escenarios import SESION, guiones_sesion_cercana, montar
from tests.fakes import CorreoFalso

CLAVE = "una-clave-larga"


@pytest.fixture
def srv(tmp_path, analizador):
    guiones = {k: v * 3 for k, v in guiones_sesion_cercana().items()}
    srv, _, _ = montar(tmp_path, analizador, guiones, validacion_humana="si_hay_arbitraje")
    srv.cuentas.correo = CorreoFalso()
    return srv


def _cuenta(srv, correo: str) -> TestClient:
    """Un navegador con sesión abierta en una cuenta nueva."""
    c = TestClient(create_app(srv))
    r = c.post("/auth/registro", json={"nombre": "Ana", "correo": correo, "contrasena": CLAVE})
    assert r.status_code == 201 and r.json()["pendiente"] == "registro", r.text
    r = c.post("/auth/verificar", json={"correo": correo, "codigo": srv.cuentas.correo.ultimo(correo)})
    assert r.status_code == 200 and r.json()["correo"] == correo
    return c


def test_sin_sesion_todo_responde_401_salvo_auth_y_salud(srv):
    c = TestClient(create_app(srv))
    for ruta in ("/proyectos", "/trazas", "/cola", "/lel", "/configuracion", "/conexion", "/auth/yo"):
        assert c.get(ruta).status_code == 401, ruta
    assert c.get("/salud").status_code == 200
    c.cookies.set(COOKIE_SESION, "U01.token-inventado")
    assert c.get("/proyectos").status_code == 401


def test_registro_codigo_sesion_y_salir(srv):
    c = TestClient(create_app(srv))
    datos = {"nombre": "Ana", "correo": "Ana@Ejemplo.mx", "contrasena": CLAVE}
    assert c.post("/auth/registro", json={**datos, "contrasena": "corta"}).status_code == 422
    assert c.post("/auth/registro", json={**datos, "correo": "sin-arroba"}).status_code == 422
    r = c.post("/auth/registro", json=datos)
    assert r.status_code == 201 and r.json() == {"pendiente": "registro", "correo": "ana@ejemplo.mx",
                                                  "sin_smtp": False, "minutos": 15}
    r = c.post("/auth/entrar", json={"correo": "ana@ejemplo.mx", "contrasena": CLAVE})
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "sin_verificar"
    r = c.post("/auth/verificar", json={"correo": "ana@ejemplo.mx", "codigo": "12345"})
    assert r.status_code == 422
    codigo = srv.cuentas.correo.ultimo("ana@ejemplo.mx")
    r = c.post("/auth/verificar", json={"correo": "ana@ejemplo.mx", "codigo": codigo})
    assert r.status_code == 200 and set(r.json()) == {"usuario_id", "nombre", "correo", "creado"}
    cookie = r.cookies.get(COOKIE_SESION)
    assert cookie and "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert c.get("/auth/yo").json()["nombre"] == "Ana"
    assert c.get("/proyectos").json() == []  # una cuenta nueva empieza sin proyectos

    assert c.post("/auth/salir").status_code == 204
    assert c.get("/proyectos").status_code == 401
    otra = TestClient(create_app(srv))
    otra.cookies.set(COOKIE_SESION, cookie)  # la cookie robada tras salir ya no sirve
    assert otra.get("/auth/yo").status_code == 401

    r = c.post("/auth/entrar", json={"correo": "ana@ejemplo.mx", "contrasena": "incorrecta"})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "credenciales"
    r = c.post("/auth/entrar", json={"correo": "ANA@ejemplo.mx", "contrasena": CLAVE})
    assert r.status_code == 200 and c.get("/auth/yo").status_code == 200
    r = c.post("/auth/registro", json=datos)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "correo_en_uso"


def test_restablecer_por_http(srv):
    c = _cuenta(srv, "ana@ejemplo.mx")
    assert c.post("/auth/recuperar", json={"correo": "nadie@ejemplo.mx"}).status_code == 202
    assert c.post("/auth/recuperar", json={"correo": "ana@ejemplo.mx"}).status_code == 202
    r = c.post("/auth/reenviar", json={"correo": "ana@ejemplo.mx"})
    assert r.status_code == 429 and r.json()["detail"]["segundos"] > 0
    codigo = srv.cuentas.correo.ultimo("ana@ejemplo.mx")
    r = c.post("/auth/restablecer", json={"correo": "ana@ejemplo.mx", "codigo": codigo, "contrasena": "clave-nueva-9"})
    assert r.status_code == 200
    assert c.post("/auth/entrar", json={"correo": "ana@ejemplo.mx", "contrasena": "clave-nueva-9"}).status_code == 200


def test_cada_cuenta_ve_y_borra_solo_lo_suyo(srv):
    ana, beto = _cuenta(srv, "ana@ejemplo.mx"), _cuenta(srv, "beto@ejemplo.mx")
    p = ana.post("/proyectos", json={"nombre": "Caja", "contexto": "Ferretería"}).json()
    pid = p["proyecto_id"]
    assert p["propietario"] == ana.get("/auth/yo").json()["usuario_id"]
    req = ana.post(f"/proyectos/{pid}/requisitos", json={"requisitos": [{"texto": SESION}]}).json()["req_ids"][0]
    srv.cola.iniciar()
    assert srv.cola.esperar(10)

    assert [x["proyecto_id"] for x in ana.get("/proyectos").json()] == [pid]
    assert beto.get("/proyectos").json() == []
    for metodo, ruta in (("get", f"/proyectos/{pid}"), ("get", f"/proyectos/{pid}/resumen"),
                         ("patch", f"/proyectos/{pid}"), ("delete", f"/proyectos/{pid}"),
                         ("get", f"/requisitos/{req}"), ("get", f"/traza/{req}"), ("get", f"/eventos/{req}"),
                         ("delete", f"/requisitos/{req}"), ("get", f"/trazas?proyecto_id={pid}"),
                         ("get", f"/lel?proyecto_id={pid}")):
        kwargs = {"json": {"nombre": "X"}} if metodo == "patch" else {}
        assert getattr(beto, metodo)(ruta, **kwargs).status_code == 404, ruta
    assert beto.post("/procesar", json={"texto": SESION, "proyecto_id": pid}).status_code == 404
    assert beto.get("/trazas").json() == [] and beto.get("/lel").json() == []
    assert [t["req_id"] for t in ana.get("/trazas").json()] == [req]
    assert ana.get("/lel").json() and ana.get(f"/requisitos/{req}").status_code == 200

    assert ana.patch(f"/proyectos/{pid}", json={"nombre": "Caja nueva"}).json()["nombre"] == "Caja nueva"
    assert ana.delete(f"/proyectos/{pid}").status_code == 204
    assert ana.get(f"/proyectos/{pid}").status_code == 404 and ana.get("/proyectos").json() == []
    assert srv.traza(req) is None and srv.repo.listar_lel(pid) == []
    assert srv.repo.obtener_doc("formalizados", req) is None
    assert not srv.grafo.get_state({"configurable": {"thread_id": req}}).values  # sin checkpoint
    srv.cola.detener()


def test_borrar_un_requisito_y_no_si_esta_en_proceso(srv):
    c = _cuenta(srv, "ana@ejemplo.mx")
    pid = c.post("/proyectos", json={"nombre": "Caja"}).json()["proyecto_id"]
    a, b = srv.procesar(SESION, pid), srv.procesar(SESION, pid)
    assert a in {e.req_id for e in srv.repo.listar_lel(pid)}
    assert c.delete(f"/requisitos/{a}").status_code == 204
    assert c.get(f"/traza/{a}").status_code == 404
    assert a not in {e.req_id for e in srv.repo.listar_lel(pid)}  # lo que salió de él también se va
    assert srv.repo.obtener_doc("formalizados", a) is None
    assert [t["req_id"] for t in c.get(f"/proyectos/{pid}/requisitos").json()] == [b]

    srv._reservar(b)  # como si estuviera en la cola
    r = c.delete(f"/requisitos/{b}")
    assert r.status_code == 409 and b in r.json()["detail"]
    assert c.delete(f"/proyectos/{pid}").status_code == 409
    srv._liberar(b)
    assert c.delete(f"/proyectos/{pid}").status_code == 204
