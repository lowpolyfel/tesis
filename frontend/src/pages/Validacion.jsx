import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useRequisito } from "../hooks/useRequisito";
import { formalizarRequisito, guardarBorrador, rechazarArtefactos, validarArtefactos } from "../services/api";
import { ESTADOS as E } from "../constants/estados";
import { TIPOS_LEL } from "../constants/agentes";
import EstadoBadge from "../components/EstadoBadge";
import EditorJSON from "../components/EditorJSON";
import ListaEditable from "../components/ListaEditable";

/*
 * Pantalla 5: la persona revisa y EDITA los tres artefactos antes de
 * aprobarlos. A la izquierda la propuesta del agente, a la derecha su
 * versión; cada sección indica si difiere y permite volver a la del agente.
 */
const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const clonar = (x) => structuredClone(x);

export default function Validacion() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { requisito: r, recargar } = useRequisito(id);
  const [trabajo, setTrabajo] = useState(null);
  const [errorJson, setErrorJson] = useState(null);
  const [comentario, setComentario] = useState("");
  const [aviso, setAviso] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [versionJson, setVersionJson] = useState(0); // remonta el editor al restaurar

  useEffect(() => {
    if (r?.artefactos && !trabajo) {
      setTrabajo(clonar(r.artefactos.validados ?? r.artefactos.borrador ?? r.artefactos.propuesta));
    }
  }, [r, trabajo]);

  if (!r) return <p className="text-sm text-slate-500">Cargando {id}…</p>;
  if (!r.artefactos) {
    return (
      <p className="text-sm">
        {id} todavía no tiene artefactos (estado actual: <EstadoBadge estado={r.estado} />).{" "}
        <Link className="underline" to={`/requisitos/${id}`}>Ver su traza</Link>
      </p>
    );
  }
  if (!trabajo) return null;

  const propuesta = r.artefactos.propuesta;
  const editable = r.estado === E.PENDIENTE_VALIDACION;
  const cambios = ["lel", "metas", "bigPicture"].filter((k) => !igual(trabajo[k], propuesta[k]));
  const set = (k) => (v) => setTrabajo((t) => ({ ...t, [k]: v }));

  const accion = async (fn, mensaje, destino) => {
    setOcupado(true);
    try {
      await fn();
      setAviso(mensaje);
      if (destino) navigate(destino);
      else recargar();
    } catch (e) {
      setAviso(`Error: ${e.message}`);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-5 pb-24">
      <header className="space-y-2">
        <nav className="text-sm text-slate-500">
          <Link to="/historial" className="hover:underline">Historial</Link> /{" "}
          <Link to={`/requisitos/${id}`} className="hover:underline">{id}</Link> / validación
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">Validación de artefactos</h1>
          <EstadoBadge estado={r.estado} className="text-sm" />
        </div>
        <p className="font-serif text-lg">«{r.texto}»</p>
        <p className="text-sm text-slate-600">
          <span className="text-slate-500">Interpretación resuelta: </span>{r.traza.resolucion.interpretacion}
        </p>
        {!editable && (
          <p className="rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
            Solo lectura: el requisito ya está en estado «{r.estado}». Se muestra la versión {r.artefactos.validados ? "validada" : "propuesta"}.
          </p>
        )}
      </header>

      <Seccion
        titulo="1. Entrada del LEL"
        modificado={!igual(trabajo.lel, propuesta.lel)}
        restaurar={editable && (() => set("lel")(clonar(propuesta.lel)))}
        agente={<LelLectura lel={propuesta.lel} />}
      >
        {editable ? <LelEditor lel={trabajo.lel} onChange={set("lel")} /> : <LelLectura lel={trabajo.lel} />}
      </Seccion>

      <Seccion
        titulo="2. Modelo de metas"
        modificado={!igual(trabajo.metas, propuesta.metas)}
        restaurar={editable && (() => set("metas")(clonar(propuesta.metas)))}
        agente={<MetasLectura metas={propuesta.metas} />}
      >
        {editable ? <MetasEditor metas={trabajo.metas} onChange={set("metas")} /> : <MetasLectura metas={trabajo.metas} />}
      </Seccion>

      <Seccion
        titulo="3. Big Picture (JSON)"
        modificado={!igual(trabajo.bigPicture, propuesta.bigPicture)}
        restaurar={editable && (() => {
          setErrorJson(null);
          set("bigPicture")(clonar(propuesta.bigPicture));
          setVersionJson((v) => v + 1);
        })}
        agente={<pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(propuesta.bigPicture, null, 2)}</pre>}
      >
        {editable ? (
          <EditorJSON
            key={versionJson}
            valor={trabajo.bigPicture}
            onChange={set("bigPicture")}
            onErrorChange={setErrorJson}
          />
        ) : (
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(trabajo.bigPicture, null, 2)}</pre>
        )}
      </Seccion>

      {aviso && <p className="text-sm text-slate-700">{aviso}</p>}

      {editable && (
        <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-slate-200 bg-[color-mix(in_oklab,var(--bg)_88%,transparent)] px-4 py-3 backdrop-blur md:left-[30vw]">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2">
            <input
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              placeholder="Comentario (obligatorio para rechazar)"
              className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
            <span className="text-xs text-slate-500">
              {cambios.length ? `Editaste: ${cambios.length} de 3 artefactos` : "Sin cambios respecto al agente"}
            </span>
            <button
              disabled={ocupado}
              onClick={() => accion(() => guardarBorrador(id, trabajo), "Borrador guardado.")}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            >
              Guardar borrador
            </button>
            <button
              disabled={ocupado || !comentario.trim()}
              title={!comentario.trim() ? "Escribe un comentario para rechazar" : ""}
              onClick={() => accion(() => rechazarArtefactos(id, comentario), "Rechazado.", `/requisitos/${id}`)}
              className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 disabled:opacity-40"
            >
              Rechazar
            </button>
            <button
              disabled={ocupado || Boolean(errorJson)}
              title={errorJson ? "Corrige el JSON del Big Picture" : ""}
              onClick={() => accion(() => validarArtefactos(id, trabajo, { comentario, editado: cambios.length > 0 }), "Validado.")}
              className="rounded bg-green-700 px-4 py-1.5 text-sm font-medium text-sobre disabled:opacity-40"
            >
              Aprobar {cambios.length ? "con mis cambios" : "tal cual"}
            </button>
          </div>
        </footer>
      )}

      {r.estado === E.VALIDADO && (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
          <span>Validado. El último paso es formalizar: incorporar la entrada al LEL acumulado.</span>
          <button
            disabled={ocupado}
            onClick={() => accion(() => formalizarRequisito(id), "Formalizado.", "/lel")}
            className="ml-auto rounded bg-slate-900 px-3 py-1.5 font-medium text-sobre"
          >
            Formalizar
          </button>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- */

function Seccion({ titulo, modificado, restaurar, agente, children }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide">{titulo}</h2>
        {modificado
          ? <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-800">editado</span>
          : <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">igual a la propuesta</span>}
        {restaurar && modificado && (
          <button onClick={restaurar} className="ml-auto text-xs text-slate-600 underline">Restaurar la versión del agente</button>
        )}
      </header>
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="min-w-0 rounded bg-slate-50 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Propuesta del Modelador</p>
          {agente}
        </div>
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Tu versión</p>
          {children}
        </div>
      </div>
    </section>
  );
}

const Etiqueta = ({ children }) => <p className="mb-0.5 text-xs font-medium text-slate-500">{children}</p>;

function LelLectura({ lel }) {
  return (
    <dl className="space-y-2 text-sm">
      <div><Etiqueta>Símbolo</Etiqueta><p className="font-semibold">{lel.simbolo} <span className="font-normal text-slate-500">({lel.tipo})</span></p></div>
      {lel.sinonimos?.length > 0 && <div><Etiqueta>Sinónimos</Etiqueta><p>{lel.sinonimos.join(", ")}</p></div>}
      <div><Etiqueta>Noción</Etiqueta><ul className="list-disc pl-5">{lel.nocion.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
      <div><Etiqueta>Impacto</Etiqueta><ul className="list-disc pl-5">{lel.impacto.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
    </dl>
  );
}

function LelEditor({ lel, onChange }) {
  const set = (k) => (v) => onChange({ ...lel, [k]: v });
  return (
    <div className="space-y-3 text-sm">
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <label>
          <Etiqueta>Símbolo</Etiqueta>
          <input value={lel.simbolo} onChange={(e) => set("simbolo")(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1" />
        </label>
        <label>
          <Etiqueta>Tipo</Etiqueta>
          <select value={lel.tipo} onChange={(e) => set("tipo")(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
            {TIPOS_LEL.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
      </div>
      <label className="block">
        <Etiqueta>Sinónimos (separados por coma)</Etiqueta>
        <input
          value={(lel.sinonimos ?? []).join(", ")}
          onChange={(e) => set("sinonimos")(e.target.value.split(",").map((x) => x.trim()).filter(Boolean))}
          className="w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <div><Etiqueta>Noción</Etiqueta><ListaEditable valores={lel.nocion} onChange={set("nocion")} /></div>
      <div><Etiqueta>Impacto</Etiqueta><ListaEditable valores={lel.impacto} onChange={set("impacto")} /></div>
    </div>
  );
}

function MetasLectura({ metas }) {
  return (
    <div className="space-y-2 text-sm">
      <div><Etiqueta>Meta estratégica</Etiqueta><p className="font-semibold">{metas.metaEstrategica}</p></div>
      <div>
        <Etiqueta>Submetas</Etiqueta>
        <ul className="space-y-1">
          {metas.submetas.map((m) => (
            <li key={m.id} className="flex gap-2">
              <span className="font-mono text-xs text-slate-500">{m.id}</span>
              <span className="flex-1">{m.descripcion}</span>
              <span className={`h-fit rounded px-1.5 text-xs ${m.tipo === "dura" ? "bg-slate-200" : "bg-sky-100 text-sky-800"}`}>{m.tipo}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function MetasEditor({ metas, onChange }) {
  const editarSub = (i, campo, v) =>
    onChange({ ...metas, submetas: metas.submetas.map((m, j) => (j === i ? { ...m, [campo]: v } : m)) });
  const agregar = () =>
    onChange({ ...metas, submetas: [...metas.submetas, { id: `M${metas.submetas.length + 1}`, descripcion: "", tipo: "dura" }] });

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <Etiqueta>Meta estratégica</Etiqueta>
        <input value={metas.metaEstrategica} onChange={(e) => onChange({ ...metas, metaEstrategica: e.target.value })} className="w-full rounded border border-slate-300 px-2 py-1" />
      </label>
      <div className="space-y-1.5">
        <Etiqueta>Submetas</Etiqueta>
        {metas.submetas.map((m, i) => (
          <div key={i} className="flex gap-1.5">
            <input value={m.id} onChange={(e) => editarSub(i, "id", e.target.value)} className="w-12 rounded border border-slate-300 px-1 py-1 font-mono text-xs" />
            <input value={m.descripcion} onChange={(e) => editarSub(i, "descripcion", e.target.value)} className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1" />
            <select value={m.tipo} onChange={(e) => editarSub(i, "tipo", e.target.value)} className="rounded border border-slate-300 px-1 py-1">
              <option value="dura">dura</option>
              <option value="blanda">blanda</option>
            </select>
            <button type="button" onClick={() => onChange({ ...metas, submetas: metas.submetas.filter((_, j) => j !== i) })} className="px-1 text-slate-400 hover:text-red-600" aria-label="Quitar">✕</button>
          </div>
        ))}
        <button type="button" onClick={agregar} className="text-xs text-slate-600 underline">+ agregar submeta</button>
      </div>
    </div>
  );
}
