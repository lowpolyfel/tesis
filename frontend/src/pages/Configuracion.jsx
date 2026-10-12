import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { useApi } from "../hooks/useApi";
import { guardarModelos, obtenerModelos, probarModelo } from "../services/backend";
import { Aviso, Cargando, Encabezado, Volver } from "../components/ui";

/*
 * Configuración de la cuenta (ADR 0021): qué proveedor y qué modelo usa cada agente
 * cuando esta cuenta analiza, y las claves de los proveedores. Se guarda en la base
 * (perfiles_llm); las claves van cifradas y no se vuelven a mostrar: solo sus últimos
 * cuatro caracteres. Un agente sin elección usa lo que dice el .env del servidor.
 */
const QUE_HACE = {
  extractor: "Separa el vocabulario del dominio en cada requisito.",
  clasificador: "Propone las interpretaciones de los términos ambiguos.",
  critico: "Debate las interpretaciones y arbitra si no hay acuerdo.",
  modelador: "Reescribe el requisito, deriva sus metas y organiza el mapa conceptual.",
  revisor: "Arma la ficha del contexto y separa los requisitos claros de los que hay que precisar.",
};

export default function Configuracion() {
  const { datos, setDatos, error } = useApi(obtenerModelos, []);
  const [agentes, setAgentes] = useState(null); // {rol: {proveedor, modelo, propio}}
  const [claves, setClaves] = useState({}); // {proveedor: texto escrito} ("" = sin cambio)
  const [urls, setUrls] = useState({}); // {proveedor: url}
  const [borrar, setBorrar] = useState(new Set()); // proveedores cuya clave se quita
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [fallo, setFallo] = useState(null);

  useEffect(() => {
    if (!datos) return;
    setAgentes(Object.fromEntries(datos.agentes.map((a) => [a.rol, { proveedor: a.proveedor, modelo: a.modelo, propio: a.propio }])));
    setUrls(Object.fromEntries(Object.entries(datos.proveedores).map(([k, v]) => [k, v.base_url ?? ""])));
    setClaves({});
    setBorrar(new Set());
  }, [datos]);

  const catalogo = useMemo(() => Object.fromEntries((datos?.catalogo ?? []).map((p) => [p.id, p])), [datos]);
  if (error) return <div className="space-y-4"><Volver a="/proyectos">Proyectos</Volver><Aviso error={error} /></div>;
  if (!datos || !agentes) return <Cargando>Cargando la configuración…</Cargando>;

  const usados = [...new Set(Object.values(agentes).map((a) => a.proveedor))];
  const conClave = Object.entries(datos.proveedores).filter(([, v]) => v.tiene_clave).map(([k]) => k);
  const visibles = [...new Set([...usados, ...conClave])].filter((p) => catalogo[p]);

  const elegir = (rol, cambio) => setAgentes((a) => {
    const actual = { ...a[rol], ...cambio, propio: true };
    // al cambiar de proveedor, el modelo sugerido de ese proveedor
    if (cambio.proveedor && cambio.proveedor !== a[rol].proveedor) actual.modelo = catalogo[cambio.proveedor]?.modelos[0] ?? "";
    return { ...a, [rol]: actual };
  });
  const delServidor = (rol) => {
    const s = datos.agentes.find((x) => x.rol === rol).servidor;
    setAgentes((a) => ({ ...a, [rol]: { ...s, propio: false } }));
  };

  const guardar = async () => {
    setGuardando(true);
    setAviso(null);
    setFallo(null);
    const proveedores = {};
    for (const p of new Set([...visibles, ...borrar])) {
      const d = {};
      if (borrar.has(p)) d.api_key = null;
      else if ((claves[p] ?? "").trim()) d.api_key = claves[p].trim();
      if (catalogo[p]?.pide_url) d.base_url = urls[p] ?? "";
      if (Object.keys(d).length) proveedores[p] = d;
    }
    try {
      const r = await guardarModelos({
        agentes: Object.fromEntries(Object.entries(agentes).map(([rol, a]) => [rol, a.propio ? { proveedor: a.proveedor, modelo: a.modelo } : null])),
        proveedores,
      });
      setDatos(r);
      setAviso("Guardado. Los próximos análisis usan esta configuración.");
    } catch (e) {
      setFallo(e.message);
    } finally {
      setGuardando(false);
    }
  };

  const faltaModelo = Object.values(agentes).some((a) => a.propio && !a.modelo.trim());

  return (
    <div className="space-y-10">
      <Encabezado volver={<Volver a="/proyectos">Proyectos</Volver>} antetitulo="Tu cuenta" titulo="Configuración">
        <p className="max-w-2xl text-[15px] leading-relaxed text-[var(--bone-dim)]">
          Elige qué proveedor y qué modelo usa cada agente cuando analizas tus proyectos. Las claves se guardan cifradas
          y no se vuelven a mostrar. La similitud entre interpretaciones sigue en Ollama local, para no cambiar el umbral calibrado.
        </p>
      </Encabezado>

      <section className="space-y-3">
        <h2>Agentes</h2>
        <ul className="space-y-2">
          {datos.agentes.map((a) => {
            const e = agentes[a.rol];
            const p = catalogo[e.proveedor];
            return (
              <li key={a.rol} className="tarjeta grid gap-3 p-4 md:grid-cols-[1fr_minmax(0,220px)_minmax(0,240px)] md:items-center">
                <div className="min-w-0">
                  <p className="text-[15.5px] text-[var(--bone)]">{a.nombre}</p>
                  <p className="text-[13px] text-[var(--bone-dim)]">{QUE_HACE[a.rol]}</p>
                  <p className="mono mt-1 text-[10px] text-[var(--bone-faint)]">
                    {e.propio
                      ? <button className="text-left hover:text-[var(--bone)]" onClick={() => delServidor(a.rol)}>usar el del servidor ({a.servidor.proveedor} · {a.servidor.modelo})</button>
                      : <>del servidor (.env)</>}
                  </p>
                </div>
                <label className="block">
                  <span className="sr-only">Proveedor de {a.nombre}</span>
                  <select className="campo" value={e.proveedor} onChange={(ev) => elegir(a.rol, { proveedor: ev.target.value })}>
                    {datos.catalogo.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                  </select>
                </label>
                <label className="block">
                  <span className="sr-only">Modelo de {a.nombre}</span>
                  <input className="campo" list={`modelos-${e.proveedor}`} value={e.modelo} placeholder="nombre del modelo"
                    onChange={(ev) => elegir(a.rol, { modelo: ev.target.value })} />
                  <datalist id={`modelos-${e.proveedor}`}>{(p?.modelos ?? []).map((m) => <option key={m} value={m} />)}</datalist>
                </label>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="space-y-3">
        <h2>Proveedores</h2>
        <p className="text-[13.5px] text-[var(--bone-dim)]">Los que usan tus agentes y los que ya tienen una clave guardada.</p>
        <ul className="space-y-2">
          {visibles.map((pid) => (
            <Proveedor key={pid} p={catalogo[pid]} guardado={datos.proveedores[pid]} clave={claves[pid] ?? ""} url={urls[pid] ?? ""}
              borrar={borrar.has(pid)} modelo={Object.values(agentes).find((a) => a.proveedor === pid)?.modelo ?? catalogo[pid].modelos[0]}
              onClave={(v) => setClaves((c) => ({ ...c, [pid]: v }))} onUrl={(v) => setUrls((u) => ({ ...u, [pid]: v }))}
              onBorrar={() => setBorrar((b) => { const n = new Set(b); if (n.has(pid)) n.delete(pid); else n.add(pid); return n; })} />
          ))}
        </ul>
      </section>

      <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-[28px] bg-[color-mix(in_oklab,var(--bg)_90%,transparent)] py-2">
        <button className="pill" disabled={guardando || faltaModelo} onClick={guardar}>{guardando ? "Guardando…" : "Guardar"}</button>
        {faltaModelo && <span className="text-[13px] text-[var(--danger)]">Escribe el modelo de cada agente.</span>}
        {aviso && <span className="text-[13px] text-[var(--ok)]">{aviso}</span>}
        {fallo && <span className="text-[13px] text-[var(--danger)]">{fallo}</span>}
        <Link className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to="/proyectos">volver</Link>
      </div>
    </div>
  );
}

function Proveedor({ p, guardado, clave, url, borrar, modelo, onClave, onUrl, onBorrar }) {
  const [prueba, setPrueba] = useState(null); // null | "probando" | {ok, ms, error}
  const probar = async () => {
    setPrueba("probando");
    try {
      setPrueba(await probarModelo({ proveedor: p.id, modelo, base_url: url || null, api_key: clave || null }));
    } catch (e) {
      setPrueba({ ok: false, error: e.message });
    }
  };
  return (
    <li className="tarjeta space-y-3 p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-[15.5px] text-[var(--bone)]">{p.nombre}</p>
        <p className="min-w-0 flex-1 text-[12.5px] text-[var(--bone-faint)]">
          {p.ayuda} {p.url_ayuda && <a className="enlace" href={p.url_ayuda} target="_blank" rel="noopener noreferrer">abrir ↗</a>}
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {(p.pide_clave || p.id === "compatible") && (
          <label className="block space-y-1">
            <span className="mono text-[10px] text-[var(--bone-faint)]">
              Clave de API {guardado?.tiene_clave && !borrar && <>· guardada, termina en «{guardado.final}»</>}
              {borrar && <span className="text-[var(--danger)]"> · se quitará al guardar</span>}
            </span>
            <input className="campo" type="password" autoComplete="off" value={clave} onChange={(e) => onClave(e.target.value)}
              placeholder={guardado?.tiene_clave ? "escribe otra para reemplazarla" : "pega aquí tu clave"} />
          </label>
        )}
        {p.pide_url && (
          <label className="block space-y-1">
            <span className="mono text-[10px] text-[var(--bone-faint)]">URL del servidor</span>
            <input className="campo" value={url} onChange={(e) => onUrl(e.target.value)} placeholder={p.base_url ?? "https://…/v1"} />
          </label>
        )}
      </div>
      <div className="mono flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-[var(--bone-faint)]">
        <button className="hover:text-[var(--bone)] disabled:opacity-40" disabled={prueba === "probando" || !modelo} onClick={probar}>
          {prueba === "probando" ? "probando…" : `probar con ${modelo || "un modelo"}`}
        </button>
        {guardado?.tiene_clave && <button className="hover:text-[var(--danger)]" onClick={onBorrar}>{borrar ? "conservar la clave" : "quitar la clave"}</button>}
        {prueba && prueba !== "probando" && (
          <span className={`normal-case tracking-normal ${prueba.ok ? "text-[var(--ok)]" : "text-[var(--danger)]"}`} style={{ fontFamily: "var(--sans)", fontSize: "12.5px" }}>
            {prueba.ok ? `Responde (${prueba.ms} ms).` : prueba.error}
          </span>
        )}
      </div>
    </li>
  );
}
