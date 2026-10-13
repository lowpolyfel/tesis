import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BaseEdge, ConnectionMode, Controls, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Panel, Position, ReactFlow,
  ReactFlowProvider, getBezierPath, useEdgesState, useNodesState, useReactFlow, Background,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useTema } from "../tema";

/*
 * El mapa conceptual, editable (ADR 0024). No se edita JSON: se mueve, se une y se valida
 * sobre el propio mapa (React Flow).
 *
 *   arrastrar un concepto      lo acomoda
 *   arrastrar de un borde      une dos conceptos: nace una proposición (se escribe su enlace)
 *   tocar un concepto o enlace lo abre a la derecha: renombrar, ligar a su término del LEL,
 *                              hacerlo central, validarlo o quitarlo
 *   Supr / ⌫                   quita lo elegido (el concepto central no se quita)
 *   ⌘Z / Ctrl+Z                deshace
 *
 * `contenido` es el MapaEditable del backend; cada cambio se guarda solo (`onGuardar`, con
 * una pausa corta) y lo que la persona escribe o une cuenta como validado por ella.
 */
const ANCHO_NIVEL = 220;
const ALTO_NIVEL = 150;
const PAUSA_GUARDAR_MS = 700;
const MAX_DESHACER = 40;

const sig = (prefijo, ids) => `${prefijo}${Math.max(0, ...ids.map((x) => Number(x.slice(1)) || 0)) + 1}`;

/* Capas desde el concepto central (como un árbol): el que falte, en la última capa */
export function acomodar(contenido) {
  const vecinos = new Map(contenido.conceptos.map((c) => [c.id, new Set()]));
  for (const r of contenido.relaciones) {
    vecinos.get(r.origen)?.add(r.destino);
    vecinos.get(r.destino)?.add(r.origen);
  }
  const nivel = new Map([[contenido.central, 0]]);
  const cola = [contenido.central];
  while (cola.length) {
    const a = cola.shift();
    for (const b of vecinos.get(a) ?? []) if (!nivel.has(b)) { nivel.set(b, nivel.get(a) + 1); cola.push(b); }
  }
  const ultimo = Math.max(0, ...nivel.values()) + 1;
  const capas = new Map();
  for (const c of contenido.conceptos) {
    const n = nivel.get(c.id) ?? ultimo;
    capas.set(n, [...(capas.get(n) ?? []), c.id]);
  }
  const pos = new Map();
  for (const [n, ids] of capas) ids.forEach((id, i) => pos.set(id, { x: (i - (ids.length - 1) / 2) * ANCHO_NIVEL, y: n * ALTO_NIVEL }));
  return { ...contenido, conceptos: contenido.conceptos.map((c) => ({ ...c, ...pos.get(c.id) })) };
}

/* Los bordes que se miran: así las flechas salen del lado más cercano */
function lados(a, b) {
  const dx = (b?.x ?? 0) - (a?.x ?? 0), dy = (b?.y ?? 0) - (a?.y ?? 0);
  if (Math.abs(dx) > Math.abs(dy) * 1.2) return dx > 0 ? [Position.Right, Position.Left] : [Position.Left, Position.Right];
  return dy > 0 ? [Position.Bottom, Position.Top] : [Position.Top, Position.Bottom];
}

/* ---------------------------------------------------------------- piezas del lienzo */

function Concepto({ data, selected }) {
  return (
    <div className={`concepto-mapa ${data.central ? "central" : ""} ${data.validado ? "ok" : ""} ${selected ? "sel" : ""}`}>
      {[Position.Top, Position.Right, Position.Bottom, Position.Left].map((p) => (
        <Handle key={p} id={p} type="source" position={p} className="asa-mapa" />
      ))}
      <span className="block text-[14px] leading-tight">{data.etiqueta}</span>
      <span className="mono mt-1 block text-[8.5px] opacity-70">{data.simbolo ? `LEL · ${data.simbolo}` : "sin término del LEL"}</span>
      {data.validado && <span className="marca-ok" aria-label="validado">✓</span>}
    </div>
  );
}

function Proposicion({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd, selected }) {
  const [ruta, lx, ly] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  return (
    <>
      <BaseEdge id={id} path={ruta} markerEnd={markerEnd}
        style={{ stroke: selected ? "var(--c1)" : data.validado ? "color-mix(in oklab,#57f7a7 70%,var(--bone))" : "var(--bone-faint)", strokeWidth: selected ? 2.2 : 1.4 }} />
      <EdgeLabelRenderer>
        <button type="button" onClick={() => data.elegir(id)}
          className={`nodrag nopan enlace-mapa ${data.validado ? "ok" : ""} ${selected ? "sel" : ""}`}
          style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)` }}>
          {data.enlace}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

const TIPOS_NODO = { concepto: Concepto };
const TIPOS_ENLACE = { proposicion: Proposicion };

/* ---------------------------------------------------------------- el editor */

export default function EditorMapa(props) {
  return <ReactFlowProvider><Editor {...props} /></ReactFlowProvider>;
}

function Editor({ inicial, simbolosLel, onGuardar, completa, onCompleta }) {
  const [tema] = useTema();
  const rf = useReactFlow();
  const [contenido, setContenido] = useState(() => (inicial.conceptos.some((c) => c.x == null) ? acomodar(inicial) : inicial));
  const [eleccion, setEleccion] = useState(null); // { tipo: "concepto" | "relacion", id }
  const [guardado, setGuardado] = useState("ok"); // ok | pendiente | guardando | error
  const [errorGuardar, setErrorGuardar] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const pila = useRef([]);
  const sucio = useRef(inicial.conceptos.some((c) => c.x == null)); // recién acomodado: guardar posiciones

  /* cada cambio del mapa: a la pila de deshacer y a guardar */
  const cambiar = useCallback((fn, { deshacible = true } = {}) => {
    setContenido((c) => {
      const nuevo = fn(c);
      if (nuevo === c) return c;
      if (deshacible) pila.current = [...pila.current.slice(-MAX_DESHACER + 1), c];
      sucio.current = true;
      return nuevo;
    });
    setGuardado("pendiente");
  }, []);
  const deshacer = useCallback(() => {
    const previo = pila.current.pop();
    if (!previo) return;
    sucio.current = true;
    setContenido(previo);
    setGuardado("pendiente");
  }, []);

  /* guardado automático */
  useEffect(() => {
    if (!sucio.current) return undefined;
    const t = setTimeout(async () => {
      sucio.current = false;
      setGuardado("guardando");
      try {
        await onGuardar(contenido);
        setGuardado(sucio.current ? "pendiente" : "ok");
        setErrorGuardar(null);
      } catch (e) {
        setGuardado("error");
        setErrorGuardar(e.message);
      }
    }, PAUSA_GUARDAR_MS);
    return () => clearTimeout(t);
  }, [contenido, onGuardar]);

  useEffect(() => {
    const tecla = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z" && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) {
        e.preventDefault();
        deshacer();
      }
    };
    addEventListener("keydown", tecla);
    return () => removeEventListener("keydown", tecla);
  }, [deshacer]);

  const elegirRelacion = useCallback((id) => setEleccion({ tipo: "relacion", id }), []);

  /* del contenido al lienzo, conservando lo que React Flow ya midió y lo que tiene elegido
     (la selección la maneja React Flow; aquí solo se lee, para el panel) */
  useEffect(() => {
    const porId = new Map(contenido.conceptos.map((c) => [c.id, c]));
    setNodes((previos) => {
      const antes = new Map(previos.map((n) => [n.id, n]));
      return contenido.conceptos.map((c) => ({
        ...(antes.get(c.id) ?? {}),
        id: c.id, type: "concepto", position: { x: c.x ?? 0, y: c.y ?? 0 },
        deletable: c.id !== contenido.central,
        data: { etiqueta: c.etiqueta, simbolo: c.simbolo, validado: c.validado, central: c.id === contenido.central },
      }));
    });
    setEdges((previas) => {
      const antes = new Map(previas.map((e) => [e.id, e]));
      return contenido.relaciones.map((r) => {
        const [sh, th] = lados(porId.get(r.origen), porId.get(r.destino));
        return {
          ...(antes.get(r.id) ?? {}),
          id: r.id, source: r.origen, target: r.destino, sourceHandle: sh, targetHandle: th, type: "proposicion",
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          data: { enlace: r.enlace, validado: r.validado, elegir: elegirRelacion },
        };
      });
    });
  }, [contenido, setNodes, setEdges, elegirRelacion]);

  /* ---- acciones sobre el lienzo ---- */
  const alSoltar = useCallback((_e, _n, movidos) => {
    const pos = new Map(movidos.map((n) => [n.id, n.position]));
    cambiar((c) => ({ ...c, conceptos: c.conceptos.map((x) => (pos.has(x.id) ? { ...x, x: pos.get(x.id).x, y: pos.get(x.id).y } : x)) }));
  }, [cambiar]);

  const unir = useCallback((con) => {
    if (!con.source || !con.target || con.source === con.target) return;
    let nueva = null;
    cambiar((c) => {
      nueva = sig("R", c.relaciones.map((r) => r.id));
      return { ...c, relaciones: [...c.relaciones, { id: nueva, origen: con.source, enlace: "se relaciona con", destino: con.target, validado: false, autor: "persona" }] };
    });
    setTimeout(() => nueva && setEleccion({ tipo: "relacion", id: nueva, nueva: true }), 0);
  }, [cambiar]);

  const quitar = useCallback(({ nodes: ns = [], edges: es = [] }) => {
    const conceptos = new Set(ns.map((n) => n.id));
    const relaciones = new Set(es.map((e) => e.id));
    cambiar((c) => {
      conceptos.delete(c.central);
      if (!conceptos.size && !relaciones.size) return c;
      return {
        ...c,
        conceptos: c.conceptos.filter((x) => !conceptos.has(x.id)),
        relaciones: c.relaciones.filter((r) => !relaciones.has(r.id) && !conceptos.has(r.origen) && !conceptos.has(r.destino)),
      };
    });
    setEleccion(null);
  }, [cambiar]);

  const editarConcepto = (id, cambios) => cambiar((c) => ({ ...c, conceptos: c.conceptos.map((x) => (x.id === id ? { ...x, ...cambios } : x)) }));
  const editarRelacion = (id, cambios) => cambiar((c) => ({ ...c, relaciones: c.relaciones.map((r) => (r.id === id ? { ...r, ...cambios } : r)) }));

  const agregarConcepto = (etiqueta, simbolo) => {
    const centro = rf.screenToFlowPosition({ x: innerWidth / 2, y: innerHeight / 2 });
    let nuevo = null;
    cambiar((c) => {
      nuevo = sig("C", c.conceptos.map((x) => x.id));
      return { ...c, conceptos: [...c.conceptos, { id: nuevo, etiqueta, simbolo: simbolo || null, x: centro.x, y: centro.y, validado: true, origen: "persona" }] };
    });
    setTimeout(() => nuevo && setEleccion({ tipo: "concepto", id: nuevo }), 0);
  };

  const validarTodo = () => cambiar((c) => ({
    ...c, proposito_validado: true,
    conceptos: c.conceptos.map((x) => ({ ...x, validado: true })), relaciones: c.relaciones.map((r) => ({ ...r, validado: true })),
  }));
  const reacomodar = () => { cambiar((c) => acomodar(c)); setTimeout(() => rf.fitView({ padding: 0.2, duration: 400 }), 50); };

  const usados = new Set(contenido.conceptos.map((c) => c.simbolo).filter(Boolean));
  const pendientes = (contenido.proposito_validado ? 0 : 1) + contenido.conceptos.filter((c) => !c.validado).length
    + contenido.relaciones.filter((r) => !r.validado).length;
  const elegido = eleccion?.tipo === "concepto" ? contenido.conceptos.find((c) => c.id === eleccion.id)
    : eleccion?.tipo === "relacion" ? contenido.relaciones.find((r) => r.id === eleccion.id) : null;

  return (
    <div className={`space-y-3 ${completa ? "mapa-completo" : ""}`}>
      <Proposito contenido={contenido} onCambio={(proposito, valido) => cambiar((c) => ({ ...c, proposito, proposito_validado: valido }))} />
      <div className="lienzo-mapa">
        <ReactFlow
          nodes={nodes} edges={edges} nodeTypes={TIPOS_NODO} edgeTypes={TIPOS_ENLACE}
          onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeDragStop={alSoltar} onConnect={unir}
          onDelete={quitar} connectionMode={ConnectionMode.Loose} deleteKeyCode={["Backspace", "Delete"]}
          onSelectionChange={({ nodes: ns, edges: es }) => {
            const uno = ns.length === 1 && !es.length ? { tipo: "concepto", id: ns[0].id }
              : es.length === 1 && !ns.length ? { tipo: "relacion", id: es[0].id } : null;
            if (uno) setEleccion((x) => (x?.tipo === uno.tipo && x.id === uno.id ? x : uno));
          }}
          onPaneClick={() => setEleccion(null)}
          colorMode={tema === "claro" ? "light" : "dark"} fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.2} maxZoom={2.5}
        >
          <Background gap={22} size={1} color="var(--line)" />
          <Controls showInteractive={false} />
          {completa && <MiniMap pannable zoomable nodeColor={(n) => (n.data?.validado ? "#57f7a7" : "#34d3be")} maskColor="color-mix(in oklab,var(--bg) 70%,transparent)" />}
          <Panel position="top-left" className="flex flex-wrap gap-1.5">
            <AgregarConcepto simbolos={simbolosLel.filter((s) => !usados.has(s.simbolo))} onAgregar={agregarConcepto} />
            <button className="boton-mapa" onClick={reacomodar} title="Ordenar desde el concepto central">Acomodar</button>
            <button className="boton-mapa" onClick={deshacer} disabled={!pila.current.length} title="⌘Z / Ctrl+Z">Deshacer</button>
            <button className="boton-mapa" onClick={onCompleta}>{completa ? "Salir de pantalla completa" : "Pantalla completa"}</button>
          </Panel>
          <Panel position="bottom-center" className="mono text-[9.5px] text-[var(--bone-faint)]">
            {{ ok: "guardado", pendiente: "sin guardar…", guardando: "guardando…", error: "no se guardó" }[guardado]}
          </Panel>
          {elegido && (
            <Panel position="top-right" className="inspector-mapa">
              {eleccion.tipo === "concepto" ? (
                <InspectorConcepto c={elegido} central={elegido.id === contenido.central} simbolosLel={simbolosLel}
                  onCambio={(cambios) => editarConcepto(elegido.id, cambios)}
                  onCentral={() => cambiar((c) => ({ ...c, central: elegido.id }))}
                  onQuitar={() => quitar({ nodes: [{ id: elegido.id }] })} onCerrar={() => setEleccion(null)} />
              ) : (
                <InspectorRelacion r={elegido} enfocar={eleccion.nueva} conceptos={contenido.conceptos}
                  onCambio={(cambios) => editarRelacion(elegido.id, cambios)}
                  onQuitar={() => quitar({ edges: [{ id: elegido.id }] })} onCerrar={() => setEleccion(null)} />
              )}
            </Panel>
          )}
        </ReactFlow>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[13.5px] text-[var(--bone-dim)]">
          {pendientes ? <><b className="font-normal text-[#ffc457]">{pendientes}</b> componente{pendientes === 1 ? "" : "s"} por validar.</> : "Todo el mapa está validado."}
          {" "}Toca un concepto o un enlace para revisarlo; arrastra desde el borde de un concepto para unirlo con otro.
        </p>
        {pendientes > 0 && <button className="pill sm ml-auto" onClick={validarTodo}>Validar todo el mapa</button>}
      </div>
      {errorGuardar && <p className="text-sm text-[var(--danger)]">{errorGuardar}</p>}
    </div>
  );
}

function Proposito({ contenido, onCambio }) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(contenido.proposito);
  useEffect(() => setTexto(contenido.proposito), [contenido.proposito]);
  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="min-w-0 flex-1">
        <p className="etiqueta">Propósito · la pregunta que responde el mapa</p>
        {editando ? (
          <form className="mt-1 flex gap-2" onSubmit={(e) => { e.preventDefault(); onCambio(texto.trim() || contenido.proposito, true); setEditando(false); }}>
            <input autoFocus value={texto} maxLength={240} onChange={(e) => setTexto(e.target.value)} className="campo text-[15px]" />
            <button className="pill sm">Listo</button>
          </form>
        ) : (
          <p className="serif mt-1 text-[24px] leading-tight">{contenido.proposito}</p>
        )}
      </div>
      {!editando && (
        <span className="flex gap-1.5 pt-5">
          <button className="boton-mapa" onClick={() => setEditando(true)}>Editar</button>
          <button className={`boton-mapa ${contenido.proposito_validado ? "ok" : ""}`} onClick={() => onCambio(contenido.proposito, !contenido.proposito_validado)}>
            {contenido.proposito_validado ? "✓ Validado" : "Validar"}
          </button>
        </span>
      )}
    </div>
  );
}

function AgregarConcepto({ simbolos, onAgregar }) {
  const [abierto, setAbierto] = useState(false);
  const [libre, setLibre] = useState("");
  if (!abierto) return <button className="boton-mapa" onClick={() => setAbierto(true)}>+ Concepto</button>;
  return (
    <div className="inspector-mapa w-64 space-y-2">
      <p className="etiqueta">Agregar un concepto</p>
      {simbolos.length > 0 && (
        <select className="campo text-[13px]" defaultValue="" onChange={(e) => {
          const s = simbolos.find((x) => x.simbolo === e.target.value);
          if (s) { onAgregar(s.simbolo, s.simbolo); setAbierto(false); }
        }}>
          <option value="" disabled>Del léxico…</option>
          {simbolos.map((s) => <option key={s.simbolo} value={s.simbolo}>{s.simbolo} ({s.tipo})</option>)}
        </select>
      )}
      <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); if (libre.trim()) { onAgregar(libre.trim(), null); setLibre(""); setAbierto(false); } }}>
        <input value={libre} onChange={(e) => setLibre(e.target.value)} maxLength={60} placeholder="u otro nombre" className="campo py-1.5 text-[13px]" />
        <button className="boton-mapa" disabled={!libre.trim()}>Agregar</button>
      </form>
      <button className="mono text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setAbierto(false)}>cerrar</button>
    </div>
  );
}

function InspectorConcepto({ c, central, simbolosLel, onCambio, onCentral, onQuitar, onCerrar }) {
  const [etiqueta, setEtiqueta] = useState(c.etiqueta);
  useEffect(() => setEtiqueta(c.etiqueta), [c.id, c.etiqueta]);
  const guardar = () => { if (etiqueta.trim() && etiqueta.trim() !== c.etiqueta) onCambio({ etiqueta: etiqueta.trim(), validado: true }); };
  return (
    <div className="w-64 space-y-3">
      <p className="etiqueta flex">Concepto {c.id}{central && " · central"}<button className="ml-auto" onClick={onCerrar} aria-label="Cerrar">✕</button></p>
      <input value={etiqueta} maxLength={60} onChange={(e) => setEtiqueta(e.target.value)} onBlur={guardar}
        onKeyDown={(e) => e.key === "Enter" && guardar()} className="campo text-[15px]" aria-label="Nombre del concepto" />
      <label className="block space-y-1">
        <span className="etiqueta">Término del LEL</span>
        <select className="campo text-[13px]" value={c.simbolo ?? ""} onChange={(e) => onCambio({ simbolo: e.target.value || null, validado: true })}>
          <option value="">— ninguno —</option>
          {simbolosLel.map((s) => <option key={s.simbolo} value={s.simbolo}>{s.simbolo}</option>)}
        </select>
      </label>
      {c.simbolo && <p className="text-[12.5px] leading-snug text-[var(--bone-dim)]">{simbolosLel.find((s) => s.simbolo === c.simbolo)?.intencion}</p>}
      <div className="flex flex-wrap gap-1.5">
        <button className={`boton-mapa ${c.validado ? "ok" : ""}`} onClick={() => onCambio({ validado: !c.validado })}>{c.validado ? "✓ Validado" : "Validar"}</button>
        {!central && <button className="boton-mapa" onClick={onCentral}>Hacer central</button>}
        {!central && <button className="boton-mapa peligro" onClick={onQuitar}>Quitar</button>}
      </div>
    </div>
  );
}

function InspectorRelacion({ r, enfocar, conceptos, onCambio, onQuitar, onCerrar }) {
  const [enlace, setEnlace] = useState(r.enlace);
  const ref = useRef(null);
  useEffect(() => setEnlace(r.enlace), [r.id, r.enlace]);
  useEffect(() => { if (enfocar) ref.current?.select(); }, [enfocar, r.id]);
  const nombre = useMemo(() => Object.fromEntries(conceptos.map((c) => [c.id, c.etiqueta])), [conceptos]);
  const guardar = () => { if (enlace.trim() && enlace.trim() !== r.enlace) onCambio({ enlace: enlace.trim(), validado: true }); };
  return (
    <div className="w-64 space-y-3">
      <p className="etiqueta flex">Proposición {r.id}<button className="ml-auto" onClick={onCerrar} aria-label="Cerrar">✕</button></p>
      <p className="text-[14px] leading-snug">{nombre[r.origen]} <span className="text-[var(--bone-faint)]">—</span></p>
      <input ref={ref} value={enlace} maxLength={50} onChange={(e) => setEnlace(e.target.value)} onBlur={guardar}
        onKeyDown={(e) => e.key === "Enter" && guardar()} className="campo text-[14px]" aria-label="Enlace" />
      <p className="text-[14px] leading-snug"><span className="text-[var(--bone-faint)]">→</span> {nombre[r.destino]}</p>
      <div className="flex flex-wrap gap-1.5">
        <button className={`boton-mapa ${r.validado ? "ok" : ""}`} onClick={() => onCambio({ validado: !r.validado })}>{r.validado ? "✓ Validada" : "Validar"}</button>
        <button className="boton-mapa" onClick={() => onCambio({ origen: r.destino, destino: r.origen, validado: true })} title="Cambiar la dirección">⇄</button>
        <button className="boton-mapa peligro" onClick={onQuitar}>Quitar</button>
      </div>
    </div>
  );
}
