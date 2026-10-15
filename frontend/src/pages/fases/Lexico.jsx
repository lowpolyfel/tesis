import { memo, useCallback, useDeferredValue, useMemo, useRef, useState } from "react";
import { useApi } from "../../hooks/useApi";
import { invalidarCache } from "../../hooks/useCache";
import {
  agregarTermino, corregirTermino, descartarTermino, lexicoDeProyecto, olvidarAcuerdo, restaurarTermino,
  validarSinAmbiguedad, validarTermino,
} from "../../services/backend";
import { ESTADO_TERMINO, VIA_TERMINO } from "../../constants/fases";
import { TIPOS_LEL } from "../../constants/agentes";
import { seccion } from "../../components/orb/secciones";
import { useOrb } from "../../components/orb/useOrb";
import { volarALaEsfera } from "../../components/fases/vuelo";
import Cita from "../../components/fases/Cita";
import { Aviso, Cargando, Chip, Confirmar, Plegable, Vacio } from "../../components/ui";

/*
 * Fase 2 (ADR 0024): el LEL interactivo. Los agentes propusieron cada término del dominio
 * con su intención (qué quiere lograr quien lo usa); la persona experta valida cada uno:
 *
 *   ✓ Validar     lo confirma tal cual
 *   ✎ Corregir    cambia lo que haga falta, o parte de otra intención de las que vieron
 *                 los agentes («Era esta»)
 *   ✕ Descartar   no es un término del dominio
 *
 * Lo que corrige, confirma entre varias intenciones o descarta, el sistema lo aprende: es
 * un acuerdo del proyecto que usan las entrevistas siguientes y las demás fases («consulta»
 * es la cita médica, no una búsqueda en la base de datos). La esfera lo recibe.
 * Con todo validado, el léxico es el sistema cognitivo del dominio y se abre el mapa.
 */
const sinAcentos = (s) => s.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();
const FILTROS = [
  ["pendientes", "Por validar"],
  ["ambiguos", "Con más de una intención"],
  ["listos", "Validados"],
  ["descartados", "Descartados"],
  ["todos", "Todos"],
];
const pasa = {
  pendientes: (e) => e.estado === "propuesto",
  ambiguos: (e) => e.ambiguedad && e.estado !== "descartado",
  listos: (e) => e.estado === "validado" || e.estado === "corregido",
  descartados: (e) => e.estado === "descartado",
  todos: () => true,
};
const lineas = (t) => t.split("\n").map((x) => x.trim()).filter(Boolean);

/* El mismo resumen que arma el backend (`resumen` en app/fases/lexico.py): al cambiar un término
   se cuenta aquí, sin volver a pedir todo el léxico */
function resumenDe(entradas) {
  const cuenta = Object.fromEntries(["propuesto", "validado", "corregido", "descartado"].map((k) => [k, entradas.filter((x) => x.estado === k).length]));
  return {
    ...cuenta, total: entradas.length, vigentes: entradas.length - cuenta.descartado,
    ambiguos: entradas.filter((x) => x.ambiguedad && x.estado !== "descartado").length,
    completo: entradas.length > 0 && cuenta.propuesto === 0 && entradas.length > cuenta.descartado,
  };
}

export default function Lexico({ proyectoId, estado, onCambio, onSeguir }) {
  const orb = useOrb();
  const { datos, setDatos, error, recargar } = useApi(() => lexicoDeProyecto(proyectoId), [proyectoId]);
  const [filtro, setFiltro] = useState(null);
  const [q, setQ] = useState("");
  const [agregando, setAgregando] = useState(false);
  const [enBloque, setEnBloque] = useState(false);
  const moodSeccion = seccion("lexico").mood;
  // el buscador responde al teclear; la lista se filtra después, sin trabar la escritura
  const qDiferida = useDeferredValue(q);
  const entradas = datos?.entradas;
  // el texto en el que se busca, sin acentos, una vez por entrada
  const buscable = useMemo(() => new Map((entradas ?? []).map((e) => [e, sinAcentos(`${e.simbolo} ${e.terminos?.join(" ")} ${e.intencion}`)])), [entradas]);
  const cuentas = useMemo(() => Object.fromEntries(FILTROS.map(([id]) => [id, (entradas ?? []).filter(pasa[id]).length])), [entradas]);
  const activo = filtro ?? (datos?.resumen.propuesto ? "pendientes" : "todos");
  const visibles = useMemo(() => {
    const f = sinAcentos(qDiferida.trim());
    return (entradas ?? []).filter((e) => pasa[activo](e) && (!f || buscable.get(e).includes(f)));
  }, [entradas, buscable, activo, qDiferida]);

  /* una entrada cambió: se reemplaza en el sitio y el resumen se cuenta aquí (las demás tarjetas no
     se vuelven a pintar). Solo si tocó lo que aprendió el sistema (validar una ambigua, corregir,
     descartar, restaurar) se vuelve a pedir el léxico, por los acuerdos. Se avisa al camino. */
  const alCambiar = useCallback((nueva, previa) => {
    setDatos((d) => {
      const nuevas = d.entradas.map((x) => (x.entrada_id === nueva.entrada_id ? nueva : x));
      return { ...d, entradas: nuevas, resumen: resumenDe(nuevas) };
    });
    if (nueva.aprendida || previa?.aprendida) recargar();
    invalidarCache(`${proyectoId}:lexico`);
    onCambio?.();
  }, [setDatos, recargar, onCambio, proyectoId]);
  /* cambió más de una entrada (en bloque, agregar, olvidar un acuerdo): se vuelve a pedir todo */
  const alCambiarTodo = () => { recargar(); invalidarCache(`${proyectoId}:lexico`); onCambio?.(); };

  if (error) return <Aviso error={error} />;
  if (!datos) return <Cargando>Cargando el léxico…</Cargando>;
  const { resumen, acuerdos, procesando } = datos;
  const fase = estado?.fases.find((f) => f.id === "lexico");
  if (!entradas.length) {
    return (
      <Vacio>
        {procesando ? "Los agentes están leyendo la entrevista: el léxico aparece aquí cuando terminen."
          : fase?.disponible ? "La entrevista no dejó términos del dominio. Agrega los que hagan falta."
            : "El léxico sale de la entrevista: primero súbela y deja que los agentes la procesen."}
      </Vacio>
    );
  }

  const sinAmbiguedad = entradas.filter((e) => e.estado === "propuesto" && !e.ambiguedad).length;
  const hechos = resumen.validado + resumen.corregido;

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <p className="text-[15px] text-[var(--bone-dim)]">
            <b className="font-normal text-[var(--bone)]">{hechos}</b> de {resumen.vigentes} términos validados
            {resumen.descartado > 0 && <> · {resumen.descartado} descartado{resumen.descartado === 1 ? "" : "s"}</>}
            {acuerdos.length > 0 && <> · el sistema aprendió <b className="font-normal text-[#f9a8d4]">{acuerdos.length}</b> acuerdo{acuerdos.length === 1 ? "" : "s"}</>}
          </p>
          {procesando > 0 && <p className="mono flex items-center gap-1.5 text-[10px] text-[var(--bone-faint)]"><span className="gira" /> llegan más términos de una entrevista</p>}
        </div>
        <div className="barra-avance" aria-hidden="true"><span style={{ width: `${resumen.vigentes ? (100 * hechos) / resumen.vigentes : 0}%` }} /></div>
      </section>

      {resumen.completo && !procesando && (
        <div className="tarjeta flex flex-wrap items-center gap-4 !border-[#57f7a7]/40 px-5 py-4">
          <span className="punto" style={{ background: "#57f7a7", boxShadow: "0 0 12px #57f7a7" }} />
          <p className="min-w-0 flex-1 text-[14.5px]">
            El léxico está validado: el sistema ya entiende el dominio como tú. Con él se arma el mapa conceptual.
          </p>
          <button className="pill sm" onClick={onSeguir}>Seguir al mapa</button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="Qué términos ver" className="pestanas">
          {FILTROS.map(([id, texto]) => (
            <button key={id} role="tab" aria-selected={activo === id} className="pestana" onClick={() => setFiltro(id)}>
              {texto}<span className="ml-1.5 opacity-60">{cuentas[id]}</span>
            </button>
          ))}
        </div>
        {entradas.length > 8 && (
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" aria-label="Buscar en el léxico"
            className="campo ml-auto w-48 py-2 text-[14px]" />
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {sinAmbiguedad > 0 && !enBloque && (
          <button className="pill ghost sm" onClick={() => setEnBloque(true)}>Validar los {sinAmbiguedad} sin ambigüedad</button>
        )}
        <button className="pill ghost sm" onClick={() => setAgregando(true)}>+ Agregar término</button>
      </div>
      {enBloque && (
        <Confirmar
          pregunta={`¿Validar de una vez ${sinAmbiguedad} término${sinAmbiguedad === 1 ? "" : "s"}?`}
          detalle="Son los que los agentes vieron con una sola intención posible. Los que tenían más de una los revisas uno por uno."
          accion="Validar" enviando="Validando…"
          onCancelar={() => setEnBloque(false)}
          onConfirmar={async () => {
            await validarSinAmbiguedad(proyectoId);
            orb.setMood("success"); orb.poke(1);
            setTimeout(() => orb.setMood(moodSeccion), 1200);
            setEnBloque(false); alCambiarTodo();
          }}
        />
      )}
      {agregando && <EditorTermino titulo="Agregar un término" onCancelar={() => setAgregando(false)}
        onGuardar={async (valores) => {
          const e = await agregarTermino(proyectoId, valores);
          setAgregando(false);
          setDatos((d) => ({ ...d, entradas: [e, ...d.entradas] }));
          alCambiarTodo();
        }} />}

      <ol className="space-y-4">
        {visibles.map((e) => <Termino key={e.entrada_id} e={e} moodSeccion={moodSeccion} onCambio={alCambiar} />)}
      </ol>
      {!visibles.length && <p className="text-[14px] text-[var(--bone-faint)]">{qDiferida ? `Nada coincide con «${qDiferida}».` : "No hay términos aquí."}</p>}

      <Memoria acuerdos={acuerdos} onOlvidar={async (a) => { await olvidarAcuerdo(a.aprendizaje_id); alCambiarTodo(); }} />
    </div>
  );
}

/* ---------------------------------------------------------------- un término */

/* memo: al validar uno, o al teclear en el buscador, las demás tarjetas no se vuelven a pintar */
const Termino = memo(function Termino({ e, moodSeccion, onCambio }) {
  const orb = useOrb();
  const ref = useRef(null);
  const [modo, setModo] = useState(null); // null | {alternativa} (corregir)
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const est = ESTADO_TERMINO[e.estado];
  const amb = e.ambiguedad;
  const [todasCitas, setTodasCitas] = useState(false);

  const hacer = async (fn, vuelo) => {
    setError(null);
    setOcupado(true);
    try {
      const nueva = await fn();
      volarALaEsfera(orb, ref.current, { moodSeccion, ...vuelo });
      onCambio(nueva, e);
    } catch (x) {
      setError(x);
    } finally {
      setOcupado(false);
    }
  };
  const validar = () => hacer(() => validarTermino(e.entrada_id),
    amb ? { mood: "aprende", etiqueta: "✓", aprendio: `«${e.simbolo}»` } : { mood: "success", etiqueta: "✓" });
  const descartar = () => hacer(() => descartarTermino(e.entrada_id), { mood: "sistema", aprendio: `«${e.simbolo}» no va` });
  const restaurar = () => hacer(() => restaurarTermino(e.entrada_id), { mood: "extractor" });

  if (modo) {
    const alt = modo.alternativa ? amb?.alternativas.find((a) => a.id === modo.alternativa) : null;
    return (
      <li ref={ref}>
        <EditorTermino
          titulo={alt ? `«${e.simbolo}»: parte de la intención ${alt.id}` : `Corregir «${e.simbolo}»`}
          inicial={alt ? { ...e, intencion: alt.intencion, nocion: [alt.significado] } : e}
          onCancelar={() => setModo(null)}
          onGuardar={async (valores) => {
            const cambios = Object.fromEntries(Object.entries(valores).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(e[k])));
            const nueva = await corregirTermino(e.entrada_id, cambios, modo.alternativa ?? null);
            setModo(null);
            volarALaEsfera(orb, ref.current, { mood: "aprende", etiqueta: "✎", moodSeccion, aprendio: `«${nueva.simbolo}»` });
            onCambio(nueva, e);
          }}
        />
      </li>
    );
  }

  return (
    <li ref={ref} className={`tarjeta termino space-y-4 p-5 ${e.estado === "descartado" ? "opacity-60" : ""}`}
      style={{ "--tono": est.tono }} onPointerEnter={() => orb.poke(0.15)}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <span className="serif text-[28px] leading-tight">{e.simbolo}</span>
        <span className="etiqueta">{e.tipo}</span>
        <span className="ml-auto flex flex-wrap gap-1.5">
          {e.marcas?.regional && <Chip tono="#ff9f6b" titulo="Expresión del español de trabajo en México">regional</Chip>}
          {e.marcas?.vago && <Chip tono="#c4b5fd">vago</Chip>}
          {e.aprendida && <Chip tono="#f9a8d4" titulo="El sistema lo guardó como acuerdo del proyecto">aprendido</Chip>}
          <Chip tono={est.tono}>{est.texto}</Chip>
        </span>
      </div>

      <div>
        <p className="etiqueta">Intención</p>
        <p className="mt-1 text-[17px] leading-snug">{e.intencion}</p>
      </div>
      <div className="grid gap-4 text-[14px] leading-relaxed sm:grid-cols-2">
        <div>
          <p className="etiqueta" title="Noción (LEL)">Qué es</p>
          <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.nocion.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
        {e.impacto?.length > 0 && (
          <div>
            <p className="etiqueta" title="Impacto (LEL)">Qué implica</p>
            <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.impacto.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        )}
      </div>
      {e.sinonimos?.length > 0 && <p className="text-[13px] text-[var(--bone-faint)]">También se dice: {e.sinonimos.join(", ")}</p>}

      {amb && (
        <div className="space-y-3 rounded-2xl border border-[var(--line)] p-4">
          <p className="text-[13.5px] text-[var(--bone-dim)]">
            <b className="font-normal text-[#ffc457]">Podía entenderse de {amb.alternativas.length} formas.</b>{" "}
            {VIA_TERMINO[amb.via] ?? ""}{amb.rondas ? ` (${amb.rondas} ronda${amb.rondas === 1 ? "" : "s"})` : ""}
            {amb.similitud != null && <span className="mono ml-2 text-[9.5px] text-[var(--bone-faint)]">similitud {Number(amb.similitud).toFixed(2)}</span>}
          </p>
          <ul className="space-y-2">
            {amb.alternativas.map((a) => {
              const propuesta = a.id === (amb.elegida_por_persona ?? amb.elegida);
              return (
                <li key={a.id} className={`flex flex-wrap items-start gap-3 rounded-xl px-3 py-2 ${propuesta ? "bg-[color-mix(in_oklab,var(--bone)_6%,transparent)]" : ""}`}>
                  <span className="mono pt-0.5 text-[10px] text-[var(--bone-faint)]">{a.id}</span>
                  <span className="min-w-0 flex-1 text-[14px]">
                    <b className="font-medium">{a.significado}</b>
                    <span className="block text-[13px] text-[var(--bone-dim)]">{a.intencion}</span>
                    {a.retirada && <span className="block text-[12px] text-[var(--bone-faint)]">El Clasificador la retiró: {a.retirada}</span>}
                  </span>
                  {propuesta ? <span className="mono pt-0.5 text-[9.5px] text-[#57f7a7]">{amb.elegida_por_persona ? "la elegiste" : "la propuesta"}</span>
                    : e.estado !== "descartado" && <button className="pill ghost sm" onClick={() => setModo({ alternativa: a.id })}>Era esta</button>}
                </li>
              );
            })}
          </ul>
          {amb.justificacion?.length > 0 && (
            <Plegable titulo="Por qué eligió el Crítico">
              <ul className="space-y-1 text-[13px] text-[var(--bone-dim)]">
                {amb.justificacion.map((j) => <li key={j.regla}><b className="mono text-[10px]">{j.regla}</b> {j.argumento}</li>)}
              </ul>
            </Plegable>
          )}
        </div>
      )}

      {e.citas?.length > 0 && (
        <div>
          <p className="etiqueta">Lo que se dijo</p>
          <ul className="mt-1.5 space-y-1.5">
            {(todasCitas ? e.citas : e.citas.slice(0, 2)).map((c, i) => <Cita key={i} cita={c} terminos={[e.simbolo, ...(e.terminos ?? []), ...(e.sinonimos ?? [])]} />)}
          </ul>
          {e.citas.length > 2 && (
            <button className="mono mt-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setTodasCitas((x) => !x)}>
              {todasCitas ? "menos citas" : `ver las ${e.citas.length} citas`}
            </button>
          )}
        </div>
      )}

      <Aviso error={error} />
      <div className="flex flex-wrap items-center gap-2">
        {e.estado === "propuesto" && <button className="pill sm" disabled={ocupado} onClick={validar}>✓ Validar</button>}
        {e.estado !== "descartado" && <button className="pill ghost sm" disabled={ocupado} onClick={() => setModo({})}>✎ Corregir</button>}
        {e.estado !== "descartado" && <button className="pill ghost sm" disabled={ocupado} onClick={descartar} title="No es un término del dominio">✕ Descartar</button>}
        {e.estado === "descartado" && <button className="pill ghost sm" disabled={ocupado} onClick={restaurar}>Restaurar</button>}
        <span className="mono ml-auto text-[9.5px] text-[var(--bone-faint)]">{e.entrada_id}{e.entrevistas?.length ? ` · ${e.entrevistas.join(" ")}` : ""}</span>
      </div>
      {e.historial?.length > 1 && (
        <Plegable titulo="Historial" nota={`${e.historial.length}`}>
          <ol className="space-y-1 text-[12.5px] text-[var(--bone-dim)]">
            {e.historial.map((h, i) => (
              <li key={i}><span className="mono text-[9.5px] text-[var(--bone-faint)]">{h.fecha?.slice(0, 16).replace("T", " ")}</span> {textoHistorial(h)}</li>
            ))}
          </ol>
        </Plegable>
      )}
    </li>
  );
});

function textoHistorial(h) {
  const quien = h.autor === "persona" ? "Tú" : h.autor === "agentes" ? "Los agentes" : "El sistema";
  const que = {
    proponer: `propusieron el término${h.entrevista ? ` (${h.entrevista})` : ""}`, validar: h.en_bloque ? "lo validaste junto con otros" : "lo validaste",
    corregir: h.alternativa ? `lo corregiste a partir de ${h.alternativa}` : "lo corregiste", descartar: "lo descartaste",
    restaurar: "lo restauraste", agregar: "lo agregaste", citas: `sumó ${h.detalle}`, recordar: "lo recordó de un acuerdo",
  }[h.accion] ?? h.accion;
  return h.autor === "persona" ? que[0].toUpperCase() + que.slice(1) : `${quien} ${que}`;
}

/* ---------------------------------------------------------------- editar o agregar */

function EditorTermino({ titulo, inicial = {}, onGuardar, onCancelar }) {
  const [simbolo, setSimbolo] = useState(inicial.simbolo ?? "");
  const [tipo, setTipo] = useState(inicial.tipo ?? "objeto");
  const [intencion, setIntencion] = useState(inicial.intencion ?? "");
  const [nocion, setNocion] = useState((inicial.nocion ?? []).join("\n"));
  const [impacto, setImpacto] = useState((inicial.impacto ?? []).join("\n"));
  const [sinonimos, setSinonimos] = useState((inicial.sinonimos ?? []).join(", "));
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const guardar = async (ev) => {
    ev.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await onGuardar({
        simbolo: simbolo.trim(), tipo, intencion: intencion.trim(), nocion: lineas(nocion), impacto: lineas(impacto),
        sinonimos: sinonimos.split(",").map((x) => x.trim()).filter(Boolean),
      });
    } catch (x) {
      setError(x);
      setEnviando(false);
    }
  };
  return (
    <form onSubmit={guardar} className="tarjeta space-y-4 p-5" style={{ borderColor: "color-mix(in oklab,#f9a8d4 45%,var(--line))" }}>
      <p className="etiqueta">{titulo}</p>
      <div className="flex flex-wrap gap-4">
        <label className="min-w-48 flex-1 space-y-1.5">
          <span className="etiqueta block">Término</span>
          <input autoFocus value={simbolo} maxLength={80} onChange={(ev) => setSimbolo(ev.target.value)} className="campo text-[15px]" required />
        </label>
        <label className="space-y-1.5">
          <span className="etiqueta block">Tipo</span>
          <select value={tipo} onChange={(ev) => setTipo(ev.target.value)} className="campo w-auto">
            {TIPOS_LEL.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      </div>
      <label className="block space-y-1.5">
        <span className="etiqueta">Intención <span className="normal-case tracking-normal">(qué quiere lograr quien lo dice)</span></span>
        <textarea value={intencion} rows={2} maxLength={400} onChange={(ev) => setIntencion(ev.target.value)} className="campo text-[14.5px]" required />
      </label>
      <label className="block space-y-1.5">
        <span className="etiqueta">Qué es <span className="normal-case tracking-normal">(una idea por renglón)</span></span>
        <textarea value={nocion} rows={2} onChange={(ev) => setNocion(ev.target.value)} className="campo text-[14px]" required />
      </label>
      <label className="block space-y-1.5">
        <span className="etiqueta">Qué implica <span className="normal-case tracking-normal">(una idea por renglón)</span></span>
        <textarea value={impacto} rows={2} onChange={(ev) => setImpacto(ev.target.value)} className="campo text-[14px]" />
      </label>
      <label className="block space-y-1.5">
        <span className="etiqueta">También se dice <span className="normal-case tracking-normal">(separado por comas)</span></span>
        <input value={sinonimos} onChange={(ev) => setSinonimos(ev.target.value)} className="campo text-[14px]" />
      </label>
      <p className="text-[12.5px] text-[var(--bone-faint)]">Lo que guardes se vuelve un acuerdo del proyecto: los agentes lo usarán desde ahora.</p>
      <Aviso error={error} />
      <div className="flex gap-2">
        <button className="pill sm" disabled={enviando || !simbolo.trim() || !intencion.trim() || !lineas(nocion).length}>{enviando ? "Guardando…" : "Guardar"}</button>
        <button type="button" className="pill ghost sm" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}

/* ---------------------------------------------------------------- lo que aprendió */

function Memoria({ acuerdos, onOlvidar }) {
  const [olvidando, setOlvidando] = useState(null);
  if (!acuerdos.length) return null;
  return (
    <section className="space-y-3 border-t border-[var(--line)] pt-6">
      <div>
        <h2>Lo que aprendió el sistema</h2>
        <p className="mt-1 text-[13.5px] text-[var(--bone-dim)]">
          Acuerdos de este proyecto: así se entienden estos términos aquí, y solo aquí. Los agentes los usan en cada fase y en las entrevistas que subas después.
        </p>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {acuerdos.map((a) => (
          <li key={a.aprendizaje_id} className="tarjeta space-y-1.5 px-4 py-3 text-[13.5px]">
            <p className="flex items-baseline gap-2">
              <b className="serif text-[19px] font-normal">{a.simbolo}</b>
              {a.descartado && <span className="etiqueta">no es del dominio</span>}
              <button className="mono ml-auto text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => setOlvidando(a)}>olvidar</button>
            </p>
            {!a.descartado && <p className="text-[var(--bone-dim)]">{a.significa}</p>}
            {a.no_significa?.length > 0 && <p className="text-[12.5px] text-[var(--bone-faint)]">No significa: {a.no_significa.join("; ")}</p>}
          </li>
        ))}
      </ul>
      {olvidando && (
        <Confirmar pregunta={`¿Olvidar el acuerdo sobre «${olvidando.simbolo}»?`}
          detalle="El término sigue en el léxico; en las entrevistas siguientes los agentes lo volverán a interpretar."
          accion="Olvidar" enviando="Olvidando…" onCancelar={() => setOlvidando(null)}
          onConfirmar={async () => { await onOlvidar(olvidando); setOlvidando(null); }} />
      )}
    </section>
  );
}
