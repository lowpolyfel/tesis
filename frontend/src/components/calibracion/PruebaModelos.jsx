import { useEffect, useMemo, useState } from "react";
import { useApi } from "../../hooks/useApi";
import {
  bancoAmbiguedad, borrarPruebaModelos, cancelarPruebaModelos, crearPruebaModelos, modelosParaProbar, pruebaModelos,
  pruebasModelos, reanudarPruebaModelos, rehacerRevisionModelos, revisarPruebaModelos, urlOverleafModelos,
} from "../../services/backend";
import { GraficaModelos } from "./graficas";
import { Aviso, Cargando, Cifra, Confirmar, Plegable, Vacio } from "../ui";

/*
 * Prueba de modelos con el banco de términos ambiguos (ADR 0027). Se eligen los modelos (de los
 * proveedores con clave guardada en Configuración, y Ollama) y los términos; el Clasificador real
 * corre con cada modelo, un término por llamada, en segundo plano. Luego una persona revisa, término
 * por término, si cada modelo hizo un buen trabajo (✓ / ✗): la tercera columna de la tabla.
 *
 * Desde el banco v2 hay controles inequívocos: la prueba mide la exhaustividad y también las
 * falsas alarmas y la precisión (un modelo que marcara todo como ambiguo ya no sale perfecto).
 *
 * «Ocultar nombres» muestra los modelos como A, B, C… en un orden barajado (fijo por prueba) y
 * baraja también el orden de los términos en la revisión, para revisar sin saber cuál es cuál; si
 * se revisa viéndolos, la revisión queda marcada como no ciega. «Rehacer la revisión» la borra.
 */
const CLAVE_ANOTADOR = "dudamel.anotador";
const leer = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ic = (m) => (m?.valor == null ? "—" : `${pct(m.valor)} [${pct(m.bajo)}, ${pct(m.alto)}]`);
const LETRAS = "ABCDEFGH";
const NOMBRE_CLASE = { polisemia: "Polisemia", regionalismo: "Regionalismo", inequivoco: "Inequívoco" };
const esAmbiguo = (t) => t.ambiguo ?? t.clase !== "inequivoco";

/* Barajado determinista: el mismo orden cada vez que se abre la misma prueba (FNV-1a) */
function huella(texto) {
  let h = 2166136261;
  for (let i = 0; i < texto.length; i += 1) { h ^= texto.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
const barajar = (xs, semilla, clave = (x) => x) => [...xs].sort((a, b) => huella(`${semilla}:${clave(a)}`) - huella(`${semilla}:${clave(b)}`));
/* A, B, C… en un orden que no delata cuál se agregó primero */
const letrasDe = (pruebaId, modelos) =>
  Object.fromEntries(barajar(modelos, pruebaId, (m) => m.id).map((m, k) => [m.id, `Modelo ${LETRAS[k]}`]));
const ESTADO = { en_proceso: "corriendo", terminada: "terminada", cancelada: "cancelada", interrumpida: "interrumpida", error: "error" };

export default function PruebaModelos() {
  const [version, setVersion] = useState(null); // null: el banco más nuevo
  const banco = useApi(() => bancoAmbiguedad(version), [version]);
  const pruebas = useApi(pruebasModelos, []);
  const [abierta, setAbierta] = useState(null);
  const [ciego, setCiego] = useState(false);

  useEffect(() => {
    if (!abierta && pruebas.datos?.length) setAbierta(pruebas.datos[0].prueba_id);
  }, [pruebas.datos, abierta]);

  if (banco.error) return <Aviso error={banco.error} />;
  if (!banco.datos) return <Cargando>Cargando el banco de términos…</Cargando>;
  const b = banco.datos;

  return (
    <div className="space-y-10">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="etiqueta mr-1">Banco</span>
          {b.versiones.map((v) => (
            <button key={v} className={`pill sm ${v === b.version ? "" : "ghost"}`} aria-pressed={v === b.version}
              onClick={() => setVersion(v)}>{v}{v === b.versiones.at(-1) ? " · el más nuevo" : ""}</button>
          ))}
        </div>
        <p className="max-w-3xl text-[14px] text-[var(--bone-dim)]">
          {b.titulo} ({b.version}). {b.descripcion}
        </p>
        <p className="max-w-3xl text-[12.5px] text-[var(--bone-faint)]">
          <b className="font-medium text-[var(--bone-dim)]">Criterio de revisión.</b> {b.criterio}
        </p>
        <Plegable titulo="Ver el banco" alAbrir
          nota={`${b.terminos.filter(esAmbiguo).length} ambiguos · ${b.terminos.filter((t) => !esAmbiguo(t)).length} inequívocos · huella ${b.huella.slice(0, 12)}`}>
          <TablaBanco terminos={b.terminos} />
        </Plegable>
      </section>

      <NuevaPrueba banco={b} onCreada={(p) => { pruebas.recargar(); setAbierta(p.prueba_id); }} />

      <ListaPruebas pruebas={pruebas} abierta={abierta} onAbrir={setAbierta} ciego={ciego}
        onBorrada={(pid) => { if (abierta === pid) setAbierta(null); pruebas.recargar(); }} />

      {abierta && (
        <Prueba key={abierta} pruebaId={abierta} ciego={ciego} onCiego={setCiego} onCambio={pruebas.recargar} />
      )}
    </div>
  );
}

function TablaBanco({ terminos }) {
  return (
    <div className="overflow-x-auto">
      <table className="tabla-viz min-w-[720px]">
        <thead><tr><th>ID</th><th>Término</th><th>Clase</th><th>Dominio</th><th>Cita</th><th>Lecturas esperadas</th><th>Pareja</th></tr></thead>
        <tbody>
          {terminos.map((t) => (
            <tr key={t.id}>
              <td className="mono text-[10px]">{t.id}</td><td className="text-[var(--bone)]">{t.termino}</td>
              <td>{NOMBRE_CLASE[t.clase]}</td><td className="text-[var(--bone-dim)]">{t.dominio}</td>
              <td className="text-[var(--bone-dim)]">«{t.cita}»</td>
              <td className="text-[12px] text-[var(--bone-dim)]">{t.lecturas.join(" · ")}</td>
              <td className="mono text-[10px] text-[var(--bone-faint)]">{t.pareja ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- nueva prueba */

function NuevaPrueba({ banco, onCreada }) {
  const disponibles = useApi(modelosParaProbar, []);
  const [elegidos, setElegidos] = useState([]); // [{proveedor, modelo}]
  const [proveedor, setProveedor] = useState("");
  const [modelo, setModelo] = useState("");
  const [conjunto, setConjunto] = useState("todos");
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const provs = disponibles.datos?.proveedores ?? [];
  const p = provs.find((x) => x.id === proveedor) ?? provs[0];
  const opciones = p ? (p.modelos.length ? p.modelos : p.sugeridos.map((m) => ({ id: m, nombre: m }))) : [];
  const conjuntos = useMemo(() => {
    const ids = (f) => banco.terminos.filter(f).map((t) => t.id);
    return [
      { id: "todos", texto: "Todos", items: ids(() => true) },
      { id: "polisemia", texto: "Polisemia", items: ids((t) => t.clase === "polisemia") },
      { id: "regionalismo", texto: "Regionalismos", items: ids((t) => t.clase === "regionalismo") },
      { id: "inequivoco", texto: "Inequívocos", items: ids((t) => !esAmbiguo(t)) },
      { id: "rapida", texto: "Prueba rápida", items: banco.terminos.filter((_, i) => i % 5 === 0).map((t) => t.id) },
    ].filter((c) => c.items.length);
  }, [banco]);
  const items = (conjuntos.find((c) => c.id === conjunto) ?? conjuntos[0]).items;

  const agregar = () => {
    const m = { proveedor: p.id, modelo: (modelo || opciones[0]?.id || "").trim() };
    if (!m.modelo || elegidos.some((e) => e.proveedor === m.proveedor && e.modelo === m.modelo) || elegidos.length >= 8) return;
    setElegidos((es) => [...es, m]);
    setModelo("");
  };
  const correr = async () => {
    setEnviando(true);
    setError(null);
    try {
      const prueba = await crearPruebaModelos({ modelos: elegidos, items, nota: nota.trim(), banco: banco.version });
      setNota("");
      onCreada(prueba);
    } catch (e) { setError(e); } finally { setEnviando(false); }
  };

  return (
    <section className="space-y-4">
      <div>
        <h2>Nueva prueba</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
          Elige de 1 a 8 modelos. Aparecen los proveedores con clave guardada en <b className="font-medium">Configuración</b> y
          Ollama; la lista de modelos la da cada proveedor. Cada modelo corre el Clasificador con el mismo prompt, un término por llamada.
        </p>
      </div>
      {disponibles.cargando && !disponibles.datos && <Cargando>Preguntando a los proveedores qué modelos hay…</Cargando>}
      <Aviso error={disponibles.error} />
      {p && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block">
            <span className="etiqueta mb-1 block">Proveedor</span>
            <select className="campo w-56 text-[13px]" value={p.id} onChange={(e) => { setProveedor(e.target.value); setModelo(""); }}>
              {provs.map((x) => <option key={x.id} value={x.id} className="bg-[var(--bg)]">{x.nombre}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="etiqueta mb-1 block">Modelo</span>
            <input className="campo w-72 text-[13px]" list={`modelos-${p.id}`} value={modelo} placeholder={opciones[0]?.id ?? "nombre del modelo"}
              onChange={(e) => setModelo(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregar(); } }} />
            <datalist id={`modelos-${p.id}`}>{opciones.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}</datalist>
          </label>
          <button className="pill ghost sm" onClick={agregar} disabled={elegidos.length >= 8}>Agregar</button>
          {p.error && <span className="text-[12px] text-[#ffc457]">⚠ {p.error}</span>}
        </div>
      )}
      {elegidos.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {elegidos.map((e, k) => (
            <li key={`${e.proveedor}:${e.modelo}`} className="tarjeta flex items-center gap-2 px-3 py-1.5 text-[13px]">
              <span className="mono text-[10px] text-[var(--bone-faint)]">M{k + 1}</span>
              {e.proveedor} · {e.modelo}
              <button className="mono text-[11px] text-[var(--bone-faint)] hover:text-[var(--danger)]" aria-label={`Quitar ${e.modelo}`}
                onClick={() => setElegidos((es) => es.filter((_, i) => i !== k))}>×</button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <span className="etiqueta mr-1">Términos del banco {banco.version}</span>
        {conjuntos.map((c) => (
          <button key={c.id} className={`pill sm ${conjunto === c.id ? "" : "ghost"}`} aria-pressed={conjunto === c.id}
            onClick={() => setConjunto(c.id)}>{c.texto} <span className="opacity-60">{c.items.length}</span></button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input value={nota} onChange={(e) => setNota(e.target.value)} maxLength={500} placeholder="Nota (p. ej. «comparación local contra nube»)"
          className="campo w-96 max-w-full text-[13px]" />
        <button className="pill sm" onClick={correr} disabled={enviando || !elegidos.length}>
          {enviando ? "Creando…" : `Correr ${items.length * elegidos.length || ""} llamadas`.trim()}
        </button>
      </div>
      <Aviso error={error} />
    </section>
  );
}

/* ---------------------------------------------------------------- lista */

function ListaPruebas({ pruebas, abierta, onAbrir, onBorrada, ciego }) {
  const [borrando, setBorrando] = useState(null);
  const lista = pruebas.datos ?? [];
  return (
    <section className="space-y-3">
      <h2>Pruebas</h2>
      <Aviso error={pruebas.error} />
      {!lista.length && !pruebas.cargando && <p className="text-[13px] text-[var(--bone-faint)]">Todavía no hay pruebas.</p>}
      {lista.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tabla-viz min-w-[720px]">
            <thead><tr><th>Prueba</th><th>Fecha</th><th>Estado</th><th>Banco</th><th>Términos</th><th>Modelos · exhaustividad / falsas alarmas / aprobación</th><th>Nota</th><th /></tr></thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.prueba_id} className={abierta === p.prueba_id ? "es-configurado" : ""}>
                  <td className="mono text-[11px]">{p.prueba_id}</td>
                  <td>{p.creado.replace("T", " ").slice(0, 16)}</td>
                  <td>{ESTADO[p.estado]}{p.estado === "en_proceso" ? ` ${p.avance.hechos}/${p.avance.total}` : ""}</td>
                  <td className="mono text-[11px]">{p.banco ?? "v1"}</td>
                  <td>{p.n_items}</td>
                  <td className="text-[12px] text-[var(--bone-dim)]">
                    {(ciego ? barajar(p.modelos, p.prueba_id, (m) => m.id) : p.modelos).map((m) => (
                      <span key={m.id} className="mr-3 inline-block">
                        {ciego ? letrasDe(p.prueba_id, p.modelos)[m.id] : m.etiqueta} · {pct(m.deteccion)} / {pct(m.falsas_alarmas)} / {m.revisados ? pct(m.aprobacion) : "—"}
                      </span>
                    ))}
                  </td>
                  <td className="max-w-[12rem] truncate text-[var(--bone-dim)]">{p.nota ?? "—"}</td>
                  <td className="whitespace-nowrap text-right">
                    <button className="pill ghost sm" onClick={() => onAbrir(p.prueba_id)}>Ver</button>{" "}
                    <button className="mono px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => setBorrando(p)}>borrar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {borrando && (
        <Confirmar pregunta={`¿Borrar la prueba ${borrando.prueba_id}?`} detalle="Se borran también sus revisiones. Si ya la citaste, descarga antes su paquete."
          accion="Borrar prueba" onCancelar={() => setBorrando(null)}
          onConfirmar={async () => { await borrarPruebaModelos(borrando.prueba_id); onBorrada(borrando.prueba_id); setBorrando(null); }} />
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- una prueba */

function Prueba({ pruebaId, ciego, onCiego, onCambio }) {
  const { datos: p, setDatos, error, recargar } = useApi(() => pruebaModelos(pruebaId), [pruebaId]);
  const version = p?.banco?.version;
  const banco = useApi(() => (version ? bancoAmbiguedad(version) : Promise.resolve(null)), [version]);
  const [accion, setAccion] = useState(null);
  const [rehaciendo, setRehaciendo] = useState(false);
  const [fallo, setFallo] = useState(null);
  const corriendo = p?.estado === "en_proceso";

  // mientras corre, se vuelve a pedir cada 2 s (y la lista, para su avance)
  useEffect(() => {
    if (!corriendo) return undefined;
    const t = setInterval(() => { recargar(); onCambio(); }, 2000);
    return () => clearInterval(t);
  }, [corriendo, recargar, onCambio]);

  if (error || banco.error) return <Aviso error={error || banco.error} />;
  if (!p || !banco.datos) return <Cargando>Cargando la prueba…</Cargando>;

  const letras = letrasDe(p.prueba_id, p.modelos);
  const nombre = (m) => (ciego ? letras[m.id] : `${m.proveedor} · ${m.modelo}`);
  const hacer = async (que, f) => {
    setAccion(que);
    setFallo(null);
    try { await f(); recargar(); onCambio(); } catch (e) { setFallo(e); } finally { setAccion(null); }
  };
  const descargar = () => hacer("zip", async () => {
    const r = await fetch(urlOverleafModelos(p.prueba_id), { credentials: "include" });
    if (!r.ok) throw new Error(`No se pudo descargar el paquete (HTTP ${r.status}).`);
    const url = URL.createObjectURL(await r.blob());
    Object.assign(document.createElement("a"), { href: url, download: `dudamel-modelos-${p.prueba_id}.zip` }).click();
    URL.revokeObjectURL(url);
  });
  const r = p.resumen;
  const conErrores = r.modelos.some((m) => m.errores);
  const hechos = p.avance.hechos / Math.max(1, p.avance.total);

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <h2>Prueba {p.prueba_id}</h2>
        <span className="text-[13px] text-[var(--bone-dim)]">
          {p.creado.replace("T", " ").slice(0, 16)} · {p.items.length} términos · {p.modelos.length} modelos · {ESTADO[p.estado]}
          {p.nota ? ` · ${p.nota}` : ""}
        </span>
        <label className="mono ml-auto flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={ciego} onChange={(e) => onCiego(e.target.checked)} />
          ocultar nombres de los modelos
        </label>
      </div>
      <p className="mono flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-[var(--bone-faint)]">
        <span>prompt <b className="font-normal text-[var(--bone)]">{p.configuracion.prompt}</b></span>
        <span>temperatura <b className="font-normal text-[var(--bone)]">{p.configuracion.temperatura}</b></span>
        <span>banco {p.banco.version} · {p.banco.huella.slice(0, 12)}</span>
        <span>versión {p.version_app}</span>
      </p>

      {corriendo && (
        <div className="space-y-2">
          <div className="h-1.5 overflow-hidden rounded-full bg-[color-mix(in_oklab,var(--bone)_10%,transparent)]">
            <div className="h-full rounded-full bg-[var(--c1)] transition-[width]" style={{ width: `${hechos * 100}%` }} />
          </div>
          <p className="text-[12.5px] text-[var(--bone-dim)]">
            {p.avance.hechos} de {p.avance.total} llamadas. Puedes revisar lo que ya llegó mientras sigue.
          </p>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {corriendo && <button className="pill ghost sm" disabled={accion} onClick={() => hacer("cancelar", () => cancelarPruebaModelos(p.prueba_id))}>Cancelar</button>}
        {["cancelada", "interrumpida"].includes(p.estado) && (
          <button className="pill sm" disabled={accion} onClick={() => hacer("reanudar", () => reanudarPruebaModelos(p.prueba_id))}>Reanudar lo que falta</button>
        )}
        {!corriendo && conErrores && (
          <button className="pill ghost sm" disabled={accion} onClick={() => hacer("errores", () => reanudarPruebaModelos(p.prueba_id, true))}>Reintentar los errores</button>
        )}
        {!corriendo && <button className="pill sm" disabled={accion} onClick={descargar}>{accion === "zip" ? "Preparando…" : "Overleaf ↓"}</button>}
        {p.revisiones && <button className="pill ghost sm" disabled={accion} onClick={() => setRehaciendo(true)}>Rehacer la revisión</button>}
      </div>
      {rehaciendo && (
        <Confirmar pregunta={`¿Borrar las ${r.modelos.reduce((s, m) => s + m.revisados, 0)} marcas de la prueba ${p.prueba_id}?`}
          detalle="Las respuestas de los modelos se conservan. Para que la aprobación cuente como revisión a ciegas, activa «ocultar nombres de los modelos» antes de volver a marcar: el orden de los modelos y de los términos se baraja."
          accion="Borrar las marcas" onCancelar={() => setRehaciendo(false)}
          onConfirmar={async () => { await rehacerRevisionModelos(p.prueba_id); setRehaciendo(false); onCiego(true); recargar(); onCambio(); }} />
      )}
      <Aviso error={fallo} />
      {r.avisos.length > 0 && (
        <ul className="space-y-1.5">{r.avisos.map((a) => <li key={a} className="text-[13px] text-[#ffc457]">⚠ {a}</li>)}</ul>
      )}

      <Resumen r={r} nombre={nombre} orden={ciego ? barajar(r.modelos, p.prueba_id, (m) => m.id) : r.modelos} />
      <Revision p={p} banco={banco.datos} ciego={ciego} nombre={nombre}
        onRevision={(x) => setDatos((d) => ({ ...d, revisiones: x.revisiones, resumen: x.resumen }))} />
    </section>
  );
}

function Resumen({ r, nombre, orden }) {
  const mejor = [...r.modelos].filter((m) => m.aprobacion.valor != null).sort((a, b) => b.aprobacion.valor - a.aprobacion.valor)[0];
  const revisados = r.modelos.reduce((s, m) => s + m.revisados, 0);
  const total = r.modelos.reduce((s, m) => s + m.respondidos, 0);
  const pares = r.pares.filter((x) => x.comunes);
  const porId = Object.fromEntries(r.modelos.map((m) => [m.id, m]));
  const controles = r.modelos.some((m) => m.falsas_alarmas);
  const m0 = r.modelos[0];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        <Cifra valor={`${r.modelos.length}`} nombre="modelos" />
        <Cifra valor={`${m0?.n ?? 0}`} nombre={controles ? `términos (${m0.n_ambiguos} ambiguos, ${m0.n_inequivocos} inequívocos)` : "términos ambiguos (sin controles)"} />
        <Cifra valor={`${revisados}/${total}`} nombre="respuestas revisadas" />
        <Cifra valor={mejor ? pct(mejor.aprobacion.valor) : "—"} nombre={mejor ? `mejor aprobación · ${nombre(mejor)}` : "sin revisiones todavía"} />
      </div>
      <GraficaModelos modelos={orden} nombres={nombre} />
      <div className="overflow-x-auto">
        <table className="tabla-viz min-w-[960px]">
          <thead>
            <tr>
              <th>Modelo</th><th>Exhaustividad</th>
              {controles && <><th>Falsas alarmas</th><th>Precisión</th><th>Parejas</th></>}
              <th>Aprobación</th><th>Revisados</th><th>Errores</th><th>Reintentos</th><th>Latencia</th>
            </tr>
          </thead>
          <tbody>
            {orden.map((m) => (
              <tr key={m.id}>
                <td className="text-[var(--bone)]">{nombre(m)}</td>
                <td>{ic(m.deteccion)}</td>
                {controles && (
                  <>
                    <td>{ic(m.falsas_alarmas)}</td><td>{ic(m.precision)}</td>
                    <td>{m.parejas ? `${m.parejas.discrimina}/${m.parejas.n}` : "—"}</td>
                  </>
                )}
                <td>{ic(m.aprobacion)}</td>
                <td>{m.revisados}/{m.n}</td><td>{m.errores}</td><td>{m.reintentos}</td>
                <td>{m.latencia_ms.mediana == null ? "—" : `${(m.latencia_ms.mediana / 1000).toFixed(1)} s`}
                  {m.latencia_ms.p90 != null && <span className="text-[var(--bone-faint)]"> · p90 {(m.latencia_ms.p90 / 1000).toFixed(1)} s</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 max-w-4xl text-[12px] text-[var(--bone-faint)]">
          Exhaustividad = ambiguos que el modelo marcó como ambiguos (2 o más intenciones) sobre todos los ambiguos; un error cuenta
          como no detectado.{controles
            ? " Falsas alarmas = inequívocos marcados como ambiguos sobre los inequívocos que respondieron. Precisión = ambiguos sobre todo lo marcado. Parejas = en cuántas parejas del mismo dominio («caja» / «caja registradora») marcó el ambiguo y no su control."
            : " Este banco no tiene controles inequívocos: no hay precisión ni falsas alarmas, y un modelo que marcara todo como ambiguo saldría perfecto."}
          {" "}Aprobación = ✓ sobre los revisados. Entre corchetes, intervalo de Wilson al 95 %.
        </p>
      </div>
      {controles && (
        <Plegable titulo="Matriz de confusión" nota="positivo = marcó ambiguo" alAbrir>
          <table className="tabla-viz min-w-[640px]">
            <thead><tr><th>Modelo</th><th>VP</th><th>FN</th><th>FP</th><th>VN</th><th>Errores en inequívocos</th></tr></thead>
            <tbody>
              {orden.map((m) => (
                <tr key={m.id}><td>{nombre(m)}</td><td>{m.confusion.vp}</td><td>{m.confusion.fn}</td><td>{m.confusion.fp}</td><td>{m.confusion.vn}</td><td>{m.errores_inequivocos}</td></tr>
              ))}
            </tbody>
          </table>
        </Plegable>
      )}
      <Plegable titulo="Por clase de término" nota={controles ? "polisemia, regionalismos e inequívocos" : "polisemia y regionalismos"} alAbrir>
        <table className="tabla-viz min-w-[640px]">
          <thead><tr><th>Modelo</th><th>Clase</th><th>Términos</th><th>Marcó ambiguo</th><th>Aprobación</th></tr></thead>
          <tbody>
            {orden.flatMap((m) => Object.entries(m.por_clase).map(([clase, c]) => (
              <tr key={`${m.id}-${clase}`}>
                <td>{nombre(m)}</td><td>{NOMBRE_CLASE[clase] ?? clase}</td><td>{c.n}</td>
                <td>{ic(c.deteccion)}<span className="text-[var(--bone-faint)]">{c.ambiguo === false ? " · falsas alarmas" : ""}</span></td>
                <td>{ic(c.aprobacion)}</td>
              </tr>
            )))}
          </tbody>
        </table>
        <p className="mt-2 text-[12px] text-[var(--bone-faint)]">
          Con 20 o 30 términos por clase los intervalos son anchos: si se traslapan, una diferencia entre clases es una tendencia por confirmar, no un resultado.
        </p>
      </Plegable>
      {pares.length > 0 && (
        <Plegable titulo="¿La diferencia es más que azar?" nota="McNemar exacta por pares" alAbrir>
          <table className="tabla-viz min-w-[640px]">
            <thead><tr><th>Modelo A</th><th>Modelo B</th><th>Revisados en ambos</th><th>✓ solo en A</th><th>✓ solo en B</th><th>p</th></tr></thead>
            <tbody>
              {pares.map((x) => (
                <tr key={`${x.a}-${x.b}`}>
                  <td>{nombre(porId[x.a])}</td><td>{nombre(porId[x.b])}</td><td>{x.comunes}</td><td>{x.solo_a}</td><td>{x.solo_b}</td>
                  <td className={x.p != null && x.p < 0.05 ? "text-[var(--bone)]" : ""}>{x.p == null ? "—" : x.p.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[12px] text-[var(--bone-faint)]">p &lt; 0.05 sugiere que uno de los dos modelos hace mejor trabajo; con pocos términos revisados, casi nunca lo será.</p>
        </Plegable>
      )}
    </div>
  );
}

/* La revisión: término y lecturas esperadas | lo que respondió el modelo | ¿buen trabajo? */
function Revision({ p, banco, ciego, nombre, onRevision }) {
  const [modeloId, setModeloId] = useState(() => (ciego ? barajar(p.modelos, p.prueba_id, (m) => m.id) : p.modelos)[0].id);
  const [revisor, setRevisor] = useState(() => leer(CLAVE_ANOTADOR, ""));
  const [pendientes, setPendientes] = useState(false);
  const [guardando, setGuardando] = useState(null);
  const [error, setError] = useState(null);
  const terminos = useMemo(() => Object.fromEntries(banco.terminos.map((t) => [t.id, t])), [banco]);
  const res = p.resultados[modeloId] ?? {};
  const marcas = p.revisiones?.marcas?.[modeloId] ?? {};
  const m = p.modelos.find((x) => x.id === modeloId);
  // a ciegas, el orden de los términos se baraja por modelo: no se revisa siempre en la misma secuencia
  const orden = ciego ? barajar(p.items, `${p.prueba_id}:${modeloId}`) : p.items;
  const modelos = ciego ? barajar(p.modelos, p.prueba_id, (x) => x.id) : p.modelos;
  const filas = orden.filter((i) => !pendientes || (res[i] && marcas[i]?.bueno == null));
  const revisadas = p.items.filter((i) => marcas[i]?.bueno != null).length;

  const marcar = async (item, bueno) => {
    if (!revisor.trim()) { setError(new Error("Escribe quién revisa antes de marcar.")); return; }
    setGuardando(item);
    setError(null);
    try {
      try { localStorage.setItem(CLAVE_ANOTADOR, revisor.trim()); } catch { /* sin almacenamiento */ }
      onRevision(await revisarPruebaModelos(p.prueba_id, { modelo: modeloId, item, bueno, revisor: revisor.trim(), a_ciegas: ciego }));
    } catch (e) { setError(e); } finally { setGuardando(null); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2>Revisión</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
          Para cada término, compara lo que respondió el modelo con lo esperado y marca si hizo un buen trabajo. {banco.criterio}
          {!ciego && " Para revisar sin saber qué modelo es cuál, activa «ocultar nombres de los modelos»: se baraja también el orden."}
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="block">
          <span className="etiqueta mb-1 block">Revisor</span>
          <input value={revisor} onChange={(e) => setRevisor(e.target.value)} maxLength={120} placeholder="Tu nombre" className="campo w-56 text-[14px]" />
        </label>
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Modelo que se revisa">
          {modelos.map((x) => (
            <button key={x.id} role="tab" aria-selected={x.id === modeloId} className={`pill sm ${x.id === modeloId ? "" : "ghost"}`}
              onClick={() => setModeloId(x.id)}>{nombre(x)}</button>
          ))}
        </div>
        <label className="mono flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={pendientes} onChange={(e) => setPendientes(e.target.checked)} />
          solo sin revisar
        </label>
        <span className="mono ml-auto text-[10px] text-[var(--bone-faint)]">{revisadas}/{p.items.length} revisados · {nombre(m)}</span>
      </div>
      <Aviso error={error} />
      {!filas.length && <Vacio>No queda nada por revisar en este modelo.</Vacio>}
      {filas.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tabla-viz min-w-[860px]">
            <thead><tr><th className="w-[34%]">Término y lecturas esperadas</th><th>Respuesta del modelo</th><th className="w-[9rem]">¿Buen trabajo?</th></tr></thead>
            <tbody>
              {filas.map((i) => {
                const t = terminos[i];
                const r = res[i];
                const bueno = marcas[i]?.bueno;
                return (
                  <tr key={i} className="align-top">
                    <td className="space-y-1 py-3">
                      <p><span className="mono mr-2 text-[10px] text-[var(--bone-faint)]">{i}</span><b className="font-medium text-[var(--bone)]">{t.termino}</b>
                        <span className="ml-2 text-[11.5px] text-[var(--bone-faint)]">{t.dominio}</span></p>
                      <p className="text-[12.5px] text-[var(--bone-dim)]">«{t.cita}»</p>
                      <p className="mono text-[10px] text-[var(--bone-faint)]">
                        se espera: <span className="text-[var(--bone-dim)]">{esAmbiguo(t) ? "ambiguo, con estas lecturas" : "unívoco, con esta única lectura"}</span>
                      </p>
                      <ul className="list-disc pl-4 text-[12px] text-[var(--bone-faint)]">{t.lecturas.map((l) => <li key={l}>{l}</li>)}</ul>
                    </td>
                    <td className="py-3"><Respuesta r={r} /></td>
                    <td className="py-3">
                      <span className="inline-flex gap-1">
                        {[[true, "✓", "Buen trabajo", "var(--ok)"], [false, "✗", "Mal trabajo", "var(--danger)"]].map(([v, txt, etiqueta, color]) => (
                          <button key={txt} type="button" disabled={!r || guardando === i} aria-label={etiqueta} title={etiqueta}
                            aria-pressed={bueno === v} onClick={() => marcar(i, bueno === v ? null : v)}
                            className="pill ghost sm min-w-[2.8rem] justify-center"
                            style={{ fontSize: 16, fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif", letterSpacing: 0, ...(bueno === v ? { background: color, borderColor: color, color: "var(--bg)" } : {}) }}>{txt}</button>
                        ))}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Respuesta({ r }) {
  if (!r) return <span className="text-[12.5px] text-[var(--bone-faint)]">todavía no corre</span>;
  if (!r.ok) return <span className="text-[12.5px] text-[var(--danger)]">error · {r.error}</span>;
  return (
    <div className="space-y-1.5">
      <p className="mono text-[10px] text-[var(--bone-faint)]">
        <span className={r.ambiguo ? "text-[var(--bone)]" : ""}>{r.ambiguo ? `ambiguo · ${r.intenciones.length} intenciones` : "unívoco"}</span>
        {` · ${(r.ms / 1000).toFixed(1)} s`}{r.intentos > 1 ? " · con reintento" : ""}
      </p>
      <ul className="space-y-1">
        {r.intenciones.map((x) => (
          <li key={x.id} className="text-[13px]">
            <span className="mono mr-1.5 text-[10px] text-[var(--bone-faint)]">{x.id}</span>
            <span className="text-[var(--bone)]">{x.significado}</span>
            <span className="text-[var(--bone-dim)]"> — {x.intencion}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
