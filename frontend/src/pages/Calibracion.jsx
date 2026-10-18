import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";
import {
  borrarCorridaCalibracion, calibracionEntrevistas, corridaCalibracion, corridasCalibracion, guardarCorridaCalibracion,
  obtenerConfiguracion, urlOverleaf,
} from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import EtiquetarEntrevista from "../components/calibracion/EtiquetarEntrevista";
import PruebaModelos from "../components/calibracion/PruebaModelos";
import { GraficaDebates, GraficaDistribucion, GraficaMetricas, GraficaRoc } from "../components/calibracion/graficas";
import { TIPOS } from "../constants/agentes";
import { Aviso, Cargando, Cifra, Confirmar, Pestanas, Plegable, Vacio } from "../components/ui";

/*
 * Calibración, en dos pestañas: el umbral sobre las entrevistas (abajo) y la prueba de modelos con
 * el banco de términos ambiguos (components/calibracion/PruebaModelos.jsx, ADR 0027).
 *
 * Calibración del umbral sobre las entrevistas (ADR 0026; antes, sobre los requisitos, ADR 0013).
 * Solo lectura respecto de la configuración: qué habría decidido «similitud ≥ umbral» con otros
 * umbrales y cuánto separa la similitud los términos que la persona anotadora marcó como
 * ambiguos (ROC, AUC e intervalos bootstrap). El umbral no se elige aquí ni se ajusta para que
 * los casos salgan bien: si la similitud no los separa, es un hallazgo.
 *
 * En orden: el ground truth de cada entrevista (etiquetar), los resultados en vivo, y las
 * corridas guardadas: la evidencia citable, con su paquete para Overleaf.
 */
const fmt = (x, d = 3) => (x == null ? "—" : Number(x).toFixed(d));
const ic = (m) => (m?.bajo == null ? "" : ` [${fmt(m.bajo)}, ${fmt(m.alto)}]`);
const NOMBRE_TIPO = (t) => (t === "no_ambiguo" ? "No ambiguo" : TIPOS[t]?.etiqueta ?? t);

const CLAVE_VISTA = "dudamel.calibracion.vista";
const VISTAS = [
  { id: "umbral", texto: "Umbral · entrevistas" },
  { id: "modelos", texto: "Modelos · banco de términos" },
];

export default function Calibracion() {
  const [vista, setVista] = useState(() => { try { return localStorage.getItem(CLAVE_VISTA) ?? "umbral"; } catch { return "umbral"; } });
  const cambiar = (v) => { setVista(v); try { localStorage.setItem(CLAVE_VISTA, v); } catch { /* sin almacenamiento */ } };
  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">
          {vista === "umbral" ? "Análisis de sensibilidad del umbral · entrevistas" : "Prueba de modelos · banco de términos ambiguos"}
        </p>
        <h1>Calibración.</h1>
        <Pestanas opciones={VISTAS} valor={vista} onCambio={cambiar} etiqueta="Qué se calibra" />
      </header>
      {vista === "umbral" ? <CalibracionUmbral /> : <PruebaModelos />}
    </div>
  );
}

function CalibracionUmbral() {
  const { proyectoId, proyectos, elegir } = useProyectoElegido();
  const { datos: cfg } = useApi(obtenerConfiguracion);
  const [rejilla, setRejilla] = useState({});
  const [borrador, setBorrador] = useState(null);
  const [vista, setVista] = useState(null); // una corrida guardada a la vista (si no, en vivo)
  const [etiquetando, setEtiquetando] = useState(null); // la entrevista que se está etiquetando (a ciegas)

  useEffect(() => {
    if (cfg && !borrador) setBorrador({ desde: cfg.calibracion.desde, hasta: cfg.calibracion.hasta, paso: cfg.calibracion.paso });
  }, [cfg, borrador]);
  useEffect(() => { setVista(null); setEtiquetando(null); }, [proyectoId]);

  const { datos: vivo, error, cargando, recargar } = useApi(
    () => (proyectoId ? calibracionEntrevistas(proyectoId, rejilla) : Promise.resolve(null)),
    [proyectoId, JSON.stringify(rejilla)],
  );
  const corridas = useApi(() => (proyectoId ? corridasCalibracion(proyectoId) : Promise.resolve([])), [proyectoId]);
  const c = vista?.resultado ?? vivo;

  return (
    <div className="space-y-10">
      <header className="space-y-3">
        {c && <p className="max-w-3xl text-sm text-[var(--bone-dim)]">{c.nota}</p>}
        <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos.filter((p) => p.tipo !== "evaluacion")} onCambio={elegir} />
      </header>

      {vista && (
        <div className="tarjeta flex flex-wrap items-center gap-3 border-[color-mix(in_oklab,var(--c1)_45%,var(--line))] p-4">
          <p className="text-[14px]">Estás viendo la corrida guardada <b className="font-medium">{vista.calibracion_id}</b> del {vista.fecha.slice(0, 10)}{vista.nota ? ` · ${vista.nota}` : ""}.</p>
          <button className="pill ghost sm ml-auto" onClick={() => setVista(null)}>Volver a los datos en vivo</button>
        </div>
      )}

      {c && <Configuracion c={c} />}
      {!vista && borrador && (
        <form className="mono flex flex-wrap items-end gap-4 text-[10px] text-[var(--bone-faint)]" onSubmit={(e) => { e.preventDefault(); setRejilla({ ...borrador }); }}>
          {["desde", "hasta", "paso"].map((k) => (
            <label key={k} className="block">
              <span className="mb-1 block">{k}</span>
              <input type="number" step="0.01" min={k === "paso" ? 0.001 : 0} max="1" value={borrador[k]}
                onChange={(e) => setBorrador((b) => ({ ...b, [k]: e.target.value }))} className="linea w-20 py-1 text-[13px] text-[var(--bone)]" />
            </label>
          ))}
          <button className="pill ghost sm">Recalcular la rejilla</button>
        </form>
      )}

      {error && !vista && <Aviso error={error} />}
      {!c && cargando && <Cargando>Calculando la calibración…</Cargando>}
      {c && c.avisos.length > 0 && (
        <ul className="space-y-1.5">
          {c.avisos.map((a) => <li key={a} className="text-[13px] text-[#ffc457]">⚠ {a}</li>)}
        </ul>
      )}

      {!vista && vivo && <GroundTruth c={vivo} onCambio={recargar} abierta={etiquetando} onAbrir={setEtiquetando} />}
      {/* a ciegas: mientras alguien etiqueta, nada de esta página muestra similitudes ni decisiones */}
      {etiquetando && (
        <p className="tarjeta p-4 text-[13.5px] text-[var(--bone-dim)]">
          Los resultados y las corridas están ocultos mientras etiquetas, para que la similitud del sistema no influya en tus respuestas.
          Aparecen al cerrar el etiquetado.
        </p>
      )}
      {!etiquetando && c && c.n_valores > 0 && <Resultados c={c} />}
      {c && c.n_valores === 0 && (
        <Vacio>Ninguna entrevista terminada de este proyecto tiene términos que hayan llegado al mecanismo de divergencia. Procesa una entrevista con términos ambiguos y vuelve aquí.</Vacio>
      )}

      {proyectoId && !etiquetando && (
        <Corridas proyectoId={proyectoId} corridas={corridas} rejilla={rejilla} hayDatos={vivo?.n_valores > 0}
          vista={vista} onVer={setVista} />
      )}
    </div>
  );
}

function Configuracion({ c }) {
  return (
    <p className="mono flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-[var(--bone-faint)]">
      <span>umbral configurado <b className="font-normal text-[var(--bone)]">{c.umbral_configurado}</b></span>
      <span>rondas máx. <b className="font-normal text-[var(--bone)]">{c.max_rondas}</b></span>
      <span>rejilla {c.parametros.desde}–{c.parametros.hasta} · paso {c.parametros.paso}</span>
      <span>embeddings <b className="font-normal text-[var(--bone)]">{c.modelos_embeddings.join(", ") || "—"}</b></span>
      {c.modelos_clasificador.length > 0 && <span>clasificador <b className="font-normal text-[var(--bone)]">{c.modelos_clasificador.join(", ")}</b></span>}
    </p>
  );
}

/* El ground truth: cada entrevista, quién la etiquetó y el etiquetado a ciegas con teclado (ADR 0029) */
function GroundTruth({ c, onCambio, abierta, onAbrir: setAbierta }) {
  return (
    <section className="space-y-4">
      <div>
        <h2>Ground truth</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
          En cada entrevista, qué términos de los que llegaron a la divergencia eran de verdad ambiguos. Se etiqueta a ciegas (sin ver
          la similitud ni la decisión del sistema), con el teclado (S sí, N no, X no sé) y en un orden barajado. Si dos personas
          etiquetan la misma entrevista, cuentan los términos en que coinciden y se calcula la kappa de Cohen.
        </p>
      </div>
      {!c.entrevistas.length && <Vacio>Este proyecto no tiene entrevistas terminadas.</Vacio>}
      <ul className="space-y-3">
        {c.entrevistas.map((e) => (
          <li key={e.entrevista_id} className="tarjeta space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="mono text-[10px] text-[var(--bone-faint)]">{e.entrevista_id}</span>
              <span className="text-[15px]">{e.titulo}</span>
              <span className="text-[12.5px] text-[var(--bone-dim)]">
                {e.n_valores} con similitud · {e.n_etiquetas ? `${e.n_etiquetas} en el ground truth` : e.anotadores?.length ? "0 en el ground truth (sin acuerdo todavía)" : "sin etiquetar"}
                {e.anotadores?.length ? ` · ${e.anotadores.join(", ")}` : ""}
              </span>
              <button className={`pill sm ml-auto ${e.n_etiquetas ? "ghost" : ""}`} disabled={!e.n_valores}
                onClick={() => setAbierta(abierta === e.entrevista_id ? null : e.entrevista_id)}>
                {abierta === e.entrevista_id ? "Ocultar" : "Etiquetar"}
              </button>
            </div>
            {abierta === e.entrevista_id && <EtiquetarEntrevista entrevistaId={e.entrevista_id} onCambio={onCambio} onCerrar={() => setAbierta(null)} />}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Resultados({ c }) {
  const gt = c.con_ground_truth;
  const m = gt?.confianza?.medidas ?? {};
  const conf = gt?.configurado;
  return (
    <section className="space-y-6">
      <h2>Resultados</h2>
      {gt && (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
          <Cifra valor={`${gt.n_emparejados}`} nombre={`términos etiquetados (${gt.n_ambiguos} ambiguos)`} />
          <Cifra valor={fmt(gt.auc)} nombre={`AUC${ic(m.auc)}`} />
          <Cifra valor={fmt(conf?.f1)} nombre={`F1 con ${c.umbral_configurado}${ic(m.f1)}`} />
          <Cifra valor={gt.separacion.separa == null ? "—" : gt.separacion.separa ? "sí" : "no"} nombre="¿algún umbral separa los casos?" />
        </div>
      )}
      {gt && (
        <p className="text-[12px] text-[var(--bone-faint)]">
          Entre corchetes, intervalos bootstrap percentil al {Math.round(gt.confianza.nivel * 100)} % ({gt.confianza.remuestreos} remuestreos, semilla {gt.confianza.semilla}).
          Positivo = «va a debate» (similitud &lt; umbral); la verdad es «ambiguo».
        </p>
      )}

      <GraficaDistribucion valores={c.valores} umbral={c.umbral_configurado} />
      {gt && (
        <div className="grid gap-6 xl:grid-cols-2">
          {gt.por_umbral.some((f) => f.f1 != null || f.precision != null || f.exhaustividad != null) &&
            <GraficaMetricas porUmbral={gt.por_umbral} umbral={c.umbral_configurado} confianza={gt.confianza} parametros={c.parametros} />}
          {gt.roc.length > 0 && <GraficaRoc roc={gt.roc} auc={gt.auc} ic={m.auc} banda={gt.roc_banda} />}
        </div>
      )}
      <GraficaDebates rejilla={c.rejilla} umbral={c.umbral_configurado} n={c.n_valores} parametros={c.parametros} />

      {gt && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="tarjeta space-y-2 p-4">
            <p className="etiqueta">Matriz de confusión · umbral {c.umbral_configurado}</p>
            <table className="tabla-viz">
              <thead><tr><th /><th>A debate</th><th>Aceptado directo</th></tr></thead>
              <tbody>
                <tr><td>Ambiguo</td><td>{conf.vp} <span className="text-[var(--bone-faint)]">VP</span></td><td>{conf.fn} <span className="text-[var(--bone-faint)]">FN</span></td></tr>
                <tr><td>No ambiguo</td><td>{conf.fp} <span className="text-[var(--bone-faint)]">FP</span></td><td>{conf.vn} <span className="text-[var(--bone-faint)]">VN</span></td></tr>
              </tbody>
            </table>
          </div>
          <div className="tarjeta space-y-2 p-4">
            <p className="etiqueta">Por tipo de ambigüedad · umbral {c.umbral_configurado}</p>
            <table className="tabla-viz">
              <thead><tr><th>Tipo</th><th>Términos</th><th>A debate</th><th>Proporción</th></tr></thead>
              <tbody>
                {gt.por_tipo.map((t) => (
                  <tr key={t.tipo}><td>{NOMBRE_TIPO(t.tipo)}</td><td>{t.n}</td><td>{t.a_debate}</td><td>{fmt(t.proporcion, 2)}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11.5px] text-[var(--bone-faint)]">En los no ambiguos, ir a debate es un falso positivo.</p>
          </div>
        </div>
      )}

      {gt?.acuerdo?.length > 0 && (
        <div className="tarjeta space-y-2 p-4">
          <p className="etiqueta">Acuerdo entre personas anotadoras · kappa de Cohen</p>
          <table className="tabla-viz">
            <thead><tr><th>Entrevista</th><th>Persona A</th><th>Persona B</th><th>Términos</th><th>Acuerdo observado</th><th>κ</th></tr></thead>
            <tbody>
              {gt.acuerdo.map((k) => (
                <tr key={`${k.entrevista_id}-${k.a}-${k.b}`}><td className="mono text-[10px]">{k.entrevista_id}</td><td>{k.a}</td><td>{k.b}</td><td>{k.n}</td><td>{fmt(k.acuerdo_observado, 2)}</td><td>{fmt(k.kappa, 2)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11.5px] text-[var(--bone-faint)]">
            {gt.desacuerdos?.length ?? 0} términos en desacuerdo y {gt.solo_no_se ?? 0} solo con «no sé» quedan fuera del ground truth.
          </p>
        </div>
      )}

      <Plegable titulo="Tabla por umbral" nota={`${c.rejilla.length} umbrales`} alAbrir>
        <TablaRejilla c={c} />
      </Plegable>
      <Plegable titulo="Valores" nota={`${c.n_valores} términos`} alAbrir>
        <TablaValores c={c} />
      </Plegable>
      {gt && (gt.etiquetas_sin_similitud.length > 0 || gt.valores_sin_etiqueta.length > 0) && (
        <p className="text-[12.5px] text-[var(--bone-faint)]">
          {gt.etiquetas_sin_similitud.length} etiquetas sin similitud (el sistema no generó dos intenciones para ese término: ningún umbral puede corregirlo)
          · {gt.valores_sin_etiqueta.length} similitudes sin etiqueta en entrevistas etiquetadas.
        </p>
      )}
    </section>
  );
}

function TablaRejilla({ c }) {
  const met = Object.fromEntries((c.con_ground_truth?.por_umbral ?? []).map((f) => [f.umbral, f]));
  return (
    <div className="overflow-x-auto">
      <table className="tabla-viz min-w-[560px]">
        <thead><tr><th>Umbral</th><th>Directos</th><th>A debate</th><th>Cambian</th><th>Precisión</th><th>Exhaustividad</th><th>F1</th></tr></thead>
        <tbody>
          {c.rejilla.map((f) => {
            const g = met[f.umbral] ?? {};
            return (
              <tr key={f.umbral} className={f.configurado ? "es-configurado" : ""}>
                <td>{f.umbral}{f.configurado ? " ←" : ""}</td><td>{f.directos}</td><td>{f.debates}</td><td>{f.cambian.length}</td>
                <td>{fmt(g.precision)}</td><td>{fmt(g.exhaustividad)}</td><td>{fmt(g.f1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TablaValores({ c }) {
  const via = { aceptado_directo: "directo", consenso: "consenso", arbitraje: "arbitraje" };
  return (
    <div className="overflow-x-auto">
      <table className="tabla-viz min-w-[640px]">
        <thead><tr><th>Entrevista</th><th>Término</th><th>Similitud</th><th>Ground truth</th><th>Decisión</th><th>Vía final</th><th>Tipo (sistema)</th></tr></thead>
        <tbody>
          {[...c.valores].sort((a, b) => a.similitud - b.similitud).map((v) => (
            <tr key={`${v.entrevista_id}:${v.termino}`}>
              <td className="mono text-[10px]">{v.entrevista_id}</td><td>{v.termino}</td><td>{fmt(v.similitud)}</td>
              <td>{v.ambiguo == null ? "—" : v.ambiguo ? "ambiguo" : "no ambiguo"}</td>
              <td>{v.decision_real === "en_debate" ? "debate" : "directo"}</td><td>{via[v.via] ?? "—"}</td>
              <td className="text-[var(--bone-dim)]">{TIPOS[v.tipo_ambiguedad]?.etiqueta ?? v.tipo_ambiguedad}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* Las corridas guardadas: la evidencia citable de la tesis, con su paquete para Overleaf */
function Corridas({ proyectoId, corridas, rejilla, hayDatos, vista, onVer }) {
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [borrando, setBorrando] = useState(null);
  const lista = corridas.datos ?? [];

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try { await guardarCorridaCalibracion(proyectoId, nota.trim(), rejilla); setNota(""); corridas.recargar(); } catch (e) { setError(e); } finally { setGuardando(false); }
  };
  const descargar = async (cid) => {
    setError(null);
    try {
      const r = await fetch(urlOverleaf(cid), { credentials: "include" });
      if (!r.ok) throw new Error(`No se pudo descargar el paquete (HTTP ${r.status}).`);
      const url = URL.createObjectURL(await r.blob());
      Object.assign(document.createElement("a"), { href: url, download: `dudamel-calibracion-${cid}.zip` }).click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e); }
  };
  const ver = async (cid) => {
    setError(null);
    try { onVer(await corridaCalibracion(cid)); scrollTo({ top: 0 }); } catch (e) { setError(e); }
  };

  return (
    <section className="space-y-4">
      <div>
        <h2>Corridas guardadas</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-[var(--bone-dim)]">
          Una corrida congela los resultados de ahora con su fecha, la configuración, la versión de la app y una huella de las
          similitudes y etiquetas de cada entrevista. Es lo que se cita en la tesis; su paquete trae las figuras (pgfplots),
          las tablas (booktabs) y los datos para Overleaf.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input value={nota} onChange={(e) => setNota(e.target.value)} maxLength={500} placeholder="Nota (p. ej. «corpus completo, nomic-embed-text»)"
          className="campo w-96 max-w-full text-[13px]" />
        <button className="pill sm" onClick={guardar} disabled={guardando || !hayDatos}>{guardando ? "Guardando…" : "Guardar corrida"}</button>
      </div>
      <Aviso error={error || corridas.error} />
      {!lista.length && !corridas.cargando && <p className="text-[13px] text-[var(--bone-faint)]">Todavía no hay corridas guardadas en este proyecto.</p>}
      {lista.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tabla-viz min-w-[720px]">
            <thead><tr><th>Corrida</th><th>Fecha</th><th>Nota</th><th>Términos</th><th>AUC</th><th>F1</th><th>¿Separa?</th><th /></tr></thead>
            <tbody>
              {lista.map((k) => (
                <tr key={k.calibracion_id} className={vista?.calibracion_id === k.calibracion_id ? "es-configurado" : ""}>
                  <td className="mono text-[11px]">{k.calibracion_id}</td>
                  <td>{k.fecha.replace("T", " ").slice(0, 16)}</td>
                  <td className="max-w-[16rem] truncate text-[var(--bone-dim)]">{k.nota ?? "—"}</td>
                  <td>{k.n_valores}{k.n_emparejados ? ` (${k.n_emparejados} etiq.)` : ""}</td>
                  <td>{fmt(k.auc)}<span className="text-[var(--bone-faint)]">{ic(k.auc_ic)}</span></td>
                  <td>{fmt(k.f1)}<span className="text-[var(--bone-faint)]">{ic(k.f1_ic)}</span></td>
                  <td>{k.separa == null ? "—" : k.separa ? "sí" : "no"}</td>
                  <td className="whitespace-nowrap text-right">
                    <button className="pill ghost sm" onClick={() => ver(k.calibracion_id)}>Ver</button>{" "}
                    <button className="pill sm" onClick={() => descargar(k.calibracion_id)}>Overleaf ↓</button>{" "}
                    <button className="mono px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => setBorrando(k)}>borrar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {borrando && (
        <Confirmar pregunta={`¿Borrar la corrida ${borrando.calibracion_id}?`} detalle="Si ya la citaste en la tesis, descarga antes su paquete." accion="Borrar corrida"
          onCancelar={() => setBorrando(null)}
          onConfirmar={async () => { await borrarCorridaCalibracion(borrando.calibracion_id); if (vista?.calibracion_id === borrando.calibracion_id) onVer(null); setBorrando(null); corridas.recargar(); }} />
      )}
    </section>
  );
}
