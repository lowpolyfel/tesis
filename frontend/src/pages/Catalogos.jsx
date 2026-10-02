import { useEffect, useState } from "react";
import { NavLink, Navigate, useParams } from "react-router";
import { obtenerCatalogo, guardarCatalogo } from "../services/api";
import TablaEditable from "../components/TablaEditable";

const TIPOS = { mexicanismos: "Mexicanismos", vaguedad: "Vaguedad" };
const COLUMNAS = [
  { clave: "expresion", titulo: "Expresión", ancho: "w-36" },
  { clave: "clasificacion", titulo: "Clasificación", ancho: "w-44" },
  { clave: "lecturas", titulo: "Lecturas posibles (una por renglón)", tipo: "lista" },
  { clave: "tratamiento", titulo: "Tratamiento" },
];

/* Pantalla 7: catálogos regionales, editables */
export default function Catalogos() {
  const { tipo } = useParams();
  const [original, setOriginal] = useState(null);
  const [filas, setFilas] = useState(null);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    if (!TIPOS[tipo]) return;
    setFilas(null);
    setAviso(null);
    obtenerCatalogo(tipo).then((f) => { setOriginal(f); setFilas(f); });
  }, [tipo]);

  if (!TIPOS[tipo]) return <Navigate to="/catalogos/mexicanismos" replace />;

  const sucio = filas && JSON.stringify(filas) !== JSON.stringify(original);
  const guardar = async () => {
    const limpias = filas
      .filter((f) => f.expresion.trim())
      .map((f) => ({ ...f, expresion: f.expresion.trim(), lecturas: f.lecturas.map((l) => l.trim()).filter(Boolean) }));
    await guardarCatalogo(tipo, limpias);
    setOriginal(limpias);
    setFilas(limpias);
    setAviso("Guardado. Se usará al procesar los próximos requisitos.");
  };

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Catálogo de términos regionales</h1>
        <p className="text-sm text-slate-500">El Extractor marca como ambiguas las expresiones de estos catálogos. Los cambios aplican a los requisitos que se procesen después.</p>
      </header>

      <div className="flex gap-1 border-b border-slate-200">
        {Object.entries(TIPOS).map(([k, v]) => (
          <NavLink
            key={k}
            to={`/catalogos/${k}`}
            className={({ isActive }) => `-mb-px border-b-2 px-3 py-1.5 text-sm ${isActive ? "border-slate-900 font-medium" : "border-transparent text-slate-500"}`}
          >
            {v}
          </NavLink>
        ))}
      </div>

      {!filas ? (
        <p className="text-sm text-slate-500">Cargando…</p>
      ) : (
        <>
          <TablaEditable
            columnas={COLUMNAS}
            filas={filas}
            onChange={(f) => { setFilas(f); setAviso(null); }}
            nuevaFila={() => ({ id: `${tipo}-${Date.now()}`, expresion: "", clasificacion: "", lecturas: [""], tratamiento: "" })}
          />
          <div className="flex items-center gap-3">
            <button onClick={guardar} disabled={!sucio} className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40">
              Guardar cambios
            </button>
            <button onClick={() => setFilas(original)} disabled={!sucio} className="rounded border border-slate-300 px-4 py-1.5 text-sm disabled:opacity-40">
              Descartar
            </button>
            <span className="text-sm text-slate-500">{aviso ?? (sucio ? "Hay cambios sin guardar." : `${filas.length} expresiones`)}</span>
          </div>
        </>
      )}
    </div>
  );
}
