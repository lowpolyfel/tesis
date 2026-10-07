import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { listarProyectos, obtenerLel } from "../services/backend";
import { TIPOS_LEL } from "../constants/agentes";
import { EntradaLel } from "./proyecto/Lexico";

const normalizar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/*
 * El LEL de cada proyecto (ADR 0008: la memoria no se mezcla entre dominios).
 * Solo entran términos léxicos resueltos y validados por una persona; los
 * unívocos no entran. Búsqueda por símbolo o término y filtro por tipo.
 * La búsqueda se escribe en un estado local y pasa a `?q=` después: atado a la
 * URL, cada tecla esperaba la navegación y se perdían caracteres.
 */
const ESPERA_URL_MS = 300;

export default function Lel() {
  const [params, setParams] = useSearchParams();
  const qUrl = params.get("q") ?? "";
  const [q, setQ] = useState(qUrl);
  const escrito = useRef(qUrl); // lo último que este campo escribió en la URL
  const tipo = params.get("tipo") ?? "";
  const proyecto = params.get("proyecto") ?? "";
  const { datos: entradas, error, cargando } = useApi(() => obtenerLel(proyecto || undefined), [proyecto]);
  const { datos: proyectos } = useApi(listarProyectos);
  // sobre los parámetros vigentes: un filtro elegido mientras corre la espera no se pierde
  // (el actualizador funcional de React Router recibe los del render en que se creó)
  const vigentes = useRef(params);
  vigentes.current = params;
  const actualizar = (cambios) => {
    const p = new URLSearchParams(vigentes.current);
    for (const [k, v] of Object.entries(cambios)) { if (v) p.set(k, v); else p.delete(k); }
    setParams(p, { replace: true });
  };
  // si la URL cambia desde fuera (el menú, atrás), el campo la sigue
  useEffect(() => {
    if (qUrl !== escrito.current) { escrito.current = qUrl; setQ(qUrl); }
  }, [qUrl]);
  useEffect(() => {
    if (q === escrito.current) return undefined;
    const t = setTimeout(() => { escrito.current = q; actualizar({ q }); }, ESPERA_URL_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  const nombreDe = (pid) => (proyectos ?? []).find((p) => p.proyecto_id === pid)?.nombre ?? pid;

  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (cargando && !entradas) return <p className="text-sm text-[var(--bone-dim)]">Cargando el LEL…</p>;

  const lista = entradas ?? [];
  const visibles = lista
    .filter((e) => !tipo || e.tipo === tipo)
    .filter((e) => !q || [e.simbolo, e.termino].some((s) => normalizar(s ?? "").includes(normalizar(q))))
    .sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));

  return (
    <div className="space-y-5">
      <header>
        <p className="mono mb-3 text-[10px] text-[var(--bone-faint)]">{lista.length} símbolos{proyecto ? ` en ${nombreDe(proyecto)}` : " en todos los proyectos"}</p>
        <h1>Léxico.</h1>
        <p className="mt-2 text-sm text-[var(--bone-dim)]">Cada entrada enlaza al requisito donde se resolvió y dice si llegó por aceptación directa, consenso o arbitraje.</p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar símbolo o término…"
          className="linea w-64 py-1.5 text-sm"
        />
        <select
          value={proyecto}
          onChange={(e) => actualizar({ proyecto: e.target.value })}
          className="rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-sm"
        >
          <option value="">Todos los proyectos</option>
          {(proyectos ?? []).map((p) => <option key={p.proyecto_id} value={p.proyecto_id}>{p.nombre}</option>)}
        </select>
        <div className="mono flex flex-wrap gap-1.5 text-[10px]">
          {["", ...TIPOS_LEL].map((t) => (
            <button
              key={t || "todos"}
              onClick={() => actualizar({ tipo: t })}
              className={`rounded-full border px-2.5 py-0.5 ${tipo === t ? "border-[var(--c1)] text-[var(--bone)]" : "border-[var(--line)] text-[var(--bone-faint)] hover:text-[var(--bone)]"}`}
            >
              {t || "todos"} ({t ? lista.filter((e) => e.tipo === t).length : lista.length})
            </button>
          ))}
        </div>
      </div>

      <ol className="grid gap-3 md:grid-cols-2">
        {visibles.map((e) => (
          <EntradaLel
            key={`${e.proyecto_id}-${e.req_id}-${e.simbolo}`}
            e={e}
            conProyecto={!proyecto && <Link to={`/proyectos/${e.proyecto_id}?vista=lel`} className="hover:text-[var(--bone)]">{nombreDe(e.proyecto_id)}</Link>}
          />
        ))}
      </ol>
      {visibles.length === 0 && (
        <p className="text-sm text-[var(--bone-dim)]">
          {lista.length ? "Ningún símbolo coincide." : "Aún no hay entradas: se crean al validar un término léxico."}
        </p>
      )}
    </div>
  );
}
