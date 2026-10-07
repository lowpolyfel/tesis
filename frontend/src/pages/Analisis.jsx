import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { especificacionDeProyecto, obtenerCola, obtenerRequisito, obtenerProyecto, requisitosDeProyecto } from "../services/backend";
import { ESTADOS as E, esTerminal, estadoSimple } from "../constants/estados";
import { TIPO_REQUISITO, nodo } from "../constants/agentes";
import { crearCoreografia } from "../escena/coreografia";
import { useEnVivo } from "../escena/useEnVivo";
import { resumenMensaje } from "../escena/resumenMensaje";
import { pasoSimple } from "../escena/pasoSimple";
import TextoMarcado from "../components/TextoMarcado";
import { EstadoChip, Volver } from "../components/ui";

/*
 * Analizar, paso 3: la escena en vivo.
 *
 * La esfera se divide en los nodos reales del sistema (Extractor, Filtros,
 * Clasificador, Divergencia, Crítico, Humano, Modelador). Cada mensaje del
 * protocolo que llega por SSE viaja de su emisor a su receptor; las
 * interpretaciones nacen del Clasificador y se acercan o alejan según la
 * similitud. Lo que se ve es exactamente lo que dice la traza.
 *
 * El backend procesa un requisito a la vez (cola); la escena sigue al que está
 * en proceso. Lo que se lee es un paso por mensaje, en lenguaje claro; la
 * bitácora técnica está plegada. Solo los requisitos en los que los agentes no
 * se pusieron de acuerdo esperan a una persona (ADR 0017).
 */

const RITMOS = [0.5, 1, 2, 4];
const enReposo = (estado) => esTerminal(estado) || estado === E.PENDIENTE_VALIDACION;

export default function Analisis() {
  const orb = useOrb();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const proyecto = params.get("proyecto");
  const ids = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);

  const [lista, setLista] = useState(null);
  const [colaFoco, setColaFoco] = useState(null);
  const [errorCarga, setErrorCarga] = useState(null);
  const [foco, setFoco] = useState(null);
  const [vistos, setVistos] = useState([]); // requisitos cuya escena ya se mostró completa
  const [repetir, setRepetir] = useState(params.get("escena") === "1");
  const [fase, setFase] = useState("division"); // division → trabajo → fusion → resultados
  const [nombreProyecto, setNombreProyecto] = useState(null);

  useEffect(() => {
    if (proyecto) obtenerProyecto(proyecto).then((x) => setNombreProyecto(x.nombre)).catch(() => {});
  }, [proyecto]);

  useEffect(() => {
    if (!ids.length || !proyecto) navigate(proyecto ? `/proyectos/${proyecto}` : "/proyectos", { replace: true });
  }, [ids, proyecto, navigate]);

  /* ---- estado del lote: sondeo ligero de la lista y de la cola ---- */
  useEffect(() => {
    if (!proyecto) return undefined;
    let activo = true;
    let t;
    const tick = async () => {
      try {
        const [todos, cola] = await Promise.all([requisitosDeProyecto(proyecto), obtenerCola()]);
        if (!activo) return;
        const porId = new Map(todos.map((r) => [r.req_id, r]));
        const nueva = ids.map((id) => porId.get(id)).filter(Boolean);
        setLista(nueva);
        setColaFoco(cola.en_proceso && ids.includes(cola.en_proceso.clave) ? cola.en_proceso.clave : null);
        setErrorCarga(null);
        if (nueva.some((r) => !enReposo(r.estado))) t = setTimeout(tick, 1500);
        else t = setTimeout(tick, 5000); // ya nada corre; se sigue mirando por si valida alguien
      } catch (e) {
        if (!activo) return;
        setErrorCarga(e);
        t = setTimeout(tick, 3000);
      }
    };
    tick();
    return () => { activo = false; clearTimeout(t); };
  }, [proyecto, ids]);

  const coreografia = useMemo(() => crearCoreografia(orb), [orb]);
  const vivo = useEnVivo(fase === "trabajo" ? foco : null, { coreografia });
  const alDia = vivo.animados >= vivo.mensajes.length;

  /*
   * A quién seguir: cada requisito del lote se muestra completo y en orden
   * (la cola también procesa en orden). El siguiente entra cuando el actual
   * llegó a reposo y su escena terminó; si aún no empieza (cargado), se espera.
   */
  const siguiente = lista?.find((r) => !vistos.includes(r.req_id) && r.req_id !== foco) ?? null;
  const listoParaVer = siguiente && (siguiente.estado !== E.CARGADO || siguiente.req_id === colaFoco);
  useEffect(() => {
    if (fase !== "trabajo") return undefined;
    if (!foco) {
      if (listoParaVer) setFoco(siguiente.req_id);
      return undefined;
    }
    if (enReposo(vivo.estado) && alDia && listoParaVer) {
      const t = setTimeout(() => { setVistos((v) => [...v, foco]); setFoco(siguiente.req_id); }, 1400);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [fase, foco, siguiente, listoParaVer, vivo.estado, alDia]);

  const todosEnReposo = Boolean(lista?.length) && lista.length === ids.length && lista.every((r) => enReposo(r.estado));
  const todosVistos = Boolean(lista) && lista.every((r) => vistos.includes(r.req_id) || r.req_id === foco);

  /* ---- 1. mitosis inicial (si todo ya estaba listo, directo a resultados salvo que se pida la escena) ---- */
  useEffect(() => {
    if (!lista || fase !== "division") return undefined;
    if (todosEnReposo && !repetir) {
      orb.setPose(isMobile() ? { x: 0, y: -0.33, s: 0.45 } : { x: -0.3, y: 0, s: 0.8 });
      setFase("resultados");
      return undefined;
    }
    orb.setPose({ x: 0, y: -0.06, s: 0.9 });
    orb.setMood("idle");
    orb.update("core", { label: "Sistema", sub: `${ids.length} ${ids.length === 1 ? "requisito" : "requisitos"}` });
    const t = setTimeout(() => { coreografia.montar(); setFase("trabajo"); }, 700);
    return () => clearTimeout(t);
  }, [lista, fase, todosEnReposo, repetir, orb, coreografia, ids.length]);

  /* ---- 2. todo en reposo y visto: los nodos se funden ---- */
  useEffect(() => {
    if (fase !== "trabajo" || !todosEnReposo || !todosVistos || !alDia || !enReposo(vivo.estado ?? E.CARGADO)) return undefined;
    const t = setTimeout(() => {
      coreografia.desmontar();
      orb.setPose({ x: 0, y: -0.06, s: 0.95 });
      orb.setMood("success");
      setFase("fusion");
    }, 1600);
    return () => clearTimeout(t);
  }, [fase, todosEnReposo, todosVistos, alDia, vivo.estado, coreografia, orb]);

  useEffect(() => {
    if (fase !== "fusion") return undefined;
    const t = setTimeout(() => {
      orb.setPose(isMobile() ? { x: 0, y: -0.33, s: 0.45 } : { x: -0.3, y: 0, s: 0.8 });
      orb.update("core", { label: "Análisis completo", sub: null });
      orb.setMood("idle");
      setFase("resultados");
    }, 1500);
    return () => clearTimeout(t);
  }, [fase, orb]);

  useEffect(() => {
    const alCambiar = () => coreografia.reacomodar();
    addEventListener("resize", alCambiar);
    return () => removeEventListener("resize", alCambiar);
  }, [coreografia]);

  /* Al salir, la esfera vuelve a ser una */
  useEffect(() => () => {
    coreografia.desmontar();
    orb.update("core", { label: null, sub: null });
    orb.setMood("idle");
  }, [orb, coreografia]);

  if (errorCarga && !lista) {
    return (
      <main className="relative z-10 mx-auto max-w-xl px-6 pt-[30vh] text-center">
        <p className="serif text-3xl">No pude seguir el análisis.</p>
        <p className="mt-3 text-sm text-[var(--bone-dim)]">{errorCarga.message}</p>
        <Link to={proyecto ? `/proyectos/${proyecto}` : "/proyectos"} className="pill ghost mt-6">Volver</Link>
      </main>
    );
  }
  if (!lista) return null;

  const focoInfo = lista.find((r) => r.req_id === foco);
  const pendientes = lista.filter((r) => r.estado === E.PENDIENTE_VALIDACION);

  return (
    <main className="relative z-10 min-h-screen">
      <div className="fixed top-20 left-5 z-20 md:top-24 md:left-10">
        <Volver a={`/proyectos/${proyecto}`}>{nombreProyecto ?? "Proyecto"}</Volver>
      </div>
      {fase === "trabajo" && focoInfo && (
        <Foco r={focoInfo} i={lista.indexOf(focoInfo)} total={lista.length} mensajes={vivo.mensajes} animados={vivo.animados} estadoVivo={vivo.estado} />
      )}
      {fase === "trabajo" && (
        <Panel
          vivo={vivo} lista={lista} foco={foco} pendientes={pendientes} proyecto={proyecto}
          onSeguir={(id) => setFoco(id)}
        />
      )}
      {fase === "fusion" && (
        <p className="mono aparece fixed inset-x-0 bottom-[18vh] text-center text-[10px] text-[var(--bone-dim)]">Reuniendo a los agentes…</p>
      )}
      {fase === "resultados" && (
        <Resultados lista={lista} proyecto={proyecto}
          onRepetir={() => { setRepetir(true); setVistos([]); setFoco(null); setFase("division"); }} />
      )}
    </main>
  );
}

/* ---------------------------------------------------------------- */

/* Decisiones de los filtros que no pasan por el Clasificador: su marca ya es final */
const SIN_CLASIFICADOR = ["resuelto_por_lel", "vaguedad"];

/*
 * El requisito en foco. Marcas y estado salen de la vista del backend
 * (GET /requisitos/{id}), no se recalculan aquí, y van al paso de la
 * animación: el estado es el de la última transición anterior al último
 * mensaje animado, y las marcas del Clasificador aparecen cuando se anima.
 */
function Foco({ r, i, total, mensajes, animados, estadoVivo }) {
  const [vista, setVista] = useState(null);
  useEffect(() => {
    let activo = true;
    const t = setTimeout(() => obtenerRequisito(r.req_id).then((v) => { if (activo) setVista(v); }).catch(() => {}),
      mensajes.length ? 400 : 0);
    return () => { activo = false; clearTimeout(t); };
  }, [r.req_id, mensajes.length]);
  const v = vista?.req_id === r.req_id ? vista : null;

  const animadas = mensajes.slice(0, animados);
  const ultima = animadas.at(-1)?.secuencia ?? 0;
  const estado = v?.transiciones.filter((t) => t.secuencia <= ultima).at(-1)?.estado ?? estadoVivo;
  const vio = (tipo) => animadas.some((m) => m.tipo === tipo);
  const marcas = !v || !vio("filtrado") ? []
    : v.marcados.filter((m) => m.tipo && (vio("interpretaciones") || SIN_CLASIFICADOR.includes(m.decision_filtro)));
  const largo = r.texto.length > 110;
  return (
    <section key={r.req_id} className="pointer-events-none fixed inset-x-0 top-[max(9vh,92px)] z-10 px-6 text-center">
      <p className="mono aparece text-[10px] text-[var(--bone-faint)]">
        Requisito {i + 1} de {total}{estado && <> · <span className="text-[var(--bone-dim)]">{estadoSimple(estado).texto}</span></>}
      </p>
      <p className={`serif aparece mx-auto mt-2 line-clamp-2 max-w-4xl leading-tight ${largo ? "text-[clamp(16px,1.5vw,21px)]" : "text-[clamp(19px,2vw,28px)]"}`}>
        «<TextoMarcado texto={r.texto} marcados={marcas} />»
      </p>
    </section>
  );
}

/*
 * Abajo: el paso actual en una frase, el avance del lote y lo que espera
 * revisión. La bitácora técnica (emisor → receptor, tipo, payload) va plegada.
 */
function Panel({ vivo, lista, foco, pendientes, proyecto, onSeguir }) {
  const [bitacora, setBitacora] = useState(false);
  const lineas = useRef(null);
  const visibles = vivo.mensajes.slice(0, Math.max(vivo.animados, 0));
  const actual = vivo.mensajes[vivo.animados - 1];
  const listos = lista.filter((r) => enReposo(r.estado)).length;
  const siguienteRitmo = RITMOS[(RITMOS.indexOf(vivo.ritmo) + 1) % RITMOS.length];

  useEffect(() => {
    lineas.current?.scrollTo({ top: lineas.current.scrollHeight, behavior: "smooth" });
  }, [visibles.length, bitacora]);

  return (
    <div className="fixed inset-x-0 bottom-0 z-10 px-4 pb-4 md:px-8">
      <div className="tarjeta mx-auto max-w-4xl">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
          {actual ? (
            <p className="min-w-0 flex-1 text-[15px]">
              <span className="mono mr-2 text-[10px]" style={{ color: nodo(actual.emisor).tono }}>{nodo(actual.emisor).nombre}</span>
              {pasoSimple(actual)}
            </p>
          ) : <p className="min-w-0 flex-1 text-[15px] text-[var(--bone-dim)]">{vivo.error ? vivo.error.message : "Esperando el primer paso…"}</p>}
          <span className="mono flex items-center gap-3 text-[10px] text-[var(--bone-faint)]">
            <button onClick={() => vivo.setRitmo(siguienteRitmo)} className="hover:text-[var(--bone)]" title="Velocidad de la animación">{vivo.ritmo}×</button>
            {vivo.animados < vivo.mensajes.length && <button onClick={vivo.acelerar} className="hover:text-[var(--bone)]">saltar</button>}
            <button onClick={() => setBitacora((x) => !x)} className="hover:text-[var(--bone)]">{bitacora ? "ocultar bitácora" : "bitácora"}</button>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-[var(--line)] px-5 py-2.5">
          <span className="mono text-[10px] text-[var(--bone-faint)]">{listos} de {lista.length} listos</span>
          <span className="flex flex-wrap gap-1.5">
            {lista.map((r) => {
              const e = estadoSimple(r.estado);
              return (
                <button key={r.req_id} onClick={() => onSeguir(r.req_id)} title={`${r.req_id} · ${e.texto}\n${r.texto}`}
                  className={`h-3 w-3 rounded-full transition-transform hover:scale-125 ${r.req_id === foco ? "ring-2 ring-[var(--bone)] ring-offset-2 ring-offset-[var(--bg)]" : ""}`}
                  style={{ background: e.tono, opacity: e.id === "cola" ? 0.4 : 1 }} />
              );
            })}
          </span>
          {pendientes.length > 0 && (
            <Link className="pill sm ml-auto" to={`/requisitos/${pendientes[0].req_id}/validacion?volver=${encodeURIComponent(`/analisis?proyecto=${proyecto}&ids=${lista.map((x) => x.req_id).join(",")}`)}`}>
              Revisar {pendientes.length > 1 ? `(${pendientes.length})` : pendientes[0].req_id}
            </Link>
          )}
        </div>

        {bitacora && (
          <ol ref={lineas} className="max-h-[22vh] overflow-y-auto border-t border-[var(--line)] px-5 py-2 font-mono text-[11.5px] leading-relaxed">
            {visibles.map((m, i) => (
              <li key={m.secuencia} className={`flex gap-3 py-0.5 ${i === visibles.length - 1 ? "text-[var(--bone)]" : "text-[var(--bone-dim)]"}`}>
                <span className="w-7 shrink-0 text-right text-[var(--bone-faint)]">{m.secuencia}</span>
                <span className="w-44 shrink-0 truncate">
                  <span style={{ color: nodo(m.emisor).tono }}>{m.emisor}</span>
                  <span className="text-[var(--bone-faint)]"> → </span>
                  <span style={{ color: nodo(m.receptor).tono }}>{m.receptor}</span>
                </span>
                <span className="w-32 shrink-0 text-[var(--bone-faint)]">{m.tipo}{m.ronda ? ` r${m.ronda}` : ""}</span>
                <span className="min-w-0 flex-1 break-words font-sans">{resumenMensaje(m)}</span>
              </li>
            ))}
            {!visibles.length && <li className="py-1 text-[var(--bone-faint)]">Sin mensajes todavía.</li>}
          </ol>
        )}
      </div>
    </div>
  );
}

/* Al terminar: qué quedó listo, qué espera revisión y la versión reescrita de cada uno */
function Resultados({ lista, proyecto, onRepetir }) {
  const [espec, setEspec] = useState(null);
  const ids = lista.map((r) => r.req_id);
  const clave = ids.join(",");
  useEffect(() => {
    especificacionDeProyecto(proyecto, clave.split(",")).then(setEspec).catch(() => setEspec(null));
  }, [proyecto, clave]);
  const porReq = new Map(
    espec ? [...espec.funcionales, ...espec.no_funcionales, ...espec.sin_clasificar].map((x) => [x.req_id, x]) : []);
  const cuenta = (id) => lista.filter((r) => estadoSimple(r.estado).id === id).length;
  const pendientes = lista.filter((r) => r.estado === E.PENDIENTE_VALIDACION);
  const listos = lista.filter((r) => r.estado === E.FORMALIZADO).map((r) => r.req_id);

  return (
    <section className="aparece mx-auto flex min-h-screen max-w-2xl flex-col gap-5 px-6 pt-[36vh] pb-14 md:mr-[7vw] md:pt-32">
      <h1 className="serif text-[clamp(40px,4.4vw,68px)] leading-[.95]">
        <em>{lista.length}</em> {lista.length === 1 ? "requisito analizado" : "requisitos analizados"}.
      </h1>
      <p className="mono flex flex-wrap gap-x-5 gap-y-1 text-[10.5px] text-[var(--bone-faint)]">
        <span><b className="font-normal text-[#57f7a7]">{cuenta("listo")}</b> listos</span>
        {cuenta("revisar") > 0 && <span><b className="font-normal text-[#f9a8d4]">{cuenta("revisar")}</b> por revisar</span>}
        {cuenta("descartado") > 0 && <span>{cuenta("descartado")} descartados</span>}
        {cuenta("error") > 0 && <span className="text-[var(--danger)]">{cuenta("error")} con error</span>}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {pendientes[0] && <Link className="pill" to={`/requisitos/${pendientes[0].req_id}/validacion`}>Revisar {pendientes.length > 1 ? `(${pendientes.length})` : ""}</Link>}
        {listos.length > 0 && <Link className={pendientes.length ? "pill ghost" : "pill"} to={`/proyectos/${proyecto}?vista=especificacion&req=${listos.join(",")}`}>Ver especificación</Link>}
        {listos.length > 0 && <Link className="pill ghost" to={`/proyectos/${proyecto}?vista=mapa&req=${listos.join(",")}`}>Crear mapa</Link>}
        <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={onRepetir}>ver la escena otra vez</button>
      </div>

      <ol className="space-y-3 pt-2">
        {lista.map((r) => {
          const x = porReq.get(r.req_id);
          const destino = r.estado === E.PENDIENTE_VALIDACION ? `/requisitos/${r.req_id}/validacion` : `/requisitos/${r.req_id}`;
          return (
            <li key={r.req_id}>
              <Link to={destino} className="tarjeta tarjeta-viva block p-4">
                <span className="flex flex-wrap items-center gap-3">
                  <span className="mono text-[10px] text-[var(--bone-faint)]">{r.req_id}</span>
                  {x?.tipo_requisito && <span className="etiqueta" style={{ color: TIPO_REQUISITO[x.tipo_requisito].tono }}>{TIPO_REQUISITO[x.tipo_requisito].etiqueta}</span>}
                  <EstadoChip estado={r.estado} className="ml-auto" />
                </span>
                <span className="mt-2 block text-[15.5px] leading-relaxed">{x?.reescrito ?? r.texto}</span>
                {x && x.reescrito !== r.texto && <span className="mt-1 block text-[13px] italic text-[var(--bone-faint)]">antes: «{r.texto}»</span>}
              </Link>
            </li>
          );
        })}
      </ol>
      <Link to={`/proyectos/${proyecto}`} className="mono self-start text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Volver al proyecto</Link>
    </section>
  );
}
