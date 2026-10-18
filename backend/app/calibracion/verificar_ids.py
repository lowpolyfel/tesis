"""Verifica la identidad de las pruebas de modelos y de las corridas de calibración (ADR 0029).

Desde `backend/`:  python -m app.calibracion.verificar_ids

Dentro de una misma base no puede haber dos documentos con el mismo id, pero sí entre bases: la
copia JSON local (`resultados/`, el respaldo cuando Mongo no responde) y Mongo Atlas numeran cada
una por su cuenta, y antes de la v2.4.0 un id borrado se volvía a usar. Este script lee las dos
fuentes (Mongo solo si responde) y reporta:

- ids que aparecen en las dos con otro contenido (otro uid u otro banco): colisiones;
- pruebas sin uid (creadas antes de la v2.4.0): su código se deriva del id y del banco;
- pruebas cuyo banco ya no coincide con el archivo del banco (huella distinta).

No escribe nada.
"""
from __future__ import annotations

from app.config import get_settings
from app.db.repositorio import RepositorioJson, crear_repositorio

from .pruebas_modelos import COLECCION_PRUEBAS, banco, codigo_de, colisiones, versiones


def fuentes(settings) -> list[tuple[str, object]]:
    salida = [("json local", RepositorioJson(settings.ruta(settings.resultados_dir)))]
    repo = crear_repositorio(settings)
    if not isinstance(repo, RepositorioJson):
        salida.append((repo.descripcion, repo))
    return salida


def informe(docs_por_fuente: list[tuple[str, list[dict]]]) -> dict:
    sin_uid, huella_distinta = [], []
    huellas = {v: banco(v)["huella"] for v in versiones()}
    for nombre, docs in docs_por_fuente:
        for d in docs:
            if d.get("borrada"):
                continue
            if not d.get("uid"):
                sin_uid.append(f"{nombre}: {codigo_de(d)}")
            b = d.get("banco") or {}
            if b.get("version") in huellas and b.get("huella") != huellas[b["version"]]:
                huella_distinta.append(f"{nombre}: {codigo_de(d)} (guardada {str(b.get('huella'))[:12]}, "
                                       f"archivo {huellas[b['version']][:12]})")
    return {"colisiones": colisiones(*docs_por_fuente), "sin_uid": sin_uid, "huella_distinta": huella_distinta}


def main() -> None:
    docs = [(nombre, repo.listar_docs(COLECCION_PRUEBAS)) for nombre, repo in fuentes(get_settings())]
    r = informe(docs)
    print(f"Fuentes: {', '.join(f'{n} ({len(d)} pruebas)' for n, d in docs)}")
    print(f"Colisiones: {len(r['colisiones'])}")
    for c in r["colisiones"]:
        print(f"  {c['prueba_id']}: " + "; ".join(f"{f['fuente']} → {f['codigo']} uid={f['uid'] or '—'}"
                                                   f"{' (borrada)' if f['borrada'] else ''}" for f in c["fuentes"]))
    print(f"Pruebas sin uid (anteriores a la v2.4.0): {len(r['sin_uid'])}")
    for x in r["sin_uid"]:
        print(f"  {x}")
    print(f"Banco con otra huella: {len(r['huella_distinta'])}")
    for x in r["huella_distinta"]:
        print(f"  {x}")


if __name__ == "__main__":
    main()
