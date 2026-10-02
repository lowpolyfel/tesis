# frontend

Interfaz en React + Vite + React Router + Tailwind de **Dudamel**. Tiene dos
trabajos: observar cómo negocian los agentes y permitir que una persona valide
los artefactos. Todavía **no está conectada al backend**: todo funciona con
datos de prueba.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

## Rutas

| Ruta | Pantalla |
|---|---|
| `/` | Portada (orbe, login y registro sin validación) → `/cola` |
| `/cargar` | 1. Carga de requisitos (texto, .txt o .pdf) y confirmación de la separación |
| `/cola` | 2. Cola de requisitos con filtro `?estado=` |
| `/requisitos/:id` | 3 y 4. Traza completa y panel de debate (`?figura=1` para capturas) |
| `/requisitos/:id/validacion` | 5. Validación y edición de artefactos |
| `/lel` | 6. LEL acumulado (`?q=`, `?tipo=`) |
| `/catalogos/:tipo` | 7. Catálogos `mexicanismos` y `vaguedad` |
| `/calibracion` | 8. Umbral, rondas y modelo por agente |
| `/evaluacion` | 9. Corpus contra ground truth |

## Dónde está cada cosa

- `src/constants/estados.js`: máquina de estados, **única fuente de verdad**
  (estados, transiciones, etiquetas y colores).
- `src/services/api.js`: **todas** las llamadas al backend. Hoy son stubs; cada
  función indica el endpoint previsto. Al conectar FastAPI solo cambia este archivo.
- `src/services/polling.js`: sondeo del estado (el proceso tarda segundos).
- `src/services/mockDb.js` y `simulacion.js`: base y proceso simulados; solo los
  usa `api.js` y desaparecen con el backend.
- `src/fixtures/`: datos de prueba. Casos clave: REQ-001 (directo),
  REQ-002 (consenso en ronda 1), REQ-003 (arbitraje).

Los cambios hechos en la interfaz se guardan en localStorage. «Restaurar datos
de prueba» (menú lateral) vuelve al estado inicial y relanza los requisitos que
se ven procesándose en vivo.
