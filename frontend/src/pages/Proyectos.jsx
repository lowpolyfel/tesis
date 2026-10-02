import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useApi } from "../hooks/useApi";
import { crearProyecto, listarProyectos } from "../services/api";

/* Todos los proyectos: cada uno agrupa sus requisitos, ciclos y artefactos */
export default function Proyectos() {
  const navigate = useNavigate();
  const { datos: proyectos, cargando } = useApi(listarProyectos);
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [abierto, setAbierto] = useState(false);

  const crear = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    const { id } = await crearProyecto({ nombre, descripcion });
    navigate(`/proyectos/${id}`);
  };

  if (cargando) return <p className="text-sm text-[var(--bone-dim)]">Cargando proyectos…</p>;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end gap-4">
        <div>
          <p className="mono mb-3 text-[10px] text-[var(--bone-faint)]">{proyectos.length} proyectos</p>
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
            <span className="mono mb-1 block text-[9.5px] text-[var(--bone-faint)]">Descripción</span>
            <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className="linea w-full py-1.5 text-[15px]" />
          </label>
          <button className="pill" disabled={!nombre.trim()}>Crear</button>
        </form>
      )}

      <ol className="grid gap-4 md:grid-cols-2">
        {proyectos.map((p, i) => (
          <li key={p.id} className="sube" style={{ "--i": i }}>
            <Link to={`/proyectos/${p.id}`} className="group block h-full rounded-2xl border border-[var(--line)] bg-white/[0.02] p-5 transition-colors hover:border-[var(--c1)] hover:bg-white/[0.04]">
              <p className="mono text-[9.5px] text-[var(--bone-faint)]">{p.id}</p>
              <p className="serif mt-1 text-[30px] leading-tight">{p.nombre}</p>
              {p.descripcion && <p className="mt-1 text-sm text-[var(--bone-dim)]">{p.descripcion}</p>}
              <dl className="mono mt-5 grid grid-cols-3 gap-3 text-[9.5px] text-[var(--bone-faint)]">
                {[
                  ["requisitos", p.requisitos],
                  ["ciclos", p.ciclos],
                  ["en el léxico", p.formalizados],
                  ["por validar", p.porValidar],
                  ["ambigüedades", p.ambiguedades],
                  ["en proceso", p.enProceso],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dd className="font-sans text-[22px] tracking-normal text-[var(--bone)] normal-case">{v}</dd>
                    <dt>{k}</dt>
                  </div>
                ))}
              </dl>
              <p className="mono mt-4 text-[9.5px] text-[var(--bone-faint)] opacity-0 transition-opacity group-hover:opacity-100">Abrir →</p>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
