import { useEffect, useMemo, useState } from "react";
import { useApi } from "../../hooks/useApi";
import {
  asignarModoFalla, bancoAmbiguedad, borrarPruebaModelos, cancelarPruebaModelos, crearPruebaModelos, modelosParaProbar,
  pruebaModelos, pruebasModelos, reanudarPruebaModelos, repetirPruebaModelos, rubricaRevision, serieModelos, urlOverleafModelos,
} from "../../services/backend";
import { GraficaModelos } from "./graficas";
import RevisionCalidad from "./RevisionCalidad";
import { Aviso, Cargando, Cifra, Confirmar, Pestanas, Plegable } from "../ui";

/*
 * Prueba de modelos con el banco de términos (ADR 0027, 0028 y 0029). Arriba, las pruebas y el
 * botón para crear una (modelos, banco, términos y cuántas corridas idénticas); abajo, la prueba
 * abierta en cuatro pestañas:
 *   - Resultados: detección contra el banco (exhaustividad, falsas alarmas, precisión, parejas) y
 *     calidad de la revisión humana, con McNemar entre modelos.
 *   - Revisión de calidad: tres criterios por salida y cobertura de lecturas, a ciegas y con teclado
 *     (RevisionCalidad.jsx).
 *   - Falsos negativos: el modo de falla de cada ambiguo no detectado.
 *   - Estabilidad: corridas idénticas de la misma configuración y el rango de la detección.
 */
const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ic = (m) => (m?.valor == null ? "—" : `${pct(m.valor)} [${pct(m.bajo)}, ${pct(m.alto)}]`);
const NOMBRE_CLASE = { polisemia: "Polisemia", regionalismo: "Regionalismo", inequivoco: "Inequívoco" };
const esAmbiguo = (t) => t.ambiguo ?? t.clase !== "inequivoco";
const ESTADO = { en_proceso: "corriendo", terminada: "terminada", cancelada: "cancelada", interrumpida: "interrumpida", error: "error" };

export default function PruebaModelos() {
  const pruebas = useApi(pruebasModelos, []);
  const [abierta, setAbierta] = useState(null);
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (!abierta && pruebas.datos?.length) setAbierta(pruebas.datos[0].prueba_id);
  }, [pruebas.datos, abierta]);

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <h2>Pruebas</h2>
          <button className={`pill sm ${creando ? "ghost" : ""}`} onClick={() => setCreando((c) => !c)} aria-expanded={creando}>
            {creando ? "Cerrar" : "Nueva prueba"}
          </button>
        </div>
        {creando && <NuevaPrueba onCreada={(p) => { pruebas.recargar(); setAbierta(p.prueba_id); setCreando(false); }} />}
        <ListaPruebas pruebas={pruebas} abierta={abierta} onAbrir={setAbierta}
          onBorrada={(pid) => { if (abierta === pid) setAbierta(null); pruebas.recargar(); }} />
      </section>
      {abierta && <Prueba key={abierta} pruebaId={abierta} onCambio={pruebas.recargar} />}
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

function NuevaPrueba({ onCreada }) {
  const [version, setVersion] = useState(null); // null: el banco más nuevo
  const bancoApi = useApi(() => bancoAmbiguedad(version), [version]);
  if (bancoApi.error) return <Aviso error={bancoApi.error} />;
  if (!bancoApi.datos) return <Cargando>Cargando el banco de términos…</Cargando>;
  return <FormularioPrueba banco={bancoApi.datos} onVersion={setVersion} onCreada={onCreada} />;
}

function FormularioPrueba({ banco, onVersion, onCreada }) {
  const disponibles = useApi(modelosParaProbar, []);
  const [repeticiones, setRepeticiones] = useState(1);
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
      const prueba = await crearPruebaModelos({ modelos: elegidos, items, nota: nota.trim(), banco: banco.version,
        repeticiones: Number(repeticiones) || 1 });
      setNota("");
      onCreada(prueba);
    } catch (e) { setError(e); } finally { setEnviando(false); }
  };

  return (
    <section className="tarjeta space-y-4 p-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="etiqueta mr-1">Banco</span>
          {banco.versiones.map((v) => (
            <button key={v} className={`pill sm ${v === banco.version ? "" : "ghost"}`} aria-pressed={v === banco.version}
              onClick={() => onVersion(v)}>{v}{v === banco.versiones.at(-1) ? " · el más nuevo" : ""}</button>
          ))}
        </div>
        <p className="max-w-3xl text-[13px] text-[var(--bone-dim)]">{banco.titulo}. {banco.descripcion}</p>
        <Plegable titulo="Ver el banco" alAbrir
          nota={`${banco.terminos.filter(esAmbiguo).length} ambiguos · ${banco.terminos.filter((t) => !esAmbiguo(t)).length} inequívocos · huella ${banco.huella.slice(0, 12)}`}>
          <TablaBanco terminos={banco.terminos} />
        </Plegable>
      </div>
      <div>
        <p className="etiqueta">Modelos</p>
        <p className="mt-1 max-w-3xl text-[13px] text-[var(--bone-dim)]">
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
        <label className="mono flex items-center gap-2 text-[10px] text-[var(--bone-faint)]" title="Corridas idénticas una tras otra, para medir la estabilidad">
          corridas idénticas
          <input type="number" min="1" max="10" value={repeticiones} onChange={(e) => setRepeticiones(e.target.value)} className="linea w-12 py-1 text-[13px] text-[var(--bone)]" />
        </label>
        <button className="pill sm" onClick={correr} disabled={enviando || !elegidos.length}>
          {enviando ? "Creando…" : `Correr ${items.length * elegidos.length * (Number(repeticiones) || 1) || ""} llamadas`.trim()}
        </button>
      </div>
      <Aviso error={error} />
    </section>
  );
}

/* ---------------------------------------------------------------- lista */

function ListaPruebas({ pruebas, abierta, onAbrir, onBorrada }) {
  const [borrando, setBorrando] = useState(null);
  const lista = pruebas.datos ?? [];
  return (
    <section className="space-y-3">
      <Aviso error={pruebas.error} />
      {!lista.length && !pruebas.cargando && <p className="text-[13px] text-[var(--bone-faint)]">Todavía no hay pruebas.</p>}
      {lista.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tabla-viz min-w-[720px]">
            <thead><tr><th>Prueba</th><th>Fecha</th><th>Estado</th><th>Términos</th><th>Modelos · exhaustividad / falsas alarmas</th><th>Revisión</th><th>Nota</th><th /></tr></thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.prueba_id} className={abierta === p.prueba_id ? "es-configurado" : ""}>
                  <td className="mono text-[11px]" title={p.uid ?? "anterior a la 2.4.0"}>{p.codigo}{p.corrida > 1 ? ` · corrida ${p.corrida}` : ""}</td>
                  <td>{p.creado.replace("T", " ").slice(0, 16)}</td>
                  <td>{ESTADO[p.estado]}{p.estado === "en_proceso" ? ` ${p.avance.hechos}/${p.avance.total}` : ""}</td>
                  <td>{p.n_items}</td>
                  <td className="text-[12px] text-[var(--bone-dim)]">
                    {p.modelos.map((m) => (
                      <span key={m.id} className="mr-3 inline-block">{m.etiqueta} · {pct(m.deteccion)} / {pct(m.falsas_alarmas)}</span>
                    ))}
                  </td>
                  <td className="text-[12px]">{p.modelos.reduce((s, m) => s + m.revisadas, 0)}/{p.modelos.reduce((s, m) => s + m.revisables, 0)}</td>
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
        <Confirmar pregunta={`¿Borrar la prueba ${borrando.codigo}?`} detalle="Se borran también sus revisiones. Su número no se vuelve a usar. Si ya la citaste, descarga antes su paquete."
          accion="Borrar prueba" onCancelar={() => setBorrando(null)}
          onConfirmar={async () => { await borrarPruebaModelos(borrando.prueba_id); onBorrada(borrando.prueba_id); setBorrando(null); }} />
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- una prueba */

const VISTAS = [
  { id: "resultados", texto: "Resultados" },
  { id: "revision", texto: "Revisión de calidad" },
  { id: "fallas", texto: "Falsos negativos" },
  { id: "estabilidad", texto: "Estabilidad" },
];

function Prueba({ pruebaId, onCambio }) {
  const { datos: p, error, recargar } = useApi(() => pruebaModelos(pruebaId), [pruebaId]);
  const version = p?.banco?.version;
  const banco = useApi(() => (version ? bancoAmbiguedad(version) : Promise.resolve(null)), [version]);
  const [vista, setVista] = useState("resultados");
  const [accion, setAccion] = useState(null);
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

  const nombre = (m) => `${m.proveedor} · ${m.modelo}`;
  const hacer = async (que, f) => {
    setAccion(que);
    setFallo(null);
    try { await f(); recargar(); onCambio(); } catch (e) { setFallo(e); } finally { setAccion(null); }
  };
  const descargar = () => hacer("zip", async () => {
    const r = await fetch(urlOverleafModelos(p.prueba_id), { credentials: "include" });
    if (!r.ok) throw new Error(`No se pudo descargar el paquete (HTTP ${r.status}).`);
    const url = URL.createObjectURL(await r.blob());
    Object.assign(document.createElement("a"), { href: url, download: `dudamel-modelos-${p.codigo}.zip` }).click();
    URL.revokeObjectURL(url);
  });
  const r = p.resumen;
  const conErrores = r.modelos.some((m) => m.errores);
  const revisadas = r.modelos.reduce((s, m) => s + m.calidad.revisadas, 0);
  const revisables = r.modelos.reduce((s, m) => s + m.calidad.revisables, 0);
  const fn = r.modelos.reduce((s, m) => s + m.falsos_negativos.items.length, 0);
  const vistas = VISTAS.map((v) => ({ ...v, cuenta: v.id === "revision" ? `${revisadas}/${revisables}` : v.id === "fallas" ? fn : null }));

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h2>Prueba {p.codigo}</h2>
          <span className="text-[13px] text-[var(--bone-dim)]">
            {p.creado.replace("T", " ").slice(0, 16)} · {p.items.length} términos · {p.modelos.length} modelos · {ESTADO[p.estado]}
            {p.nota ? ` · ${p.nota}` : ""}
          </span>
        </div>
        <p className="mono flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-[var(--bone-faint)]">
          <span>prompt <b className="font-normal text-[var(--bone)]">{p.configuracion.prompt}</b></span>
          <span>temperatura <b className="font-normal text-[var(--bone)]">{p.configuracion.temperatura}</b> · semilla {p.configuracion.semilla ?? "—"}</span>
          <span>banco {p.banco.version} · {p.banco.huella.slice(0, 12)}</span>
          <span>versión {p.version_app}</span>
          {p.serie && p.serie !== p.prueba_id ? <span>corrida {p.corrida} de la serie {p.serie}</span> : null}
          <span title="identificador único">uid {p.uid ? p.uid.slice(0, 8) : "— (anterior a la 2.4.0)"}</span>
        </p>
      </header>

      {corriendo && (
        <div className="space-y-2">
          <div className="h-1.5 overflow-hidden rounded-full bg-[color-mix(in_oklab,var(--bone)_10%,transparent)]">
            <div className="h-full rounded-full bg-[var(--c1)] transition-[width]" style={{ width: `${(p.avance.hechos / Math.max(1, p.avance.total)) * 100}%` }} />
          </div>
          <p className="text-[12.5px] text-[var(--bone-dim)]">{p.avance.hechos} de {p.avance.total} llamadas.</p>
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
      </div>
      <Aviso error={fallo} />

      <Pestanas opciones={vistas} valor={vista} onCambio={setVista} etiqueta="Qué ver de la prueba" />
      {vista === "resultados" && <Resultados r={r} nombre={nombre} />}
      {vista === "revision" && <RevisionCalidad prueba={p} banco={banco.datos} onCambio={() => { recargar(); onCambio(); }} />}
      {vista === "fallas" && <FalsosNegativos p={p} r={r} nombre={nombre} onCambio={recargar} />}
      {vista === "estabilidad" && <Estabilidad p={p} onCambio={() => { recargar(); onCambio(); }} />}
    </section>
  );
}

const NOMBRE_CRITERIO = { fidelidad: "Fidelidad", delimitacion: "Delimitación", intencion: "Intención" };
const p3 = (x) => (x == null ? "—" : x < 0.001 ? x.toExponential(1) : x.toFixed(3));

function Resultados({ r, nombre }) {
  const controles = r.modelos.some((m) => m.falsas_alarmas);
  const revisada = r.modelos.some((m) => m.calidad.revisadas);
  const m0 = r.modelos[0];
  return (
    <div className="space-y-7">
      {r.avisos.length > 0 && (
        <ul className="space-y-1.5">{r.avisos.map((a) => <li key={a} className="text-[13px] text-[var(--aviso)]">⚠ {a}</li>)}</ul>
      )}
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        <Cifra valor={`${r.modelos.length}`} nombre="modelos" />
        <Cifra valor={`${m0?.n ?? 0}`} nombre={controles ? `términos (${m0.n_ambiguos} ambiguos, ${m0.n_inequivocos} inequívocos)` : "términos ambiguos (sin controles)"} />
        <Cifra valor={`${r.modelos.reduce((s, m) => s + m.calidad.revisadas, 0)}`} nombre="salidas con revisión de calidad" />
        <Cifra valor={`${r.modelos.reduce((s, m) => s + m.falsos_negativos.items.length, 0)}`} nombre="falsos negativos" />
      </div>

      <section className="space-y-3">
        <h3 className="text-[15px] text-[var(--bone)]">Detección, contra el banco</h3>
        <GraficaModelos modelos={r.modelos} nombres={nombre} />
        <div className="overflow-x-auto">
          <table className="tabla-viz min-w-[820px]">
            <thead><tr><th>Modelo</th><th>Exhaustividad</th>{controles && <><th>Falsas alarmas</th><th>Precisión</th><th>Parejas</th></>}<th>Errores</th><th>Reintentos</th><th>Latencia</th></tr></thead>
            <tbody>
              {r.modelos.map((m) => (
                <tr key={m.id}>
                  <td className="text-[var(--bone)]">{nombre(m)}</td><td>{ic(m.deteccion)}</td>
                  {controles && <><td>{ic(m.falsas_alarmas)}</td><td>{ic(m.precision)}</td><td>{m.parejas ? `${m.parejas.discrimina}/${m.parejas.n}` : "—"}</td></>}
                  <td>{m.errores}</td><td>{m.reintentos}</td>
                  <td>{m.latencia_ms.mediana == null ? "—" : `${(m.latencia_ms.mediana / 1000).toFixed(1)} s`}
                    {m.latencia_ms.p90 != null && <span className="text-[var(--bone-faint)]"> · p90 {(m.latencia_ms.p90 / 1000).toFixed(1)} s</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 max-w-4xl text-[12px] text-[var(--bone-faint)]">
            Exhaustividad = ambiguos marcados como ambiguos sobre todos los ambiguos (un error cuenta como no detectado).
            {controles ? " Falsas alarmas = inequívocos marcados sobre los inequívocos que respondieron. Precisión = ambiguos sobre todo lo marcado. Parejas = ambiguo marcado y su control del mismo dominio no." : " Sin controles en el banco no hay precisión ni falsas alarmas."}
            {" "}Entre corchetes, intervalo de Wilson al 95 %.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-[15px] text-[var(--bone)]">Calidad, de la revisión humana</h3>
        {!revisada && <p className="text-[13px] text-[var(--bone-faint)]">— Todavía no hay revisión de calidad: ábrela en la pestaña «Revisión de calidad».</p>}
        {revisada && (
          <div className="overflow-x-auto">
            <table className="tabla-viz min-w-[760px]">
              <thead><tr><th>Modelo</th><th>Revisadas</th><th>Fidelidad</th><th>Delimitación</th><th>Intención</th><th>Cobertura</th></tr></thead>
              <tbody>
                {r.modelos.map((m) => {
                  const q = m.calidad;
                  return (
                    <tr key={m.id}>
                      <td className="text-[var(--bone)]">{nombre(m)}</td><td>{q.revisadas}/{q.revisables}</td>
                      {["fidelidad", "delimitacion", "intencion"].map((c) => <td key={c}>{ic(q.criterios[c])}</td>)}
                      <td>{q.cobertura.proporcion == null ? "—" : `${q.cobertura.cubiertas}/${q.cobertura.esperadas} · ${pct(q.cobertura.proporcion)}`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {r.aprobacion_legado && (
          <p className="text-[12.5px] text-[var(--bone-faint)]">
            Criterio anterior (v2.3, un ✓/✗ por salida, sin desglose; no se traduce a los criterios nuevos):{" "}
            {r.modelos.map((m) => `${nombre(m)} ${ic(r.aprobacion_legado.por_modelo[m.id])}`).join(" · ")}.
          </p>
        )}
      </section>

      {controles && (
        <Plegable titulo="Matriz de confusión" nota="positivo = marcó ambiguo" alAbrir>
          <table className="tabla-viz min-w-[640px]">
            <thead><tr><th>Modelo</th><th>VP</th><th>FN</th><th>FP</th><th>VN</th><th>Errores en inequívocos</th></tr></thead>
            <tbody>
              {r.modelos.map((m) => (
                <tr key={m.id}><td>{nombre(m)}</td><td>{m.confusion.vp}</td><td>{m.confusion.fn}</td><td>{m.confusion.fp}</td><td>{m.confusion.vn}</td><td>{m.errores_inequivocos}</td></tr>
              ))}
            </tbody>
          </table>
        </Plegable>
      )}
      <Plegable titulo="Por clase de término" nota="tendencias, no resultados, si los intervalos se traslapan" alAbrir>
        <table className="tabla-viz min-w-[560px]">
          <thead><tr><th>Modelo</th><th>Clase</th><th>Términos</th><th>Marcó ambiguo</th></tr></thead>
          <tbody>
            {r.modelos.flatMap((m) => Object.entries(m.por_clase).map(([clase, c]) => (
              <tr key={`${m.id}-${clase}`}>
                <td>{nombre(m)}</td><td>{NOMBRE_CLASE[clase] ?? clase}</td><td>{c.n}</td>
                <td>{ic(c.deteccion)}<span className="text-[var(--bone-faint)]">{c.ambiguo === false ? " · falsas alarmas" : ""}</span></td>
              </tr>
            )))}
          </tbody>
        </table>
      </Plegable>
      <Plegable titulo="Subenumeración" nota="ítems con 3 lecturas esperadas" alAbrir>
        <table className="tabla-viz min-w-[560px]">
          <thead><tr><th>Modelo</th><th>Ítems con 3 lecturas</th><th>Marcados ambiguos</th><th>Con 3 intenciones o más</th></tr></thead>
          <tbody>
            {r.modelos.map((m) => {
              const t = m.subenumeracion.con_tres;
              return <tr key={m.id}><td>{nombre(m)}</td><td>{t.n}</td><td>{t.marcados}</td><td>{t.tres_o_mas}</td></tr>;
            })}
          </tbody>
        </table>
        <p className="mt-2 max-w-3xl text-[12px] text-[var(--bone-faint)]">
          La divergencia es el coseno mínimo entre paráfrasis: si la lectura más alejada nunca se genera, el mínimo sube y un término ambiguo puede quedar por encima del umbral.
        </p>
      </Plegable>
      {r.pares.length > 0 && (
        <Plegable titulo="¿La diferencia es más que azar?" nota="McNemar exacta: detección y cada criterio" alAbrir>
          <table className="tabla-viz min-w-[720px]">
            <thead><tr><th>Modelos</th><th>Medida</th><th>n</th><th>Solo A</th><th>Solo B</th><th>p</th></tr></thead>
            <tbody>
              {r.pares.flatMap((x) => {
                const a = r.modelos.find((m) => m.id === x.a), b = r.modelos.find((m) => m.id === x.b);
                const filas = [["Detección (ambiguos)", x.deteccion], ...["fidelidad", "delimitacion", "intencion"].map((c) => [NOMBRE_CRITERIO[c], x.calidad[c]])];
                return filas.map(([medida, v], k) => (
                  <tr key={`${x.a}-${x.b}-${medida}`}>
                    <td>{k === 0 ? `A: ${nombre(a)} · B: ${nombre(b)}` : ""}</td><td>{medida}</td><td>{v.n}</td><td>{v.solo_a}</td><td>{v.solo_b}</td>
                    <td className={v.p != null && v.p < 0.05 ? "text-[var(--bone)]" : ""}>{p3(v.p)}</td>
                  </tr>
                )).concat(x.excluidos_por_intenciones ? [
                  <tr key={`${x.a}-${x.b}-ex`}><td /><td colSpan={5} className="text-[12px] text-[var(--bone-faint)]">
                    {x.excluidos_por_intenciones} ítems fuera de la comparación de calidad: los dos modelos dieron distinto número de intenciones.
                  </td></tr>] : []);
              })}
            </tbody>
          </table>
        </Plegable>
      )}
    </div>
  );
}

function FalsosNegativos({ p, r, nombre, onCambio }) {
  const rubrica = useApi(rubricaRevision, []);
  const [error, setError] = useState(null);
  const modos = rubrica.datos?.modos_falla ?? [];
  const asignar = async (modelo, item, modo) => {
    setError(null);
    try { await asignarModoFalla(p.prueba_id, { modelo, item, modo: modo || null }); onCambio(); } catch (e) { setError(e); }
  };
  return (
    <div className="space-y-6">
      <p className="max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
        Los términos ambiguos que cada modelo marcó como unívocos (o en los que falló). Elige el modo de falla que mejor lo explica:
        el reporte los cuenta por modo.
      </p>
      <Aviso error={error || rubrica.error} />
      {r.modelos.map((m) => (
        <section key={m.id} className="space-y-2">
          <h3 className="text-[15px] text-[var(--bone)]">{nombre(m)} <span className="text-[12.5px] text-[var(--bone-faint)]">· {m.falsos_negativos.items.length} falsos negativos · {m.falsos_negativos.sin_clasificar} sin clasificar</span></h3>
          {!m.falsos_negativos.items.length && <p className="text-[13px] text-[var(--bone-faint)]">— Ninguno.</p>}
          {m.falsos_negativos.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="tabla-viz min-w-[760px]">
                <thead><tr><th>Ítem</th><th>Respuesta del modelo</th><th className="w-[18rem]">Modo de falla</th></tr></thead>
                <tbody>
                  {m.falsos_negativos.items.map((x) => {
                    const res = p.resultados[m.id]?.[x.item];
                    return (
                      <tr key={x.item} className="align-top">
                        <td><span className="mono mr-2 text-[10px] text-[var(--bone-faint)]">{x.item}</span><b className="font-medium text-[var(--bone)]">{x.termino}</b></td>
                        <td className="text-[12.5px] text-[var(--bone-dim)]">
                          {res?.ok ? res.intenciones.map((i) => i.significado).join(" / ") : <span className="text-[var(--danger)]">error · {res?.error}</span>}
                        </td>
                        <td>
                          <select className="campo w-full text-[12.5px]" value={x.modo ?? ""} onChange={(e) => asignar(m.id, x.item, e.target.value)}>
                            <option value="" className="bg-[var(--bg)]">{x.sugerido ? `sin clasificar (sugerido: ${modos.find((k) => k.clave === x.sugerido)?.nombre ?? x.sugerido})` : "sin clasificar"}</option>
                            {modos.map((k) => <option key={k.clave} value={k.clave} className="bg-[var(--bg)]" title={k.descripcion}>{k.nombre}</option>)}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

function Estabilidad({ p, onCambio }) {
  const serie = p.serie || p.prueba_id;
  const { datos: e, error, recargar } = useApi(() => serieModelos(serie), [serie]);
  const [veces, setVeces] = useState(2);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(null);
  const repetir = async () => {
    setEnviando(true);
    setFallo(null);
    try { await repetirPruebaModelos(p.prueba_id, Number(veces)); recargar(); onCambio(); } catch (x) { setFallo(x); } finally { setEnviando(false); }
  };
  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
        Corre otra vez exactamente la misma configuración (modelos, términos, banco, prompt, temperatura y semilla) para medir
        cuánto cambia la detección entre corridas idénticas. Ollama con semilla debería repetir; la API de Google no garantiza
        determinismo. Las corridas van una tras otra.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="mono flex items-center gap-2 text-[10px] text-[var(--bone-faint)]">
          corridas más
          <input type="number" min="1" max="10" value={veces} onChange={(x) => setVeces(x.target.value)} className="linea w-14 py-1 text-[13px] text-[var(--bone)]" />
        </label>
        <button className="pill sm" disabled={enviando || p.estado === "en_proceso"} onClick={repetir}>{enviando ? "Creando…" : "Repetir la prueba"}</button>
      </div>
      <Aviso error={error || fallo} />
      {!e && !error && <Cargando>Cargando la serie…</Cargando>}
      {e && (
        <>
          {e.avisos.length > 0 && <ul className="space-y-1.5">{e.avisos.map((a) => <li key={a} className="text-[13px] text-[var(--aviso)]">⚠ {a}</li>)}</ul>}
          <div className="overflow-x-auto">
            <table className="tabla-viz min-w-[640px]">
              <thead><tr><th>Modelo</th><th>Ambiguos</th>{e.corridas.map((c) => <th key={c.prueba_id}>Corrida {c.corrida}</th>)}<th>Rango</th></tr></thead>
              <tbody>
                {e.modelos.map((m) => (
                  <tr key={m.etiqueta}>
                    <td className="text-[var(--bone)]">{m.etiqueta}</td><td>{m.n_ambiguos}</td>
                    {m.detecciones.map((d, k) => <td key={e.corridas[k].prueba_id}>{d ?? "—"}</td>)}
                    <td>{m.rango == null ? "—" : `${m.minimo}–${m.maximo} (${m.rango})`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mono text-[10px] text-[var(--bone-faint)]">serie {e.serie} · {e.corridas.map((c) => `${c.codigo} (${ESTADO[c.estado] ?? c.estado})`).join(" · ")}</p>
        </>
      )}
    </div>
  );
}
