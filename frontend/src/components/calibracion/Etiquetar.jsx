import { useEffect, useMemo, useState } from "react";
import { etiquetasEntrevista, guardarEtiquetas } from "../../services/backend";
import { TIPOS } from "../../constants/agentes";
import { Aviso, Cargando } from "../ui";

/*
 * El ground truth de una entrevista (ADR 0026): la persona anotadora marca qué términos son
 * ambiguos y de qué tipo. Por omisión se etiqueta A CIEGAS: no se ve la similitud ni la
 * decisión del sistema, para que el ground truth no se incline hacia él. «Ver al sistema»
 * las muestra, y desde ese momento lo que se guarde queda marcado como visto (no a ciegas).
 * Los términos son los que encontró el Extractor; se pueden agregar los que se le pasaron.
 * Solo se guardan los términos con una decisión (ambiguo o no).
 */
const TIPOS_AMBIGUEDAD = ["lexica", "regional", "alcance", "anaforica", "sintactica"];
const CLAVE_ANOTADOR = "dudamel.anotador";
const clave = (t) => t.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase().trim();
const leerAnotador = () => { try { return localStorage.getItem(CLAVE_ANOTADOR) ?? ""; } catch { return ""; } };

export default function Etiquetar({ entrevistaId, onGuardado, onCerrar }) {
  const [verSistema, setVerSistema] = useState(false);
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [filas, setFilas] = useState(null); // [{termino, decision_filtro, ambiguo: true|false|null, tipo, nota}]
  const [anotador, setAnotador] = useState(leerAnotador);
  const [visto, setVisto] = useState(false); // vio al sistema en esta sesión de etiquetado
  const [nuevo, setNuevo] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [guardado, setGuardado] = useState(null);

  useEffect(() => {
    let vivo = true;
    etiquetasEntrevista(entrevistaId, verSistema).then((d) => {
      if (!vivo) return;
      setDatos(d);
      setFilas((previas) => {
        if (previas) return previas; // ya se está etiquetando: solo llegan los datos del sistema
        const hechas = Object.fromEntries((d.etiquetado?.etiquetas ?? []).map((e) => [clave(e.termino), e]));
        const base = d.terminos.map((t) => ({ termino: t.termino, decision_filtro: t.decision_filtro, ambiguo: null, tipo: null, nota: null, ...hechas[clave(t.termino)] }));
        const extra = Object.values(hechas).filter((e) => !d.terminos.some((t) => clave(t.termino) === clave(e.termino)))
          .map((e) => ({ ...e, decision_filtro: "agregado" }));
        return [...base, ...extra];
      });
      if (d.etiquetado && !anotador) setAnotador(d.etiquetado.anotador);
      if (d.etiquetado && d.etiquetado.a_ciegas === false) setVisto(true);
    }).catch((e) => vivo && setError(e));
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entrevistaId, verSistema]);

  const sistema = useMemo(() => Object.fromEntries((datos?.terminos ?? []).map((t) => [clave(t.termino), t])), [datos]);

  if (error) return <Aviso error={error} />;
  if (!filas) return <Cargando>Cargando los términos…</Cargando>;

  const cambiar = (i, cambios) => { setFilas((fs) => fs.map((f, k) => (k === i ? { ...f, ...cambios } : f))); setGuardado(null); };
  const decididas = filas.filter((f) => f.ambiguo != null);
  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      try { localStorage.setItem(CLAVE_ANOTADOR, anotador.trim()); } catch { /* sin almacenamiento */ }
      const doc = await guardarEtiquetas(entrevistaId, {
        anotador: anotador.trim(), a_ciegas: !visto,
        etiquetas: decididas.map((f) => ({ termino: f.termino, ambiguo: f.ambiguo, tipo: f.ambiguo ? f.tipo || null : null, nota: f.nota || null })),
      });
      setGuardado(doc);
      onGuardado?.(doc);
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="space-y-4 border-t border-[var(--line)] pt-4">
      <div className="flex flex-wrap items-end gap-4">
        <label className="block">
          <span className="etiqueta mb-1 block">Anotador</span>
          <input value={anotador} onChange={(e) => setAnotador(e.target.value)} maxLength={120} placeholder="Tu nombre"
            className="campo w-56 text-[14px]" />
        </label>
        <label className="mono flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={verSistema} onChange={(e) => { setVerSistema(e.target.checked); if (e.target.checked) setVisto(true); }} />
          ver al sistema (similitud y decisión)
        </label>
        <span className={`mono text-[10px] ${visto ? "text-[#ffc457]" : "text-[var(--bone-faint)]"}`}>
          {visto ? "se guardará como etiquetado viendo al sistema" : "a ciegas"}
        </span>
      </div>

      <table className="tabla-viz">
        <thead>
          <tr><th>Término</th><th>Filtro</th><th>¿Ambiguo?</th><th>Tipo</th>{verSistema && <><th>Similitud</th><th>Sistema</th></>}</tr>
        </thead>
        <tbody>
          {filas.map((f, i) => {
            const s = sistema[clave(f.termino)];
            return (
              <tr key={`${f.termino}-${i}`}>
                <td className="text-[var(--bone)]">{f.termino}</td>
                <td className="mono text-[10px] text-[var(--bone-faint)]">{f.decision_filtro ?? "—"}</td>
                <td>
                  <span className="inline-flex gap-1">
                    {[[true, "sí"], [false, "no"]].map(([v, txt]) => (
                      <button key={txt} type="button" onClick={() => cambiar(i, { ambiguo: f.ambiguo === v ? null : v })}
                        className={`pill sm ${f.ambiguo === v ? "" : "ghost"}`} aria-pressed={f.ambiguo === v}>{txt}</button>
                    ))}
                  </span>
                </td>
                <td>
                  {f.ambiguo && (
                    <select value={f.tipo ?? ""} onChange={(e) => cambiar(i, { tipo: e.target.value || null })}
                      className="rounded-full border border-[var(--line)] bg-transparent px-2 py-1 text-[12px] text-[var(--bone)]">
                      <option value="" className="bg-[var(--bg)]">sin tipo</option>
                      {TIPOS_AMBIGUEDAD.map((t) => <option key={t} value={t} className="bg-[var(--bg)]">{TIPOS[t]?.etiqueta ?? t}</option>)}
                    </select>
                  )}
                </td>
                {verSistema && (
                  <>
                    <td>{s?.similitud != null ? s.similitud.toFixed(3) : "—"}</td>
                    <td className="text-[12px] text-[var(--bone-dim)]">{s?.decision ? (s.decision === "en_debate" ? "debate" : "directo") : "unívoco o filtrado"}</td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      <form className="flex flex-wrap gap-2" onSubmit={(e) => {
        e.preventDefault();
        const t = nuevo.trim();
        if (!t || filas.some((f) => clave(f.termino) === clave(t))) return;
        setFilas((fs) => [...fs, { termino: t, decision_filtro: "agregado", ambiguo: true, tipo: null, nota: null }]);
        setNuevo("");
      }}>
        <input value={nuevo} onChange={(e) => setNuevo(e.target.value)} maxLength={120} placeholder="Término que el sistema no encontró"
          className="campo w-72 text-[13px]" />
        <button className="pill ghost sm">Agregar</button>
      </form>

      <Aviso error={error} />
      <div className="flex flex-wrap items-center gap-3">
        <button className="pill sm" onClick={guardar} disabled={guardando || !anotador.trim() || !decididas.length}>
          {guardando ? "Guardando…" : `Guardar ${decididas.length} etiqueta${decididas.length === 1 ? "" : "s"}`}
        </button>
        <button className="pill ghost sm" onClick={onCerrar}>Cerrar</button>
        {guardado && <span className="mono text-[10px] text-[var(--ok)]">guardado · {guardado.actualizada}</span>}
        {!anotador.trim() && <span className="text-[12px] text-[var(--bone-faint)]">Escribe quién etiqueta para poder guardar.</span>}
      </div>
    </div>
  );
}
