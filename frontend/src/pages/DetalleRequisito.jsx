import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useState } from "react";
import { useRequisito } from "../hooks/useRequisito";
import { reprocesarRequisito } from "../services/api";
import { ESTADOS as E, INFO_ESTADO, VIAS_RESOLUCION as V, estaEnProceso } from "../constants/estados";
import { AGENTES } from "../constants/agentes";
import EstadoBadge from "../components/EstadoBadge";
import LineaEstados from "../components/LineaEstados";
import TextoResaltado from "../components/TextoResaltado";
import Etapa from "../components/Etapa";
import MedidorSimilitud from "../components/MedidorSimilitud";
import InterpretacionCard from "../components/InterpretacionCard";
import PanelDebate from "../components/debate/PanelDebate";

/*
 * Pantalla 3: traza completa de un requisito, por etapas y en orden.
 * Pensada para leerse en una captura (también con ?figura=1).
 */

const CATEGORIAS = [
  ["sujeto", "Sujetos"],
  ["verbo", "Verbos"],
  ["objeto", "Objetos"],
  ["estado", "Estados"],
  ["restriccion", "Restricciones"],
];

const segundos = (ms) => `${(ms / 1000).toFixed(1)} s`;
const hora = (iso) => new Date(iso).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "medium" });

export default function DetalleRequisito() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const figura = params.get("figura") === "1";
  const { requisito: r, recargar } = useRequisito(id);

  if (!r) return <p className="text-sm text-slate-500">Cargando {id}…</p>;

  const t = r.traza;
  const enProceso = estaEnProceso(r.estado);
  // La primera etapa sin datos es la que los agentes están trabajando
  const orden = ["extraccion", "clasificacion", "divergencia", "debate", "resolucion", "artefactos"];
  const falta = (k) =>
    k === "debate"
      ? t.divergencia?.decision !== "directo" && (!t.debate || t.debate.resultado === "en_curso")
      : !t[k];
  const faltantes = orden.filter(falta);
  const enCurso = enProceso ? faltantes[0] : null;
  const estadoEtapa = (k) => (t[k] ? "hecho" : enCurso === k ? "curso" : "pendiente");

  return (
    <div className="space-y-5">
      <Encabezado r={r} figura={figura} recargar={recargar} />

      <section className="rounded-lg border border-slate-200 bg-white px-4 py-3">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Camino en la máquina de estados</p>
        <LineaEstados historial={r.historial} estado={r.estado} />
      </section>

      {/* 1 */}
      <Etapa numero={1} titulo="Requisito original" meta={`${r.origen}`}>
        <TextoResaltado texto={r.texto} marcados={t.extraccion?.marcados ?? []} conLeyenda={Boolean(t.extraccion)} />
        {!t.extraccion && <p className="mt-2 text-sm text-slate-500">Los términos ambiguos se marcarán al terminar la extracción.</p>}
      </Etapa>

      {/* 2 */}
      <Etapa
        numero={2}
        titulo="Extracción"
        agente={`${AGENTES.extractor.nombre} — ${AGENTES.extractor.rol.toLowerCase()}`}
        meta={t.extraccion && `${t.extraccion.modelo} · ${segundos(t.extraccion.duracionMs)}`}
        estado={estadoEtapa("extraccion")}
      >
        {t.extraccion && (
          <dl className="grid gap-3 sm:grid-cols-5">
            {CATEGORIAS.map(([cat, nombre]) => {
              const terminos = t.extraccion.terminos.filter((x) => x.categoria === cat);
              return (
                <div key={cat}>
                  <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{nombre}</dt>
                  <dd className="flex flex-wrap gap-1">
                    {terminos.length ? terminos.map((x) => (
                      <span key={x.texto} title={`lema: ${x.lema}`} className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">{x.texto}</span>
                    )) : <span className="text-sm text-slate-400">—</span>}
                  </dd>
                </div>
              );
            })}
          </dl>
        )}
      </Etapa>

      {/* 3 */}
      <Etapa
        numero={3}
        titulo="Interpretaciones candidatas"
        agente={`${AGENTES.clasificador.nombre} — ${AGENTES.clasificador.rol.toLowerCase()}`}
        meta={t.clasificacion && `${t.clasificacion.modelo} · ${segundos(t.clasificacion.duracionMs)}`}
        estado={estadoEtapa("clasificacion")}
      >
        {t.clasificacion && (
          <>
            <p className="mb-3 text-sm text-slate-600">
              Términos en disputa:{" "}
              {t.clasificacion.enDisputa.length
                ? t.clasificacion.enDisputa.map((x) => `«${x}»`).join(", ")
                : "ninguno (las lecturas solo difieren en la redacción)"}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {["A", "B"].map((k) => (
                <InterpretacionCard
                  key={k}
                  clave={k}
                  interpretacion={t.clasificacion.interpretaciones[k]}
                  destacada={t.resolucion?.via === V.ARBITRAJE && t.resolucion.eleccion === k}
                />
              ))}
            </div>
          </>
        )}
      </Etapa>

      {/* 4 */}
      <Etapa
        numero={4}
        titulo="Divergencia: similitud coseno"
        agente="Mecanismo de divergencia (no es un agente)"
        estado={t.divergencia ? "hecho" : enCurso === "divergencia" ? "curso" : "pendiente"}
      >
        {t.divergencia && (
          <MedidorSimilitud similitud={t.divergencia.similitud} umbral={t.divergencia.umbral} modelo={t.divergencia.modeloEmbeddings} />
        )}
      </Etapa>

      {/* 5 */}
      <Etapa
        id="debate"
        numero={5}
        titulo="Debate"
        agente={`Clasificador defiende cada lectura; ${AGENTES.critico.nombre} conduce y arbitra`}
        meta={t.debate?.arbitraje?.modelo && `árbitro: ${t.debate.arbitraje.modelo}`}
        estado={
          t.divergencia?.decision === "directo" ? "omitida"
            : t.debate ? "hecho"
            : enCurso === "debate" ? "curso" : "pendiente"
        }
      >
        {t.divergencia?.decision === "directo" ? (
          <p className="text-sm text-slate-600">
            No hubo debate: la similitud inicial ({t.divergencia.similitud.toFixed(2)}) quedó por arriba del umbral ({t.divergencia.umbral.toFixed(2)}).
          </p>
        ) : t.debate && (
          <PanelDebate debate={t.debate} similitudInicial={t.divergencia.similitud} />
        )}
      </Etapa>

      {/* 6 */}
      <Etapa numero={6} titulo="Resolución" estado={estadoEtapa("resolucion")}>
        {t.resolucion && <Resolucion resolucion={t.resolucion} />}
      </Etapa>

      {/* 7 */}
      <Etapa
        numero={7}
        titulo="Artefactos y validación humana"
        agente={`${AGENTES.modelador.nombre} — ${AGENTES.modelador.rol.toLowerCase()}`}
        meta={t.artefactos?.modelo}
        estado={estadoEtapa("artefactos")}
      >
        {t.artefactos && <Validacion r={r} figura={figura} />}
      </Etapa>

      {!figura && <Historial historial={r.historial} />}
    </div>
  );
}

/* ---------------------------------------------------------------- */

function Encabezado({ r, figura, recargar }) {
  const navigate = useNavigate();
  const [ocupado, setOcupado] = useState(false);
  const cfg = r.configUsada;

  const reprocesar = async () => {
    setOcupado(true);
    try {
      await reprocesarRequisito(r.id);
      recargar();
    } finally {
      setOcupado(false);
    }
  };

  return (
    <header className="space-y-3">
      {!figura && (
        <nav className="text-sm text-slate-500">
          <Link to="/cola" className="hover:underline">Cola</Link> / {r.id}
        </nav>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{r.id}</h1>
        <EstadoBadge estado={r.estado} className="text-sm" />
        {estaEnProceso(r.estado) && (
          <span className="flex items-center gap-1.5 text-sm text-amber-700">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            procesando (se actualiza solo)
          </span>
        )}
        {!figura && (
          <div className="ml-auto flex flex-wrap gap-2">
            {r.estado === E.PENDIENTE_VALIDACION && (
              <button onClick={() => navigate(`/requisitos/${r.id}/validacion`)} className="rounded bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700">
                Validar artefactos
              </button>
            )}
            {r.estado === E.RECHAZADO && (
              <button onClick={reprocesar} disabled={ocupado} className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
                Reprocesar con la configuración actual
              </button>
            )}
            <Link to={`/requisitos/${r.id}?figura=1`} target="_blank" className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
              Vista para captura ↗
            </Link>
          </div>
        )}
      </div>
      <p className="text-sm text-slate-500">
        {INFO_ESTADO[r.estado].descripcion}{" "}
        Procesado con umbral <span className="font-mono">{cfg.umbral.toFixed(2)}</span>, máximo{" "}
        <span className="font-mono">{cfg.maxRondas}</span> {cfg.maxRondas === 1 ? "ronda" : "rondas"}.
      </p>
      {r.simulado && !figura && (
        <p className="rounded bg-slate-100 px-3 py-1.5 text-xs text-slate-600">
          Traza generada por el simulador (texto sin fixture escrito a mano): los argumentos son de relleno.
        </p>
      )}
    </header>
  );
}

function Resolucion({ resolucion }) {
  const titulo = {
    [V.DIRECTO]: "Aceptación directa",
    [V.CONSENSO]: `Consenso en la ronda ${resolucion.ronda}`,
    [V.ARBITRAJE]: "Arbitraje del Crítico",
  }[resolucion.via];
  const color = {
    [V.DIRECTO]: "border-teal-500",
    [V.CONSENSO]: "border-emerald-500",
    [V.ARBITRAJE]: "border-orange-500",
  }[resolucion.via];

  return (
    <div className="space-y-2">
      <p className="text-sm">
        <span className="text-slate-500">Cómo se llegó: </span>
        <strong>{titulo}</strong>
      </p>
      <blockquote className={`border-l-4 ${color} bg-slate-50 px-3 py-2 text-base text-slate-900`}>
        {resolucion.interpretacion}
      </blockquote>
      <p className="text-sm text-slate-600">{resolucion.explicacion}</p>
    </div>
  );
}

function Validacion({ r, figura }) {
  const ultimo = r.historial.at(-1);
  const lel = (r.artefactos.validados ?? r.artefactos.propuesta).lel;

  return (
    <div className="space-y-3 text-sm">
      <p>
        Entrada del LEL propuesta: <strong>«{lel.simbolo}»</strong> ({lel.tipo}). También se generaron el modelo de metas y el Big Picture.
      </p>
      {r.estado === E.PENDIENTE_VALIDACION && (
        <p className="rounded bg-violet-50 px-3 py-2 text-violet-900">
          Esperando revisión humana.{" "}
          {!figura && <Link className="font-medium underline" to={`/requisitos/${r.id}/validacion`}>Revisar y editar los artefactos →</Link>}
        </p>
      )}
      {[E.VALIDADO, E.FORMALIZADO].includes(r.estado) && (
        <p className="rounded bg-green-50 px-3 py-2 text-green-900">
          Validado {r.historial.find((h) => h.estado === E.VALIDADO)?.editado ? "con ediciones de la persona revisora" : "sin cambios"}.
          {r.estado === E.FORMALIZADO && " Incorporado al LEL acumulado."}{" "}
          {!figura && <Link className="font-medium underline" to={`/requisitos/${r.id}/validacion`}>Ver artefactos</Link>}
        </p>
      )}
      {r.estado === E.RECHAZADO && (
        <p className="rounded bg-red-50 px-3 py-2 text-red-900">
          Rechazado: {ultimo.comentario || "sin comentario."}
        </p>
      )}
    </div>
  );
}

function Historial({ historial }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
      <summary className="cursor-pointer py-1 font-medium">Historial de estados ({historial.length})</summary>
      <table className="mt-2 w-full text-left">
        <tbody>
          {historial.map((h, i) => (
            <tr key={i} className="border-t border-slate-100">
              <td className="py-1 pr-4 font-mono text-xs text-slate-500">{hora(h.en)}</td>
              <td className="py-1 pr-4"><EstadoBadge estado={h.estado} /></td>
              <td className="py-1 text-slate-600">{h.comentario}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
