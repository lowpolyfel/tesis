/*
 * Transporte con el backend (FastAPI). Todas las llamadas pasan por aquí.
 * VITE_API_URL permite apuntar a otro servidor; por omisión, localhost:8000.
 */
export const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/* El backend responde errores como { detail }; se convierten en Error con ese texto */
async function leer(r) {
  const tipo = r.headers.get("content-type") ?? "";
  const cuerpo = tipo.includes("application/json") ? await r.json().catch(() => null) : await r.text().catch(() => null);
  if (!r.ok) {
    const d = cuerpo?.detail;
    const texto = typeof d === "string" ? d
      : Array.isArray(d) ? d.map((x) => `${(x.loc ?? []).slice(1).join(".")}: ${x.msg}`).join("; ")
        : d?.mensaje ? [d.mensaje, ...(d.errores ?? [])].join(" · ") // p. ej. corpus inválido
          : `HTTP ${r.status}`;
    const e = new Error(texto);
    e.status = r.status;
    e.detalle = d;
    throw e;
  }
  return cuerpo;
}

async function pedir(metodo, ruta, { cuerpo, form, params } = {}) {
  const url = new URL(BASE_URL + ruta);
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  const opciones = { method: metodo, headers: {} };
  if (form) opciones.body = form;
  else if (cuerpo !== undefined) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  let r;
  try {
    r = await fetch(url, opciones);
  } catch {
    throw new Error(`No hay conexión con el backend en ${BASE_URL}. ¿Está corriendo uvicorn?`);
  }
  return leer(r);
}

export const get = (ruta, params) => pedir("GET", ruta, { params });
export const post = (ruta, cuerpo) => pedir("POST", ruta, { cuerpo });
export const patch = (ruta, cuerpo) => pedir("PATCH", ruta, { cuerpo });
export const postArchivo = (ruta, campo, archivo) => {
  const form = new FormData();
  form.append(campo, archivo);
  return pedir("POST", ruta, { form });
};
