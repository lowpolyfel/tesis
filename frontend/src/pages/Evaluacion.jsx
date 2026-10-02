import { useEffect, useState } from "react";
import { ejecutarCorpus, listarEjecuciones, obtenerConfiguracion, obtenerCorpus } from "../services/api";
import { seguirEjecucion } from "../services/polling";

const pct = (x) => `${Math.round(x * 100)}%`;

/* Pantalla 9: lanzar el corpus y comparar contra el ground truth */
export default function Evaluacion() {
  const [corpus, setCorpus] = useState(null);
  const [config, setConfig] = useState(null);
  const [corridas, setCorridas] = useState([]);
  const [seleccion, setSeleccion] = useState(null);
  const [enCurso, setEnCurso] = useState(null);

  const refrescar = () => listarEjecuciones().then((l) => { setCorridas(l); return l; });

  useEffect(() => {
    obtenerCorpus().then(setCorpus);
    obtenerConfiguracion().then((d) => setConfig(d.config));
    refrescar().then((l) => setSeleccion(l.find((e) => e.estado === "terminada")?.id ?? null));
  }, []);

  useEffect(() => {
    if (!enCurso) return;
    return seguirEjecucion(enCurso.id, (ej) => {
      setEnCurso(ej);
      if (ej.estado === "terminada") {
        refrescar();
        setSeleccion(ej.id);
        setEnCurso(null);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enCurso?.id]);

  const lanzar = async () => {
    const { id } = await ejecutarCorpus();
    setEnCurso({ id, procesados: 0, total: corpus.length });
  };

  if (!corpus || !config) return <p className="text-sm text-slate-500">Cargando corpus…</p>;
  const actual = corridas.find((e) => e.id === seleccion);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">Corpus y evaluación</h1>
        <p className="text-sm text-slate-500">
          {corpus.length} requisitos de prueba, {corpus.filter((c) => c.verdad.ambiguo).length} anotados como ambiguos en el ground truth.
        </p>
      </header>

      <section className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white p-4">
        <button onClick={lanzar} disabled={Boolean(enCurso)} className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          Ejecutar corpus completo
        </button>
        <span className="text-sm text-slate-600">
          Con la configuración vigente: umbral <span className="font-mono">{config.umbral.toFixed(2)}</span>, máximo <span className="font-mono">{config.maxRondas}</span> rondas.
        </span>
        {enCurso && (
          <div className="w-full">
            <div className="h-2 rounded bg-slate-100">
              <div className="h-2 rounded bg-indigo-500 transition-all" style={{ width: `${(enCurso.procesados / enCurso.total) * 100}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-500">Procesando {enCurso.procesados} de {enCurso.total}…</p>
          </div>
        )}
      </section>

      {actual?.resultados && <Resultados ej={actual} />}

      <section className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold uppercase tracking-wide">Corridas</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              <th className="px-4 py-1.5">Corrida</th><th>Fecha</th><th>Umbral</th><th>Rondas</th>
              <th className="text-right">Detectadas</th><th className="text-right">Falsas alarmas</th><th className="text-right">Debates de más</th><th className="px-4 text-right">F1</th>
            </tr>
          </thead>
          <tbody>
            {corridas.filter((e) => e.resultados).map((e) => {
              const s = e.resultados.resumen;
              return (
                <tr key={e.id} onClick={() => setSeleccion(e.id)} className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${e.id === seleccion ? "bg-indigo-50" : ""}`}>
                  <td className="px-4 py-1.5 font-mono text-xs">{e.id}</td>
                  <td className="font-mono text-xs">{new Date(e.inicio).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td className="font-mono">{e.config.umbral.toFixed(2)}</td>
                  <td className="font-mono">{e.config.maxRondas}</td>
                  <td className="text-right font-mono">{s.detectadas}/{s.ambiguedadesReales}</td>
                  <td className="text-right font-mono">{s.falsasAlarmas}</td>
                  <td className="text-right font-mono">{s.debatesDeMas}</td>
                  <td className="px-4 text-right font-mono">{s.f1.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Metrica({ titulo, valor, detalle, tono = "slate" }) {
  const tonos = { slate: "border-slate-200", rojo: "border-red-200 bg-red-50", verde: "border-green-200 bg-green-50", ambar: "border-amber-200 bg-amber-50" };
  return (
    <div className={`rounded-lg border bg-white p-3 ${tonos[tono]}`}>
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-2xl font-semibold">{valor}</p>
      {detalle && <p className="text-xs text-slate-500">{detalle}</p>}
    </div>
  );
}

function Resultados({ ej }) {
  const { resumen: s, filas } = ej.resultados;
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">
        Resultados de {ej.id} <span className="text-sm font-normal text-slate-500">(umbral {ej.config.umbral.toFixed(2)}, {ej.config.maxRondas} rondas)</span>
      </h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metrica titulo="Ambigüedades detectadas" valor={`${s.detectadas} de ${s.ambiguedadesReales}`} detalle={`recall ${pct(s.recall)} · ${s.omitidas} omitidas`} tono="verde" />
        <Metrica titulo="Falsas alarmas" valor={s.falsasAlarmas} detalle={`precisión ${pct(s.precision)}`} tono="rojo" />
        <Metrica titulo="Debates activados de más" valor={s.debatesDeMas} detalle={`${s.debatesActivados} activados; ${s.debatesNecesarios} necesarios`} tono="ambar" />
        <Metrica titulo="Debates que faltaron" valor={s.debatesFaltantes} detalle={`F1 de términos ${s.f1.toFixed(2)}`} />
      </div>
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-14 px-2 py-2">ID</th>
              <th className="px-2 py-2">Requisito</th>
              <th className="w-44 px-2 py-2">Ground truth</th>
              <th className="w-44 px-2 py-2">Detectado</th>
              <th className="w-16 px-2 py-2 text-right">Sim.</th>
              <th className="w-28 px-2 py-2">Debate</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.id} className="border-t border-slate-100 align-top">
                <td className="px-2 py-1.5 font-mono text-xs">{f.id}</td>
                <td className="px-2 py-1.5">{f.texto}</td>
                <td className="px-2 py-1.5 text-xs">{f.verdad.terminos.length ? f.verdad.terminos.join(", ") : <span className="text-slate-400">no ambiguo</span>}</td>
                <td className="px-2 py-1.5 text-xs">
                  {f.aciertos.map((t) => <span key={t} className="mr-1 inline-block rounded bg-green-100 px-1 text-green-800">✓ {t}</span>)}
                  {f.falsasAlarmas.map((t) => <span key={t} className="mr-1 inline-block rounded bg-red-100 px-1 text-red-800">✗ {t}</span>)}
                  {f.omitidos.map((t) => <span key={t} className="mr-1 inline-block rounded bg-slate-100 px-1 text-slate-500 line-through">{t}</span>)}
                </td>
                <td className="px-2 py-1.5 text-right font-mono">{f.sistema.similitud.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-xs">
                  {f.debate ? "activado" : "no"}
                  {f.debateDeMas && <span className="block font-medium text-amber-700">de más</span>}
                  {f.debateFaltante && <span className="block font-medium text-red-700">faltó</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-slate-100 px-2 py-1.5 text-xs text-slate-500">
          ✓ detectado y anotado · ✗ falsa alarma · <span className="line-through">tachado</span> anotado pero no detectado
        </p>
      </div>
    </section>
  );
}
