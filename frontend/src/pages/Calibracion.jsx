import { useEffect, useState } from "react";
import { obtenerConfiguracion, guardarConfiguracion } from "../services/api";
import { AGENTES, ORDEN_AGENTES } from "../constants/agentes";

/*
 * Pantalla 8: umbral de similitud, máximo de rondas y modelo de cada agente.
 * Se aplica en caliente a lo que se procese después; no reinicia nada.
 */
export default function Calibracion() {
  const [datos, setDatos] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [nota, setNota] = useState("");
  const [aviso, setAviso] = useState(null);

  const cargar = () => obtenerConfiguracion().then((d) => { setDatos(d); setCfg(d.config); });
  useEffect(() => { cargar(); }, []);

  if (!cfg) return <p className="text-sm text-slate-500">Cargando configuración…</p>;

  const vigente = datos.config;
  const sucio = JSON.stringify(cfg) !== JSON.stringify(vigente);
  const set = (k, v) => { setCfg((c) => ({ ...c, [k]: v })); setAviso(null); };
  const setModelo = (agente, v) => { setCfg((c) => ({ ...c, modelos: { ...c.modelos, [agente]: v } })); setAviso(null); };

  const guardar = async () => {
    await guardarConfiguracion(cfg, nota);
    setNota("");
    setAviso("Guardado. Los requisitos que se carguen o reprocesen a partir de ahora usan estos valores.");
    cargar();
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">Calibración</h1>
        <p className="text-sm text-slate-500">
          Los cambios se aplican en caliente: no hay que reiniciar nada. Los requisitos ya procesados conservan la configuración con la que corrieron (se ve en su detalle).
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide">Divergencia y debate</h2>
          <label className="block text-sm">
            <span className="flex justify-between">
              <span>Umbral de similitud</span>
              <span className="font-mono">{cfg.umbral.toFixed(2)} {cfg.umbral !== vigente.umbral && <span className="text-slate-400">(vigente {vigente.umbral.toFixed(2)})</span>}</span>
            </span>
            <input type="range" min="0.5" max="0.95" step="0.01" value={cfg.umbral} onChange={(e) => set("umbral", +e.target.value)} className="w-full" />
            <span className="text-xs text-slate-500">Si la similitud entre interpretaciones es menor que este valor, se activa el debate.</span>
          </label>
          <label className="block text-sm">
            <span>Máximo de rondas de debate</span>
            <input type="number" min="1" max="6" value={cfg.maxRondas} onChange={(e) => set("maxRondas", Math.max(1, Math.min(6, +e.target.value || 1)))} className="ml-3 w-20 rounded border border-slate-300 px-2 py-1 font-mono" />
            <span className="block text-xs text-slate-500">Al agotarse sin consenso, arbitra el Crítico.</span>
          </label>
          <label className="block text-sm">
            <span>Modelo de embeddings</span>
            <select value={cfg.modeloEmbeddings} onChange={(e) => set("modeloEmbeddings", e.target.value)} className="ml-3 rounded border border-slate-300 px-2 py-1">
              {datos.disponibles.embeddings.map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
        </div>

        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide">Modelo por agente</h2>
          {ORDEN_AGENTES.map((a) => {
            const opciones = AGENTES[a].proveedor === "api" ? datos.disponibles.api : datos.disponibles.ollama;
            return (
              <label key={a} className="grid grid-cols-[7rem_1fr] items-center gap-2 text-sm">
                <span>
                  {AGENTES[a].nombre}
                  <span className="block text-xs text-slate-400">{AGENTES[a].proveedor === "api" ? "API externa" : "Ollama local"}</span>
                </span>
                <select value={cfg.modelos[a]} onChange={(e) => setModelo(a, e.target.value)} className="rounded border border-slate-300 px-2 py-1 font-mono text-xs">
                  {opciones.map((m) => <option key={m}>{m}</option>)}
                </select>
              </label>
            );
          })}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <input value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Nota del experimento (opcional)" className="w-72 rounded border border-slate-300 px-2 py-1.5 text-sm" />
        <button onClick={guardar} disabled={!sucio} className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40">Aplicar</button>
        <button onClick={() => setCfg(vigente)} disabled={!sucio} className="rounded border border-slate-300 px-4 py-1.5 text-sm disabled:opacity-40">Descartar</button>
        {aviso && <span className="text-sm text-green-700">{aviso}</span>}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold uppercase tracking-wide">Historial de calibraciones</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr><th className="px-4 py-1.5">Fecha</th><th>Umbral</th><th>Rondas</th><th>Modelos</th><th>Nota</th></tr>
          </thead>
          <tbody>
            {datos.historial.map((h, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-4 py-1.5 font-mono text-xs">{new Date(h.en).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" })}</td>
                <td className="font-mono">{h.config.umbral.toFixed(2)}</td>
                <td className="font-mono">{h.config.maxRondas}</td>
                <td className="font-mono text-xs text-slate-600">{ORDEN_AGENTES.map((a) => h.config.modelos[a]).join(" · ")}</td>
                <td className="text-slate-600">{h.nota}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
