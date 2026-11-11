import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useApi } from "../hooks/useApi";
import {
  cuestionario, enviarCuestionario, guardarCuestionario,
} from "../services/backend";
import { Aviso, Cargando, Encabezado, Volver } from "../components/ui";

/*
 * Cuestionario de evaluación de la experiencia (ADR 0032, docs/cuestionario-evaluacion.md).
 * Uno por cuenta; se abre cuando la cuenta terminó al menos un proyecto hasta los requisitos.
 * Se guarda solo mientras se contesta (borrador) y se envía al final. Abajo, el acceso a los
 * resultados (ResultadosCuestionario.jsx; todas las cuentas, salvo que CUESTIONARIO_ADMINS los limite).
 */
export default function Cuestionario() {
  const { datos, error, recargar } = useApi(cuestionario);
  return (
    <div className="space-y-8">
      <Encabezado volver={<Volver a="/proyectos">Proyectos</Volver>} antetitulo="Evaluación" titulo="Cuestionario de la experiencia" />
      <Aviso error={error} />
      {!datos && !error && <Cargando>Cargando el cuestionario…</Cargando>}
      {datos && !datos.disponible && <Cerrado motivo={datos.motivo} />}
      {datos?.disponible && <Formulario datos={datos} alCambiar={recargar} />}
      {datos?.es_admin && <AccesoResultados />}
    </div>
  );
}

function Cerrado({ motivo }) {
  return (
    <div className="tarjeta space-y-3 p-6">
      <p className="text-[15px]"><span aria-hidden="true">🔒</span> Todavía no está abierto.</p>
      <p className="max-w-xl text-[14px] leading-relaxed text-[var(--bone-dim)]">{motivo} El cuestionario compara tu experiencia a mano con la del sistema, así que se contesta después de recorrer el camino completo: entrevista, léxico, mapa conceptual, metas y requisitos.</p>
      <Link to="/proyectos" className="pill ghost sm">Ir a mis proyectos</Link>
    </div>
  );
}

/* ---------------------------------------------------------------- formulario */

const vacia = (v) => v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);

function Formulario({ datos, alCambiar }) {
  const { preguntas: q, respuesta } = datos;
  const todas = useMemo(() => q.secciones.flatMap((s) => s.preguntas), [q]);
  const [resp, setResp] = useState(() => respuesta?.respuestas ?? {});
  const [base, setBase] = useState(() => respuesta?.respuestas ?? {}); // lo enviado, para «Cancelar»
  const [estado, setEstado] = useState(respuesta?.estado ?? "borrador");
  const [editando, setEditando] = useState(respuesta?.estado !== "enviado");
  const [guardado, setGuardado] = useState(respuesta?.actualizado ?? null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [faltan, setFaltan] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const sucio = useRef(false);

  const obligatorias = todas.filter((p) => p.obligatoria);
  const contestadas = obligatorias.filter((p) => !vacia(resp[p.id])).length;
  const pendientes = obligatorias.filter((p) => vacia(resp[p.id]));

  /* Borrador: se guarda solo, un momento después del último cambio */
  useEffect(() => {
    if (!sucio.current || estado === "enviado") return undefined;
    const t = setTimeout(async () => {
      setGuardando(true);
      try {
        const r = await guardarCuestionario(resp);
        sucio.current = false;
        setGuardado(r.actualizado);
        setError(null);
      } catch (e) {
        setError(e);
      } finally {
        setGuardando(false);
      }
    }, 900);
    return () => clearTimeout(t);
  }, [resp, estado]);

  const cambiar = (id, valor) => {
    sucio.current = true;
    setResp((r) => ({ ...r, [id]: valor }));
    setFaltan((f) => f.filter((x) => x !== id));
  };

  const irA = (id) => document.getElementById(`pregunta-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });

  const enviar = async () => {
    if (pendientes.length) {
      setFaltan(pendientes.map((p) => p.id));
      irA(pendientes[0].id);
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const r = estado === "enviado" ? await guardarCuestionario(resp) : await enviarCuestionario(resp);
      sucio.current = false;
      setBase(r.respuestas);
      setEstado(r.estado);
      setGuardado(r.actualizado);
      setEditando(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
      alCambiar?.();
    } catch (e) {
      setError(e);
      if (e.detalle?.faltantes) setFaltan(e.detalle.faltantes);
    } finally {
      setEnviando(false);
    }
  };

  if (estado === "enviado" && !editando) {
    return (
      <div className="tarjeta space-y-3 p-6">
        <p className="serif text-[26px] leading-tight">¡Gracias! Tu cuestionario quedó enviado.</p>
        <p className="max-w-xl text-[14px] leading-relaxed text-[var(--bone-dim)]">Tus respuestas se guardaron con tu cuenta solo para que no se conteste dos veces; en los resultados aparecen sin tu nombre ni tu correo. Si quieres corregir algo, puedes revisarlas.</p>
        <button className="pill ghost sm" onClick={() => setEditando(true)}>Revisar mis respuestas</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="tarjeta space-y-3 p-6">
        {q.presentacion.split("\n\n").map((p) => <p key={p} className="max-w-2xl text-[14.5px] leading-relaxed text-[var(--bone-dim)]">{p}</p>)}
        <p className="mono text-[10.5px] text-[var(--bone-faint)]">Puedes dejarlo a medias: se guarda solo y lo retomas después desde el lobby de proyectos.</p>
      </div>

      <Progreso contestadas={contestadas} total={obligatorias.length} guardando={guardando} guardado={guardado} enviado={estado === "enviado"} />

      {q.secciones.map((s, i) => (
        <section key={s.id} className="tarjeta space-y-6 p-5 sm:p-6" aria-labelledby={`titulo-${s.id}`}>
          <header className="space-y-1.5">
            <p className="etiqueta">Sección {i + 1} de {q.secciones.length}</p>
            <p id={`titulo-${s.id}`} role="heading" aria-level={2} className="serif text-[24px] leading-tight">{s.titulo}</p>
            {s.instruccion && <p className="max-w-2xl text-[14px] leading-relaxed text-[var(--bone-dim)]">{s.instruccion}</p>}
          </header>
          {s.preguntas.map((p) => (
            <Pregunta key={p.id} p={p} valor={resp[p.id]} onCambio={(v) => cambiar(p.id, v)} falta={faltan.includes(p.id)} />
          ))}
        </section>
      ))}

      <div className="tarjeta space-y-3 p-5">
        {faltan.length > 0 && (
          <div className="space-y-2">
            <p className="text-[14px] text-[var(--danger)]">Faltan {faltan.length} pregunta(s) obligatoria(s):</p>
            <p className="flex flex-wrap gap-1.5">
              {faltan.map((id) => {
                const p = todas.find((x) => x.id === id);
                return <button key={id} className="pill ghost sm" onClick={() => irA(id)}>{p ? p.n : id}</button>;
              })}
            </p>
          </div>
        )}
        <Aviso error={error} />
        <div className="flex flex-wrap items-center gap-3">
          <button className="pill" onClick={enviar} disabled={enviando}>
            {enviando ? "Enviando…" : estado === "enviado" ? "Guardar cambios" : "Enviar cuestionario"}
          </button>
          {estado === "enviado" && <button className="pill ghost sm" onClick={() => { setEditando(false); setResp(base); setFaltan([]); }}>Cancelar</button>}
          <span className="mono text-[10.5px] text-[var(--bone-faint)]">{contestadas} de {obligatorias.length} obligatorias</span>
        </div>
      </div>
    </div>
  );
}

function Progreso({ contestadas, total, guardando, guardado, enviado }) {
  const pct = total ? Math.round((contestadas / total) * 100) : 0;
  return (
    <div className="sticky top-[68px] z-20 rounded-2xl md:top-[76px] border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_88%,transparent)] px-4 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="mono text-[10.5px] text-[var(--bone-dim)]">{contestadas} / {total} obligatorias · {pct}%</span>
        <span className="mono text-[10px] text-[var(--bone-faint)]" aria-live="polite">
          {enviado ? "Enviado: los cambios se guardan con «Guardar cambios»"
            : guardando ? "Guardando…" : guardado ? `Guardado ${new Date(guardado).toLocaleTimeString()}` : "Sin guardar todavía"}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[color-mix(in_oklab,var(--bone)_10%,transparent)]" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-[var(--c1)] transition-[width]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- una pregunta */

function Pregunta({ p, valor, onCambio, falta }) {
  return (
    <fieldset id={`pregunta-${p.id}`} className={`space-y-3 rounded-xl ${falta ? "outline outline-1 outline-offset-8 outline-[var(--danger)]" : ""}`}>
      <legend className="text-[15px] leading-relaxed">
        <span className="mono mr-2 text-[11px] text-[var(--bone-faint)]">{p.n}.</span>{p.texto}
        {!p.obligatoria && <span className="ml-2 text-[12px] text-[var(--bone-faint)]">(opcional)</span>}
      </legend>
      {p.tipo === "opcion" && <Opciones p={p} valor={valor} onCambio={onCambio} />}
      {p.tipo === "casillas" && <Casillas p={p} valor={valor ?? []} onCambio={onCambio} />}
      {p.tipo === "escala" && <Escala p={p} valor={valor} onCambio={onCambio} />}
      {p.tipo === "numero" && (
        <div className="flex flex-wrap items-center gap-3">
          <input type="number" inputMode="numeric" min={0} max={10000} step={1} className="campo w-32 text-[15px]"
            value={valor ?? ""} aria-label={`Respuesta a la pregunta ${p.n}`}
            onChange={(e) => onCambio(e.target.value === "" ? null : Math.max(0, Math.min(10000, Math.trunc(Number(e.target.value)))))} />
          {p.ayuda && <span className="text-[12.5px] text-[var(--bone-faint)]">{p.ayuda}</span>}
        </div>
      )}
      {p.tipo === "texto" && (
        <textarea className="campo text-[14.5px]" rows={3} maxLength={4000} value={valor ?? ""}
          aria-label={`Respuesta a la pregunta ${p.n}`} onChange={(e) => onCambio(e.target.value)} />
      )}
    </fieldset>
  );
}

function Opciones({ p, valor, onCambio }) {
  return (
    <div className="grid gap-2">
      {p.opciones.map((o) => (
        <label key={o} className={`opcion-cuestionario ${valor === o ? "elegida" : ""}`}>
          <input type="radio" name={p.id} value={o} checked={valor === o} onChange={() => onCambio(o)} />
          <span>{o}</span>
        </label>
      ))}
    </div>
  );
}

function Casillas({ p, valor, onCambio }) {
  const alternar = (o) => {
    if (valor.includes(o)) return onCambio(valor.filter((x) => x !== o));
    // la opción exclusiva («Ninguno», «No tuve ningún problema») no va con las demás
    if (o === p.exclusiva) return onCambio([o]);
    return onCambio([...valor.filter((x) => x !== p.exclusiva), o]);
  };
  return (
    <div className="grid gap-2">
      <p className="text-[12px] text-[var(--bone-faint)]">Puedes marcar varias.</p>
      {p.opciones.map((o) => (
        <label key={o} className={`opcion-cuestionario ${valor.includes(o) ? "elegida" : ""}`}>
          <input type="checkbox" checked={valor.includes(o)} onChange={() => alternar(o)} />
          <span>{o}</span>
        </label>
      ))}
    </div>
  );
}

/* Escala del 1 al 5: con las cinco etiquetas si las tiene (comparación) o solo las de los extremos */
function Escala({ p, valor, onCambio }) {
  const todas = p.etiquetas.every(Boolean);
  return (
    <div className="space-y-1.5">
      <div role="radiogroup" aria-label={`Pregunta ${p.n}`} className="grid grid-cols-5 gap-1.5 sm:max-w-xl">
        {[1, 2, 3, 4, 5].map((k) => (
          <button key={k} type="button" role="radio" aria-checked={valor === k}
            aria-label={p.etiquetas[k - 1] ? `${k}: ${p.etiquetas[k - 1]}` : String(k)}
            className={`escala-cuestionario ${valor === k ? "elegida" : ""}`} onClick={() => onCambio(valor === k ? null : k)}>
            <span className="text-[15px]">{k}</span>
            {todas && <span className="text-[10.5px] leading-tight opacity-80">{p.etiquetas[k - 1]}</span>}
          </button>
        ))}
      </div>
      {!todas && (
        <div className="flex justify-between gap-4 text-[11.5px] text-[var(--bone-faint)] sm:max-w-xl">
          <span>1 · {p.etiquetas[0]}</span><span className="text-right">5 · {p.etiquetas[4]}</span>
        </div>
      )}
    </div>
  );
}

/* El acceso a los resultados (la página aparte también está en el menú) */
function AccesoResultados() {
  return (
    <Link to="/cuestionario/resultados" className="tarjeta tarjeta-viva flex flex-wrap items-center gap-4 p-5">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="etiqueta">Anónimos</p>
        <p className="serif text-[22px] leading-tight">Resultados de la evaluación</p>
        <p className="text-[14px] text-[var(--bone-dim)]">Gráficas y exportación en CSV, LaTeX para Overleaf o PDF; anónimos.</p>
      </div>
      <span className="pill ghost sm">Ver resultados</span>
    </Link>
  );
}
