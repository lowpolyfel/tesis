import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useOrb, usePoseEsfera } from "../../components/orb/useOrb";
import { crearEntrevista, leerArchivoEntrevista, obtenerProyecto, vistaPreviaEntrevista } from "../../services/backend";
import { recordarProyecto } from "../../components/proyectoRecordado";
import { Volver } from "../../components/ui";

/*
 * La entrada de la versión 2 (ADR 0024): la entrevista con el cliente. La esfera la recibe:
 *   inicio   → la esfera al centro: «suelta la entrevista»
 *   pegar    → la esfera a un lado; aparece el texto
 *   leyendo  → la esfera lee el archivo (PDF con texto o .txt)
 *   revisar  → la esfera a la izquierda; a la derecha, el título, el texto (se puede
 *              corregir) y cómo se leyó: los turnos y quién habla
 * Al enviarla entra a la cola y la escena muestra a los agentes trabajar.
 */
const POSES = {
  inicio: { d: { x: 0, y: -0.08, s: 1.05 }, m: { x: 0, y: -0.16, s: 0.8 } },
  arrastre: { d: { x: 0, y: -0.08, s: 1.3 }, m: { x: 0, y: -0.16, s: 0.95 } },
  pegar: { d: { x: -0.26, y: 0, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  leyendo: { d: { x: 0, y: -0.04, s: 0.9 }, m: { x: 0, y: -0.1, s: 0.7 } },
  revisar: { d: { x: -0.3, y: 0.02, s: 0.78 }, m: { x: 0, y: -0.36, s: 0.4 } },
};
POSES.enviando = POSES.leyendo;
const ESPERA_VISTA_MS = 500;

export default function NuevaEntrevista() {
  const orb = useOrb();
  const navigate = useNavigate();
  const { id: proyectoId } = useParams();
  const [proyecto, setProyecto] = useState(null);
  const [fase, setFase] = useState("inicio");
  const [arrastrando, setArrastrando] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [texto, setTexto] = useState("");
  const [origen, setOrigen] = useState(null);
  const [vista, setVista] = useState(null);
  const [error, setError] = useState(null);
  const archivo = useRef(null);

  usePoseEsfera(POSES[arrastrando ? "arrastre" : fase], [fase, arrastrando]);
  useEffect(() => {
    recordarProyecto(proyectoId);
    obtenerProyecto(proyectoId).then(setProyecto).catch((e) => setError(e.message));
  }, [proyectoId]);

  const trabajando = fase === "leyendo" || fase === "enviando";
  useEffect(() => {
    orb.setMood(trabajando ? "revisor" : arrastrando || fase === "pegar" ? "entrevista" : "idle");
    orb.update("core", {
      label: fase === "leyendo" ? "Leyendo" : fase === "enviando" ? "A los agentes" : fase === "revisar" && vista ? `${vista.turnos.length} turnos` : null,
      sub: fase === "leyendo" ? origen?.archivo ?? "" : fase === "revisar" && vista?.hablantes?.length ? `${vista.hablantes.length} hablantes` : null,
      desde: trabajando ? Date.now() : null,
    });
  }, [orb, fase, trabajando, arrastrando, vista, origen]);
  useEffect(() => () => orb.update("core", { label: null, sub: null, desde: null }), [orb]);

  /* arrastrar y soltar sobre toda la pantalla: la esfera «atrae» el archivo */
  const leerVigente = useRef(null);
  useEffect(() => {
    if (fase !== "inicio" && fase !== "pegar") return undefined;
    let profundidad = 0;
    const entra = (e) => { if (e.dataTransfer?.types?.includes("Files")) { profundidad++; setArrastrando(true); } };
    const sale = () => { profundidad = Math.max(0, profundidad - 1); if (!profundidad) setArrastrando(false); };
    const sobre = (e) => e.preventDefault();
    const suelta = (e) => {
      e.preventDefault();
      profundidad = 0;
      setArrastrando(false);
      const f = e.dataTransfer.files?.[0];
      if (f) leerVigente.current?.(f);
    };
    addEventListener("dragenter", entra);
    addEventListener("dragleave", sale);
    addEventListener("dragover", sobre);
    addEventListener("drop", suelta);
    return () => {
      removeEventListener("dragenter", entra);
      removeEventListener("dragleave", sale);
      removeEventListener("dragover", sobre);
      removeEventListener("drop", suelta);
    };
  }, [fase]);

  const leerArchivo = async (f) => {
    setError(null);
    setOrigen({ tipo: f.name.toLowerCase().endsWith(".pdf") ? "pdf" : "txt", archivo: f.name });
    setFase("leyendo");
    try {
      const [r] = await Promise.all([leerArchivoEntrevista(proyectoId, f), new Promise((ok) => setTimeout(ok, 900))]);
      setTitulo(r.titulo);
      setTexto(r.texto);
      setOrigen(r.origen);
      setVista(r.vista);
      orb.poke(1.2);
      setFase("revisar");
    } catch (e) {
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("inicio");
    }
  };
  leerVigente.current = leerArchivo;

  /* la vista previa sigue al texto mientras se corrige */
  useEffect(() => {
    if (fase !== "revisar" || !texto.trim()) return undefined;
    let vivo = true;
    const t = setTimeout(() => {
      vistaPreviaEntrevista(proyectoId, texto).then((v) => { if (vivo) { setVista(v); setError(null); } })
        .catch((e) => vivo && setError(e.message));
    }, ESPERA_VISTA_MS);
    return () => { vivo = false; clearTimeout(t); };
  }, [fase, texto, proyectoId]);

  const enviar = async () => {
    setError(null);
    setFase("enviando");
    try {
      const e = await crearEntrevista(proyectoId, { titulo: titulo.trim() || "Entrevista", texto, origen: origen ?? { tipo: "texto" } });
      orb.setMood("success");
      orb.poke(1.4);
      setTimeout(() => navigate(`/proyectos/${proyectoId}/entrevistas/${e.entrevista_id}`), 500);
    } catch (e) {
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("revisar");
    }
  };

  return (
    <main className="relative z-10 min-h-screen">
      <input ref={archivo} type="file" accept=".txt,.pdf" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) leerArchivo(f); }} />
      {!trabajando && (
        <div className="fixed top-20 left-5 z-20 md:top-24 md:left-10">
          <Volver a={`/proyectos/${proyectoId}?fase=entrevista`}>{proyecto?.nombre ?? "Proyecto"}</Volver>
        </div>
      )}

      {fase === "inicio" && (
        <section className="aparece fixed inset-x-0 bottom-[7vh] flex flex-col items-center gap-6 px-6 text-center">
          <h1 className="serif text-[clamp(44px,5.6vw,84px)] leading-[.95]">¿Qué te <em>contaron</em>?</h1>
          <p className="max-w-md text-[15px] leading-relaxed text-[var(--bone-dim)]">
            {arrastrando ? "Suéltala sobre la esfera." : "Suelta la entrevista sobre la esfera (PDF o .txt), o pega su transcripción."}
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <button className="pill" onClick={() => archivo.current.click()} onPointerEnter={() => orb.poke(0.25)}>Sube la entrevista</button>
            <button className="pill ghost" onClick={() => setFase("pegar")} onPointerEnter={() => orb.poke(0.25)}>Pegar texto</button>
          </div>
          <p className="max-w-lg text-[12.5px] text-[var(--bone-faint)]">
            Mejor si viene por hablante («Entrevistador: …», «Dra. Ruiz: …»). Si no, cada párrafo cuenta como una intervención.
          </p>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        </section>
      )}

      {fase === "pegar" && (
        <section className="aparece mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6 pt-[40vh] pb-12 md:mr-[8vw] md:pt-24">
          <h1 className="serif text-[clamp(40px,4vw,64px)] leading-[.95]">Pega la <em>entrevista</em>.</h1>
          <input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={160} placeholder="Título (por ejemplo: Entrevista con la Dra. Ruiz)"
            className="linea w-full py-2 text-[15px]" />
          <textarea autoFocus value={texto} onChange={(e) => setTexto(e.target.value)} onInput={() => orb.poke(0.04)} rows={12}
            placeholder={"Entrevistador: ¿Qué le gustaría que hiciera el sistema?\nDra. Ruiz: Quiero registrar las consultas de mis pacientes…"}
            className="linea w-full resize-none rounded-none border-b bg-transparent py-3 text-[15px] leading-relaxed" />
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button className="pill" disabled={!texto.trim()} onClick={() => { setOrigen({ tipo: "texto" }); setVista(null); setFase("revisar"); }}>Ver cómo se lee</button>
            <button className="pill ghost" onClick={() => setFase("inicio")}>Volver</button>
          </div>
        </section>
      )}

      {trabajando && (
        <p className="mono aparece fixed inset-x-0 bottom-[16vh] text-center text-[10.5px] text-[var(--bone-dim)]">
          {fase === "leyendo" ? "Leyendo el archivo y separando quién dijo qué…" : "Entregando la entrevista a los agentes…"}
        </p>
      )}

      {fase === "revisar" && (
        <Revisar titulo={titulo} setTitulo={setTitulo} texto={texto} setTexto={setTexto} vista={vista} origen={origen}
          error={error} onEnviar={enviar} onVolver={() => { setError(null); setFase(origen?.tipo === "texto" ? "pegar" : "inicio"); }} />
      )}
    </main>
  );
}

function Revisar({ titulo, setTitulo, texto, setTexto, vista, origen, error, onEnviar, onVolver }) {
  const [editar, setEditar] = useState(false);
  const entrevistador = vista?.hablantes?.find((h) => h.rol_probable === "entrevistador")?.nombre;
  return (
    <section className="aparece mx-auto flex min-h-screen max-w-2xl flex-col gap-5 px-6 pt-[34vh] pb-16 md:mr-[5vw] md:pt-28">
      <div className="space-y-1">
        <p className="etiqueta">{origen?.archivo ? `${origen.archivo}${origen.paginas ? ` · ${origen.paginas} páginas` : ""}` : "Texto pegado"}</p>
        <input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={160} placeholder="Título de la entrevista"
          className="linea serif w-full py-1 text-[34px] leading-tight" aria-label="Título de la entrevista" />
      </div>
      {vista ? (
        <p className="text-[14.5px] text-[var(--bone-dim)]">
          {vista.modo === "hablantes"
            ? <>Leí <b className="font-normal text-[var(--bone)]">{vista.turnos.length} intervenciones</b> de {vista.hablantes.map((h) => h.nombre).join(", ")}{entrevistador ? <> (quien pregunta parece ser <b className="font-normal text-[var(--bone)]">{entrevistador}</b>)</> : null}.</>
            : <>No reconocí hablantes: leí <b className="font-normal text-[var(--bone)]">{vista.turnos.length} párrafos</b>, cada uno como una intervención.</>}
          {" "}{vista.caracteres.toLocaleString("es-MX")} caracteres.
        </p>
      ) : <p className="mono flex items-center gap-2 text-[10.5px] text-[var(--bone-dim)]"><span className="gira" /> Leyendo…</p>}
      {vista?.advertencias?.length > 0 && <p className="text-[12.5px] text-[var(--bone-faint)]">{vista.advertencias.join(" ")}</p>}

      {editar ? (
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={16}
          className="campo text-[14px] leading-relaxed" aria-label="Texto de la entrevista" />
      ) : vista && (
        <ol className="tarjeta max-h-[46vh] space-y-2 overflow-y-auto p-4">
          {vista.turnos.slice(0, 200).map((t) => (
            <li key={t.n} className="grid grid-cols-[2.6rem_1fr] gap-2 text-[13.5px] leading-relaxed">
              <span className="mono pt-0.5 text-[9.5px] text-[var(--bone-faint)]">T{t.n}</span>
              <span>{t.hablante && <b className="font-medium">{t.hablante}: </b>}<span className="text-[var(--bone-dim)]">{t.texto}</span></span>
            </li>
          ))}
          {vista.turnos.length > 200 && <li className="text-[12px] text-[var(--bone-faint)]">… y {vista.turnos.length - 200} más</li>}
        </ol>
      )}
      {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button className="pill" disabled={!texto.trim() || !vista} onClick={onEnviar}>Que la analicen los agentes</button>
        <button className="pill ghost" onClick={() => setEditar((x) => !x)}>{editar ? "Ver los turnos" : "Corregir el texto"}</button>
        <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={onVolver}>volver</button>
      </div>
    </section>
  );
}
