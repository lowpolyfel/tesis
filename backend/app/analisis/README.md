# analisis

Vistas derivadas de las trazas para el frontend (ADR 0015). Funciones puras: no
llaman a ningún LLM ni al repositorio; las rutas de `api/routes/analisis.py`
leen y delegan.

| Archivo | Qué hace |
|---|---|
| `traza.py` | Mensajes efectivos (sin repetidos tras un reinicio) y configuración normalizada |
| `requisito.py` | `vista_requisito` (por término, con I1..In) y `resumen_requisito` |
| `proyecto.py` | `resumen_proyecto`, `ambiguedades_proyecto`, `flujo_proyecto` (fases KMoS-SSA) |
| `configuracion.py` | Configuración vigente y catálogos, de solo lectura |
| `formas.py` | Forma exacta de cada vista (Pydantic, `response_model` de las rutas) |

| Método | Ruta | Forma |
|---|---|---|
| GET | `/requisitos/{req_id}` | `VistaRequisito` |
| GET | `/proyectos/{proyecto_id}/resumen` | `ResumenProyecto` |
| GET | `/proyectos/{proyecto_id}/ambiguedades` | `AmbiguedadesProyecto` |
| GET | `/proyectos/{proyecto_id}/flujo` | `FlujoProyecto` |
| GET | `/configuracion` | `Configuracion` |
| GET | `/catalogos` | `Catalogos` |
