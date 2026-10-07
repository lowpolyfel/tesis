"""Cola de un solo trabajador: prioridad, orden de llegada y fallas aisladas."""
import threading

from app.orchestration.cola import Cola


def test_prioridad_y_orden_de_llegada():
    cola, hechos, puerta, ocupado = Cola(), [], threading.Event(), threading.Event()
    cola.encolar("ejecutar", "bloqueo", lambda: (ocupado.set(), puerta.wait()))
    cola.iniciar()
    assert ocupado.wait(5)  # el trabajador está ocupado mientras se encola lo demás
    for tipo, clave in [("ejecutar", "R01"), ("analisis", "C01"), ("ejecutar", "R02"), ("reanudar", "R09"),
                        ("continuar", "R05")]:
        cola.encolar(tipo, clave, lambda c=clave: hechos.append(c))
    estado = cola.estado()
    assert estado["en_proceso"] == {"tipo": "ejecutar", "clave": "bloqueo"}
    assert [p["clave"] for p in estado["pendientes"]] == ["R09", "R05", "R01", "R02", "C01"]
    puerta.set()
    assert cola.esperar(5)
    assert hechos == ["R09", "R05", "R01", "R02", "C01"]
    assert cola.estado() == {"en_proceso": None, "pendientes": []}
    cola.detener()


def test_un_trabajo_que_falla_no_detiene_la_cola():
    cola, hechos = Cola(), []
    cola.encolar("ejecutar", "R01", lambda: 1 / 0)
    cola.encolar("ejecutar", "R02", lambda: hechos.append("R02"))
    cola.iniciar()
    assert cola.esperar(5) and hechos == ["R02"]
    cola.detener()
