import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { obtenerCola, requisitosDeProyecto } from "../services/backend";
import { ESTADOS as E, estaEnProceso, esTerminal, infoEstado } from "../constants/estados";
import { nodo } from "../constants/agentes";
import { crearCoreografia } from "../escena/coreografia";
import { useEnVivo } from "../escena/useEnVivo";
import { marcasDesdeMensajes, resumenMensaje } from "../escena/resumenMensaje";
import TextoMarcado from "../components/TextoMarcado";

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
 * en proceso. Los que llegan a pendiente_validacion quedan en la bandeja
 * "por validar": la validación es de una persona, uno por uno.
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

  useEffect(() => {
    if (!ids.length || !proyecto) navigate("/inicio", { replace: true });
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
    orb.update("core", { label: "Dividiendo en agentes", sub: `${ids.length} ${ids.length === 1 ? "requisito" : "requisitos"}` });
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
        <Link to="/inicio" className="pill ghost mt-6">Volver</Link>
      </main>
    );
  }
  if (!lista) return null;

  const focoInfo = lista.find((r) => r.req_id === foco);
  const pendientes = lista.filter((r) => r.estado === E.PENDIENTE_VALIDACION);

  return (
    <main className="relative z-10 min-h-screen">
      {fase === "trabajo" && focoInfo && (
        <Foco r={focoInfo} i={lista.indexOf(focoInfo)} total={lista.length} mensajes={vivo.mensajes} estado={vivo.estado ?? focoInfo.estado} />
      )}
      {fase === "trabajo" && (
        <Panel
          vivo={vivo} lista={lista} foco={foco} pendientes={pendientes} proyecto={proyecto}
          onSeguir={(id) => setFoco(id)}
        />
      )}
      {fase === "fusion" && (
        <p className="mono sube fixed inset-x-0 bottom-[18vh] text-center text-[10px] text-[var(--bone-dim)]">Reuniendo a los agentes…</p>
      )}
      {fase === "resultados" && (
        <Resultados lista={lista} proyecto={proyecto}
          onRepetir={() => { setRepetir(true); setVistos([]); setFoco(null); setFase("division"); }} />
      )}
    </main>
  );
}

/* ---------------------------------------------------------------- */

function Foco({ r, i, total, mensajes, estado }) {
  const marcas = marcasDesdeMensajes(mensajes);
  const largo = r.texto.length > 110;
  return (
    <section key={r.req_id} className="pointer-events-none fixed inset-x-0 top-[9vh] z-10 px-6 text-center">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">
        Requisito {i + 1} de {total} · {r.req_id} · ciclo {r.ciclo ?? 1} · <span className="text-[var(--bone-dim)]">{infoEstado(estado).etiqueta}</span>
      </p>
      <p
        className={`serif sube mx-auto mt-2 line-clamp-2 max-w-4xl leading-tight ${largo ? "text-[clamp(16px,1.5vw,21px)]" : "text-[clamp(19px,2vw,28px)]"}`}
        style={{ "--i": 1 }}
      >
        «<TextoMarcado texto={r.texto} marcados={marcas} />»
      </p>
    </section>
  );
}

function Panel({ vivo, lista, foco, pendientes, proyecto, onSeguir }) {
  const [abierta, setAbierta] = useState(!isMobile());
  const lineas = useRef(null);
  const visibles = vivo.mensajes.slice(0, Math.max(vivo.animados, 0));
  const actual = vivo.mensajes[vivo.animados - 1];

  useEffect(() => {
    lineas.current?.scrollTo({ top: lineas.current.scrollHeight, behavior: "smooth" });
  }, [visibles.length]);

  return (
    <div className="fixed inset-x-0 bottom-0 z-10 px-4 pb-4 md:px-8">
      <div className="mx-auto grid max-w-6xl gap-3 md:grid-cols-[1fr_300px]">
        {/* Bitácora: un renglón por mensaje del protocolo */}
        <section className="rounded-2xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_82%,transparent)] backdrop-blur-xl">
          <header className="flex items-center gap-3 border-b border-[var(--line)] px-4 py-2">
            <button className="mono text-[9.5px] text-[var(--bone-dim)] hover:text-[var(--bone)]" onClick={() => setAbierta((x) => !x)}>
              Bitácora · {visibles.length}/{vivo.mensajes.length} {abierta ? "▾" : "▸"}
            </button>
            {actual && (
              <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--bone-dim)]">
                <b className="text-[var(--bone)]">{nodo(actual.emisor).nombre}</b> → {nodo(actual.receptor).nombre}: {resumenMensaje(actual)}
              </span>
            )}
            <span className="ml-auto flex items-center gap-1">
              {RITMOS.map((x) => (
                <button key={x} onClick={() => vivo.setRitmo(x)}
                  className={`mono rounded-full px-2 py-0.5 text-[9px] ${vivo.ritmo === x ? "bg-[var(--bone)] text-[#16130f]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}`}>
                  {x}×
                </button>
              ))}
              {!(vivo.animados >= vivo.mensajes.length) && (
                <button onClick={vivo.acelerar} className="mono ml-1 text-[9px] text-[var(--bone-faint)] hover:text-[var(--bone)]">saltar</button>
              )}
            </span>
          </header>
          {abierta && (
            <ol ref={lineas} className="max-h-[24vh] overflow-y-auto px-4 py-2 font-mono text-[11.5px] leading-relaxed">
              {visibles.map((m, i) => (
                <li key={m.secuencia} className={`flex gap-3 py-0.5 ${i === visibles.length - 1 ? "text-[var(--bone)]" : "text-[var(--bone-dim)]"}`}>
                  <span className="w-7 shrink-0 text-right text-[var(--bone-faint)]">{m.secuencia}</span>
                  <span className="w-5 shrink-0 text-[var(--bone-faint)]">{m.ronda ? `r${m.ronda}` : ""}</span>
                  <span className="w-48 shrink-0 truncate">
                    <span style={{ color: nodo(m.emisor).tono }}>{m.emisor}</span>
                    <span className="text-[var(--bone-faint)]"> → </span>
                    <span style={{ color: nodo(m.receptor).tono }}>{m.receptor}</span>
                  </span>
                  <span className="w-36 shrink-0 text-[var(--bone-faint)]">{m.tipo}</span>
                  <span className="min-w-0 flex-1 break-words font-sans">{resumenMensaje(m)}</span>
                </li>
              ))}
              {!visibles.length && <li className="py-1 text-[var(--bone-faint)]">Esperando el primer mensaje…</li>}
              {vivo.error && <li className="py-1 text-rose-300">{vivo.error.message}</li>}
            </ol>
          )}
        </section>

        {/* Lote: quién está en proceso, quién espera validación */}
        <section className="rounded-2xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_82%,transparent)] p-3 backdrop-blur-xl">
          <p className="mono text-[9.5px] text-[var(--bone-faint)]">
            Lote · {lista.filter((r) => enReposo(r.estado)).length} de {lista.length} listos
          </p>
          <ol className="mt-2 max-h-[16vh] space-y-0.5 overflow-y-auto">
            {lista.map((r) => (
              <li key={r.req_id}>
                <button onClick={() => onSeguir(r.req_id)} title={r.texto}
                  className={`flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-[12px] hover:bg-white/5 ${r.req_id === foco ? "text-[var(--bone)]" : "text-[var(--bone-dim)]"}`}>
                  <span className="mono w-9 shrink-0 text-[9px]">{r.req_id}</span>
                  <span className="min-w-0 flex-1 truncate">{r.texto}</span>
                  {estaEnProceso(r.estado) && r.estado !== E.CARGADO ? <span className="gira" /> : <span className={`punto ${infoEstado(r.estado).punto}`} />}
                </button>
              </li>
            ))}
          </ol>
          {pendientes.length > 0 && (
            <div className="mt-3 border-t border-[var(--line)] pt-2">
              <p className="mono text-[9.5px] text-pink-200">Por validar · {pendientes.length}</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {pendientes.map((r) => (
                  <Link key={r.req_id} to={`/requisitos/${r.req_id}/validacion?volver=${encodeURIComponent(`/analisis?proyecto=${proyecto}&ids=${lista.map((x) => x.req_id).join(",")}`)}`}
                    className="mono rounded-full border border-pink-300/40 px-2.5 py-1 text-[9.5px] text-pink-100 hover:bg-pink-300/10">
                    Validar {r.req_id}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Resultados({ lista, proyecto, onRepetir }) {
  const cuenta = (estado) => lista.filter((r) => r.estado === estado).length;
  const pendientes = lista.filter((r) => r.estado === E.PENDIENTE_VALIDACION);
  return (
    <section className="mx-auto flex min-h-screen max-w-2xl flex-col gap-5 px-6 pt-[36vh] pb-14 md:mr-[7vw] md:pt-28">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">Análisis del lote</p>
      <h1 className="serif sube text-[clamp(40px,4.4vw,68px)] leading-[.95]" style={{ "--i": 1 }}>
        <em>{lista.length}</em> {lista.length === 1 ? "requisito" : "requisitos"} procesados.
      </h1>
      <p className="sube text-sm text-[var(--bone-dim)]" style={{ "--i": 2 }}>
        {cuenta(E.PENDIENTE_VALIDACION)} esperan tu validación · {cuenta(E.FORMALIZADO)} formalizados · {cuenta(E.RECHAZADO)} rechazados
        {cuenta(E.ERROR) ? ` · ${cuenta(E.ERROR)} con error` : ""}.
      </p>

      <div className="sube sticky top-20 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-full px-3 py-2 backdrop-blur-xl" style={{ "--i": 3 }}>
        {pendientes[0] && <Link className="pill" to={`/requisitos/${pendientes[0].req_id}/validacion`}>Validar el siguiente</Link>}
        <Link className="pill ghost" to={`/proyectos/${proyecto}`}>Ver el proyecto</Link>
        <Link className="pill ghost" to={`/ambiguedades?proyecto=${proyecto}`}>Ambigüedades</Link>
        <Link className="pill ghost" to={`/big-picture?proyecto=${proyecto}`}>Big Picture</Link>
        <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={onRepetir}>
          Ver la escena otra vez
        </button>
      </div>

      <p className="mono text-[9.5px] text-[var(--bone-faint)]">Toca un requisito para ver cómo lo decidieron los agentes</p>
      <ol className="border-t border-[var(--line)]">
        {lista.map((r, i) => (
          <li key={r.req_id} className="sube" style={{ "--i": 4 + Math.min(i, 8) }}>
            <Link to={r.estado === E.PENDIENTE_VALIDACION ? `/requisitos/${r.req_id}/validacion` : `/requisitos/${r.req_id}`}
              className="group flex items-baseline gap-4 border-b border-[var(--line)] py-3 transition-colors hover:bg-white/[0.025]">
              <span className="mono w-12 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{r.req_id}</span>
              <span className="min-w-0 flex-1 text-[15px] leading-relaxed">{r.texto}</span>
              <span className="mono flex w-36 shrink-0 items-center justify-end gap-2 text-[9.5px] text-[var(--bone-dim)]">
                <span className={`punto ${infoEstado(r.estado).punto}`} />
                {infoEstado(r.estado).etiqueta}
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <Link to="/inicio" className="mono self-start text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Analizar otro documento</Link>
    </section>
  );
}
