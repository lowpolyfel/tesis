import { useState } from "react";
import { useNavigate } from "react-router";
import { crearRequisitos, extraerTextoDeArchivo, separarRequisitos } from "../services/api";
import { documentoEjemplo } from "../fixtures/documentoEjemplo";

/*
 * Pantalla 1: pegar texto o subir .txt/.pdf, revisar la separación en
 * requisitos individuales y confirmar antes de procesar.
 */
export default function CargaRequisitos() {
  const navigate = useNavigate();
  const [texto, setTexto] = useState("");
  const [origen, setOrigen] = useState("texto pegado");
  const [piezas, setPiezas] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  const subir = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setOcupado(true);
    try {
      setTexto(await extraerTextoDeArchivo(file));
      setOrigen(file.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
      e.target.value = "";
    }
  };

  const detectar = async () => {
    setOcupado(true);
    const lista = await separarRequisitos(texto);
    setPiezas(lista.map((p, i) => ({ ...p, clave: i })));
    setOcupado(false);
  };

  const editar = (i, valor) => setPiezas((ps) => ps.map((p, j) => (j === i ? { ...p, texto: valor } : p)));
  const quitar = (i) => setPiezas((ps) => ps.filter((_, j) => j !== i));
  const unir = (i) => setPiezas((ps) => [
    ...ps.slice(0, i),
    { ...ps[i], texto: `${ps[i].texto} ${ps[i + 1].texto}` },
    ...ps.slice(i + 2),
  ]);
  const agregar = () => setPiezas((ps) => [...ps, { texto: "", clave: Date.now() }]);

  const confirmar = async () => {
    const validas = piezas.filter((p) => p.texto.trim());
    setOcupado(true);
    const { ids } = await crearRequisitos(validas.map((p) => ({ texto: p.texto, origen })));
    navigate(`/cola?nuevos=${ids.join(",")}`);
  };

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Cargar requisitos</h1>
        <p className="text-sm text-slate-500">Pega el texto o sube un archivo. Antes de procesar, confirma cómo se separaron los requisitos.</p>
      </header>

      {!piezas ? (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label className="cursor-pointer rounded border border-slate-300 px-3 py-1.5 hover:bg-slate-50">
              Subir .txt o .pdf
              <input type="file" accept=".txt,.pdf" onChange={subir} className="hidden" />
            </label>
            <button onClick={() => { setTexto(documentoEjemplo); setOrigen("ejemplo.txt"); }} className="text-slate-600 underline">
              Usar texto de ejemplo
            </button>
            <span className="text-slate-400">Origen: {origen}</span>
          </div>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            rows={12}
            placeholder="1. El sistema debe…"
            className="w-full rounded border border-slate-300 p-3 font-mono text-sm"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            onClick={detectar}
            disabled={!texto.trim() || ocupado}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {ocupado ? "Procesando…" : "Detectar requisitos"}
          </button>
        </section>
      ) : (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm">
            Se detectaron <strong>{piezas.length}</strong> requisitos. Edita, une o elimina antes de confirmar.
          </p>
          <ol className="space-y-2">
            {piezas.map((p, i) => (
              <li key={p.clave} className="flex gap-2">
                <span className="w-6 pt-2 text-right font-mono text-xs text-slate-400">{i + 1}</span>
                <textarea
                  value={p.texto}
                  onChange={(e) => editar(i, e.target.value)}
                  rows={2}
                  className="min-w-0 flex-1 rounded border border-slate-300 p-2 text-sm"
                />
                <div className="flex flex-col gap-1 text-xs">
                  <button onClick={() => unir(i)} disabled={i === piezas.length - 1} className="rounded border border-slate-300 px-2 py-1 disabled:opacity-30">
                    Unir con el siguiente
                  </button>
                  <button onClick={() => quitar(i)} className="rounded border border-red-200 px-2 py-1 text-red-700">Eliminar</button>
                </div>
              </li>
            ))}
          </ol>
          <button onClick={agregar} className="text-sm text-slate-600 underline">+ Agregar requisito</button>
          <div className="flex gap-2 border-t border-slate-100 pt-3">
            <button
              onClick={confirmar}
              disabled={ocupado || !piezas.some((p) => p.texto.trim())}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              Confirmar y procesar {piezas.filter((p) => p.texto.trim()).length} requisitos
            </button>
            <button onClick={() => setPiezas(null)} className="rounded border border-slate-300 px-4 py-2 text-sm">
              Volver al texto
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
