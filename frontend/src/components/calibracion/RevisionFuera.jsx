import { useState } from "react";
import { importarRevision, urlExportarRevision } from "../../services/backend";
import { Aviso } from "../ui";

/*
 * Revisar fuera del sistema (ADR 0030). Se descarga un archivo a ciegas (rúbrica, salidas con id
 * opaco S001…, falsos negativos y una plantilla JSON), lo contesta una persona o una IA, y se
 * importa lo que devolvió. Cada marca importada guarda quién la puso; por omisión no se pisa lo
 * marcado en la pantalla y, en lo que se traslapa, se mide el acuerdo (kappa por criterio).
 */
const CLAVE_QUIEN = "dudamel.importa";
const leer = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
const NOMBRES = { fidelidad: "fidelidad", delimitacion: "delimitación", intencion: "intención" };
const fmt = (x) => (x == null ? "—" : x.toFixed(2));

export default function RevisionFuera({ prueba, doc, onImportado }) {
  const marcadas = Object.values(doc?.marcas ?? {}).reduce((s, m) => s + Object.keys(m).length, 0);
  const [pendientes, setPendientes] = useState(marcadas > 0);
  const [descargando, setDescargando] = useState(null);
  const [contenido, setContenido] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [{ tipo, quien }, setQuien] = useState(() => leer(CLAVE_QUIEN, { tipo: "ia", quien: "" }));
  const [sobrescribir, setSobrescribir] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [informe, setInforme] = useState(null);
  const [error, setError] = useState(null);

  const descargar = async (formato) => {
    setDescargando(formato);
    setError(null);
    try {
      const r = await fetch(urlExportarRevision(prueba.prueba_id, { formato, pendientes }), { credentials: "include" });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `No se pudo exportar (HTTP ${r.status}).`);
      const nombre = `revision-${prueba.codigo ?? prueba.prueba_id}${pendientes ? "-pendientes" : ""}.${formato}`;
      const url = URL.createObjectURL(await r.blob());
      Object.assign(document.createElement("a"), { href: url, download: nombre }).click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e); } finally { setDescargando(null); }
  };

  const elegirArchivo = async (f) => {
    setArchivo(f?.name ?? null);
    setContenido(f ? await f.text() : "");
  };

  const importar = async () => {
    setEnviando(true);
    setError(null);
    setInforme(null);
    try {
      try { localStorage.setItem(CLAVE_QUIEN, JSON.stringify({ tipo, quien: quien.trim() })); } catch { /* sin almacenamiento */ }
      const r = await importarRevision(prueba.prueba_id, { contenido, tipo, quien: quien.trim(), sobrescribir });
      setInforme(r);
      setContenido("");
      setArchivo(null);
      onImportado();
    } catch (e) { setError(e); } finally { setEnviando(false); }
  };

  return (
    <div className="grid gap-5 md:grid-cols-2">
      <section className="space-y-3">
        <p className="text-[14px] text-[var(--bone)]">1 · Exportar</p>
        <p className="text-[12.5px] text-[var(--bone-dim)]">
          Un archivo a ciegas: la rúbrica con sus casos frecuentes, cada salida sin el nombre del modelo (S015 es la
          salida 15 de esta pantalla), los falsos negativos y una plantilla JSON. Pégalo en el chat de una IA, o dáselo a
          una persona, y pide que devuelva el bloque JSON de la sección «Respuesta» con cada <code>null</code> contestado.
        </p>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={pendientes} onChange={(e) => setPendientes(e.target.checked)} />
          Solo lo que falta (salidas sin revisar y falsos negativos sin modo)
        </label>
        <div className="flex flex-wrap gap-2">
          <button className="pill sm" disabled={!!descargando} onClick={() => descargar("md")}>
            {descargando === "md" ? "Preparando…" : "Descargar .md"}
          </button>
          <button className="pill ghost sm" disabled={!!descargando} onClick={() => descargar("json")}>
            {descargando === "json" ? "Preparando…" : ".json"}
          </button>
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-[14px] text-[var(--bone)]">2 · Importar lo contestado</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="pill ghost sm cursor-pointer">
            Elegir archivo
            <input type="file" accept=".md,.json,.txt,text/markdown,application/json,text/plain" className="sr-only"
              onChange={(e) => elegirArchivo(e.target.files?.[0])} />
          </label>
          <span className="mono text-[10.5px] text-[var(--bone-faint)]">{archivo ?? "o pega la respuesta abajo"}</span>
        </div>
        <textarea value={contenido} onChange={(e) => { setContenido(e.target.value); setArchivo(null); }} rows={4}
          placeholder="La respuesta de la IA (con o sin texto alrededor) o el JSON contestado"
          className="campo w-full font-mono text-[11.5px]" />
        <div className="flex flex-wrap items-end gap-3">
          <fieldset className="flex items-center gap-3 text-[13px] text-[var(--bone-dim)]">
            <legend className="etiqueta mb-1">Quién lo contestó</legend>
            {[["ia", "Una IA"], ["persona", "Una persona"]].map(([v, t]) => (
              <label key={v} className="flex cursor-pointer items-center gap-1.5">
                <input type="radio" name="tipo" checked={tipo === v} onChange={() => setQuien((q) => ({ ...q, tipo: v }))} />{t}
              </label>
            ))}
          </fieldset>
          <input value={quien} onChange={(e) => setQuien((q) => ({ ...q, quien: e.target.value }))} maxLength={120}
            placeholder={tipo === "ia" ? "Proveedor y modelo (p. ej. google · gemini-2.5-pro)" : "Nombre"}
            aria-label="Nombre o modelo" className="campo min-w-[14rem] flex-1 text-[13px]" />
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={sobrescribir} onChange={(e) => setSobrescribir(e.target.checked)} />
          Pisar lo que ya está marcado (si no, se conserva y se mide el acuerdo)
        </label>
        <Aviso error={error} />
        <button className="pill sm" disabled={enviando || !contenido.trim() || !quien.trim()} onClick={importar}>
          {enviando ? "Importando…" : "Importar"}
        </button>
        {informe && <Informe informe={informe} />}
      </section>

      {doc?.importaciones?.length > 0 && (
        <section className="space-y-1 md:col-span-2">
          <p className="etiqueta">Importaciones</p>
          <ul className="space-y-1 text-[12.5px] text-[var(--bone-dim)]">
            {doc.importaciones.map((x) => (
              <li key={x.numero}>
                <span className="mono mr-2 text-[10.5px] text-[var(--bone-faint)]">#{x.numero} · {x.fecha.slice(0, 16).replace("T", " ")}</span>
                {x.tipo === "ia" ? "IA" : "Persona"} · {x.quien}: {x.aplicadas} aplicadas, {x.conservadas} conservadas
                {x.modos_aplicados ? `, ${x.modos_aplicados} modos de falla` : ""}
                {x.acuerdo && <span className="text-[var(--bone-faint)]"> · {acuerdoTexto(x.acuerdo)}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// iguales/n siempre; la kappa no se define si las dos marcaron todo igual con una sola clase
function acuerdoTexto(a) {
  return `acuerdo con lo que ya había en ${a.fidelidad.n} salidas: ` +
    Object.entries(NOMBRES).map(([k, n]) => `${n} ${Math.round(a[k].acuerdo_observado * a[k].n)}/${a[k].n} (κ ${fmt(a[k].kappa)})`).join(", ") +
    (a.lecturas.n ? `, lecturas iguales ${a.lecturas.iguales}/${a.lecturas.n}` : "");
}

function Informe({ informe: r }) {
  return (
    <div className="tarjeta space-y-1.5 p-3 text-[12.5px] text-[var(--bone-dim)]" aria-live="polite">
      <p className="text-[var(--bone)]">
        {r.aplicadas} marcas aplicadas · {r.conservadas} conservadas · {r.sin_contestar} sin contestar
        {r.modos_aplicados || r.modos_conservados ? ` · ${r.modos_aplicados} modos de falla (${r.modos_conservados} conservados)` : ""}
      </p>
      <p>Revisión: {r.revisadas} de {r.total} salidas.</p>
      {r.acuerdo && <p>{acuerdoTexto(r.acuerdo)}. Una kappa baja dice que quien contestó no aplica la rúbrica como tú.</p>}
      {r.errores.length > 0 && (
        <p className="text-[var(--danger)]">
          {r.errores.length} con error: {r.errores.slice(0, 8).map((e) => `${e.id} (${e.motivo})`).join(", ")}
          {r.errores.length > 8 ? "…" : ""}
        </p>
      )}
    </div>
  );
}
