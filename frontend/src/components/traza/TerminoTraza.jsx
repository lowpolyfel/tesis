import { INFO_VIA } from "../../constants/estados";
import { REGLAS, colorInterpretacion, tipo } from "../../constants/agentes";
import MatrizPares from "./MatrizPares";
import MatrizReglas from "./MatrizReglas";
import GraficaRondas from "./GraficaRondas";

/*
 * Un término a lo largo del método: interpretaciones (Clasificador),
 * divergencia (mecanismo), debate ronda por ronda (Crítico ↔ Clasificador),
 * resolución, validación humana y entrada del LEL.
 */
const n2 = (x) => (x == null ? "—" : x.toFixed(2));
const MOTIVO = { umbral: "la similitud alcanzó el umbral", una_interpretacion: "quedó una sola interpretación", rondas_agotadas: "se agotaron las rondas" };
const CAMBIO = { ninguno: "aprobó la propuesta", eleccion: "eligió otra interpretación", edicion: "reescribió la interpretación" };

function Interp({ i, propuesta, final }) {
  const c = colorInterpretacion(i.id);
  return (
    <li className={`rounded-lg border-l-4 p-3 ${c.clase} ${i.estado === "retirada" ? "opacity-60" : ""}`}>
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <b>{i.id}</b> {i.significado}
        {propuesta === i.id && <span className="rounded bg-slate-900 px-1.5 text-[10px] text-sobre">propuesta</span>}
        {final === i.id && <span className="rounded bg-emerald-600 px-1.5 text-[10px] text-sobre">validada</span>}
        {i.estado === "retirada" && (
          <span className="rounded bg-rose-100 px-1.5 text-[10px] text-rose-800" title={i.motivo_retiro ?? ""}>retirada en la ronda {i.retirada_en_ronda}</span>
        )}
      </p>
      <p className="mt-1 text-sm text-slate-700">{i.parafrasis_del_requisito}</p>
      {i.estado === "retirada" && i.motivo_retiro && <p className="mt-1 text-xs text-slate-500">Motivo: {i.motivo_retiro}</p>}
    </li>
  );
}

function Ronda({ r, umbral }) {
  return (
    <li className="space-y-3 rounded-lg border border-slate-200 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Ronda {r.ronda}</p>
      <div>
        <p className="mb-1 text-xs text-slate-500">Crítico: evaluación de {r.evaluadas.map((e) => e.id).join(", ")} contra R1–R3</p>
        <MatrizReglas evaluaciones={r.evaluaciones} />
      </div>
      {r.objeciones?.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {r.objeciones.map((o, k) => (
            <li key={k}><b style={{ color: colorInterpretacion(o.interpretacion_id).trazo }}>{o.interpretacion_id}</b> · <span title={REGLAS[o.regla]?.nombre}>{o.regla}</span>: {o.texto}</li>
          ))}
        </ul>
      ) : <p className="text-sm text-slate-500">Sin objeciones: todas cumplen R1–R3.</p>}
      {r.refinamiento && (
        <p className="text-sm">
          <span className="text-slate-500">Clasificador: </span>
          conserva {r.refinamiento.interpretaciones.map((i) => i.id).join(", ") || "—"}
          {r.refinamiento.retiradas?.length > 0 && <> · retira {r.refinamiento.retiradas.map((x) => `${x.interpretacion_id} (${x.motivo})`).join(", ")}</>}
          {r.refinamiento.nota && <span className="text-slate-500"> · {r.refinamiento.nota}</span>}
        </p>
      )}
      {r.similitud && (
        <p className="text-sm">
          <span className="text-slate-500">Divergencia: </span>
          similitud {n2(r.similitud.similitud)} {r.similitud.similitud >= umbral ? "≥" : "<"} {umbral}
          {r.similitud.par_minimo && <span className="text-slate-500"> (par mínimo {r.similitud.par_minimo.join("–")})</span>}
        </p>
      )}
      {r.consenso && <p className="text-sm text-emerald-700">Consenso: {MOTIVO[r.consenso.motivo] ?? r.consenso.motivo}; propuesta {r.consenso.propuesta}.</p>}
    </li>
  );
}

export default function TerminoTraza({ t, umbral }) {
  const info = tipo(t.tipo_ambiguedad);
  const res = t.resolucion;
  const via = res ? INFO_VIA[res.via] : null;
  const propuesta = res?.propuesta?.id;
  const final = t.validacion?.final?.id;

  if (t.univoco) {
    return (
      <li className="flex flex-wrap items-baseline gap-2 text-sm">
        <b>«{t.termino}»</b>
        <span className="text-slate-500">unívoco: una sola interpretación razonable (queda en la traza, no entra al LEL)</span>
        {t.origen && t.origen !== "extractor" && <span className="text-xs text-slate-500">· detectado por {t.origen}</span>}
      </li>
    );
  }

  return (
    <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold">«{t.termino}»</h3>
        {t.tipo_ambiguedad && <span className={`rounded px-2 py-0.5 text-xs ${info.clase}`} title={info.descripcion}>{info.etiqueta}</span>}
        {t.origen && t.origen !== "extractor" && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">detectado por {t.origen}</span>}
        {t.univoco == null && <span className="text-xs text-slate-500">esperando al Clasificador…</span>}
        {via && (
          <span className="ml-auto flex items-center gap-2 text-xs text-slate-600">
            <span className="punto" style={{ background: via.tono }} />{via.etiqueta}
            {res.similitud_final != null && <> · similitud final {n2(res.similitud_final)}</>}
          </span>
        )}
      </header>
      {t.detalle && <p className="text-xs text-slate-500">{t.detalle}</p>}

      <section>
        <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Interpretaciones del Clasificador</h4>
        <ul className="grid gap-2 md:grid-cols-2">
          {t.interpretaciones.map((i) => <Interp key={i.id} i={i} propuesta={propuesta} final={final} />)}
        </ul>
      </section>

      {t.divergencia_inicial && (
        <section className="flex flex-wrap items-start gap-6">
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Divergencia</h4>
            <p className="text-sm">
              Similitud mínima entre pares <b>{n2(t.divergencia_inicial.similitud)}</b>{" "}
              {t.divergencia_inicial.similitud >= t.divergencia_inicial.umbral ? "≥" : "<"} umbral {t.divergencia_inicial.umbral}
              {" → "}<b>{String(t.divergencia_inicial.decision).replaceAll("_", " ")}</b>
            </p>
            <p className="text-xs text-slate-500">embeddings: {t.divergencia_inicial.modelo_embeddings}</p>
            <div className="mt-2"><MatrizPares pares={t.divergencia_inicial.pares} parMinimo={t.divergencia_inicial.par_minimo} umbral={t.divergencia_inicial.umbral} /></div>
          </div>
          {t.rondas.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Similitud por ronda</h4>
              <GraficaRondas inicial={t.divergencia_inicial.similitud} rondas={t.rondas} umbral={t.divergencia_inicial.umbral ?? umbral} />
            </div>
          )}
        </section>
      )}

      {t.rondas.length > 0 && (
        <section>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Debate</h4>
          <ol className="space-y-2">{t.rondas.map((r) => <Ronda key={r.ronda} r={r} umbral={t.divergencia_inicial?.umbral ?? umbral} />)}</ol>
        </section>
      )}

      {res && (
        <section className="rounded-lg bg-slate-50 p-3 text-sm">
          <p>
            <b>Resolución:</b> {via?.etiqueta ?? res.via}
            {res.motivo && <> · {MOTIVO[res.motivo] ?? res.motivo}</>}
            {res.propuesta && <> · se propone <b>{res.propuesta.id}</b> «{res.propuesta.significado}»</>}
          </p>
          {res.arbitraje && (
            <ul className="mt-2 space-y-0.5">
              {res.arbitraje.justificacion_por_regla.map((j) => (
                <li key={j.regla}><b>{j.regla}</b> {REGLAS[j.regla]?.nombre}: {j.argumento}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {t.validacion && (
        <p className="text-sm">
          <b>Humano:</b> {CAMBIO[t.validacion.cambio] ?? t.validacion.cambio}
          {t.validacion.final && <> → {t.validacion.final.id} «{t.validacion.final.significado}»</>}
        </p>
      )}
      {t.entrada_lel && (
        <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
          <b>LEL:</b> {t.entrada_lel.simbolo} ({t.entrada_lel.tipo}) · {t.entrada_lel.nocion?.join(" ")}
        </p>
      )}
    </article>
  );
}
