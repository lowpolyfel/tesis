import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useApi } from "../hooks/useApi";
import { crearProyecto, listarProyectos, resumenProyecto } from "../services/backend";

/*
 * Todos los proyectos: cada uno agrupa los requisitos de un dominio, sus
 * ciclos KMoS-SSA y su propio LEL (la memoria no se mezcla entre dominios).
 * Los proyectos que crea una evaluación contra el corpus van aparte.
 */
export default function Proyectos() {
  const navigate = useNavigate();
  const { datos: proyectos, error, cargando } = useApi(listarProyectos);
  const [contadores, setContadores] = useState({});
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    if (!proyectos) return;
    let activo = true;
    Promise.all(proyectos.map((p) => resumenProyecto(p.proyecto_id).then((r) => [p.proyecto_id, r.contadores]).catch(() => [p.proyecto_id, null])))
      .then((pares) => { if (activo) setContadores(Object.fromEntries(pares)); });
    return () => { activo = false; };
  }, [proyectos]);

  const crear = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    try {
      const p = await crearProyecto({ nombre, descripcion });
      navigate(`/proyectos/${p.proyecto_id}`);
    } catch (err) {
      setAviso(err.message);
    }
  };

  if (error) return <p className="text-sm text-rose-600">{error.message}</p>;
  if (cargando || !proyectos) return <p className="text-sm text-slate-500">Cargando proyectos…</p>;

  const normales = proyectos.filter((p) => p.tipo !== "evaluacion");
  const evaluaciones = proyectos.filter((p) => p.tipo === "evaluacion");

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end gap-4">
        <div>
          <p className="mono mb-3 text-[10px] text-[var(--bone-faint)]">{normales.length} proyectos</p>
          <h1>Proyectos.</h1>
        </div>
        <button className="pill ghost ml-auto" onClick={() => setAbierto((x) => !x)}>{abierto ? "Cancelar" : "+ Nuevo proyecto"}</button>
      </header>

      {abierto && (
        <form onSubmit={crear} className="sube grid gap-4 rounded-2xl border border-[var(--line)] p-5 sm:grid-cols-[1fr_1.4fr_auto] sm:items-end">
          <label className="block">
            <span className="mono mb-1 block text-[9.5px] text-[var(--bone-faint)]">Nombre</span>
            <input autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)} className="linea w-full py-1.5 text-[15px]" />
          </label>
          <label className="block">
            <span className="mono mb-1 block text-[9.5px] text-[var(--bone-faint)]">Dominio o descripción</span>
            <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className="linea w-full py-1.5 text-[15px]" />
          </label>
          <button className="pill" disabled={!nombre.trim()}>Crear</button>
          {aviso && <p className="text-sm text-rose-600 sm:col-span-3">{aviso}</p>}
        </form>
      )}

      <ol className="grid gap-4 md:grid-cols-2">
        {normales.map((p, i) => <Tarjeta key={p.proyecto_id} p={p} c={contadores[p.proyecto_id]} i={i} />)}
      </ol>

      {evaluaciones.length > 0 && (
        <section className="space-y-3">
          <h2>Proyectos de evaluación</h2>
          <p className="text-sm text-slate-500">Los crea una corrida contra el corpus (Evaluación); tienen su propio LEL y no se mezclan con los demás.</p>
          <ol className="grid gap-4 md:grid-cols-2">
            {evaluaciones.map((p, i) => <Tarjeta key={p.proyecto_id} p={p} c={contadores[p.proyecto_id]} i={i} />)}
          </ol>
        </section>
      )}
    </div>
  );
}

function Tarjeta({ p, c, i }) {
  const cifras = c ? [
    ["requisitos", c.requisitos], ["ciclos", c.ciclos], ["en proceso", c.en_proceso],
    ["por validar", c.por_validar], ["formalizados", c.formalizados], ["ambiguos", c.ambiguos],
    ["en el LEL", c.lel], ["rechazados", c.rechazados], ["con error", c.errores],
  ] : [];
  return (
    <li className="sube" style={{ "--i": i }}>
      <Link to={`/proyectos/${p.proyecto_id}`} className="group block h-full rounded-2xl border border-[var(--line)] bg-white/[0.02] p-5 transition-colors hover:border-[var(--c1)] hover:bg-white/[0.04]">
        <p className="mono text-[9.5px] text-[var(--bone-faint)]">{p.proyecto_id}{p.tipo === "evaluacion" ? " · evaluación" : ""}</p>
        <p className="serif mt-1 text-[30px] leading-tight">{p.nombre}</p>
        {p.descripcion && <p className="mt-1 text-sm text-[var(--bone-dim)]">{p.descripcion}</p>}
        {c ? (
          <dl className="mono mt-5 grid grid-cols-3 gap-3 text-[9.5px] text-[var(--bone-faint)]">
            {cifras.map(([k, v]) => (
              <div key={k}>
                <dd className={`font-sans text-[22px] tracking-normal normal-case ${v ? "text-[var(--bone)]" : "text-[var(--bone-faint)]"}`}>{v}</dd>
                <dt>{k}</dt>
              </div>
            ))}
          </dl>
        ) : <p className="mono mt-5 text-[9.5px] text-[var(--bone-faint)]">contando…</p>}
        <p className="mono mt-4 text-[9.5px] text-[var(--bone-faint)] opacity-0 transition-opacity group-hover:opacity-100">Abrir →</p>
      </Link>
    </li>
  );
}
