import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router";
import { useApi } from "../../hooks/useApi";
import { invalidarCache } from "../../hooks/useCache";
import { borrarProyecto, fasesDeProyecto, obtenerProyecto, resumenProyecto } from "../../services/backend";
import { FASES } from "../../constants/fases";
import { olvidarProyecto, recordarProyecto } from "../../components/proyectoRecordado";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Confirmar, Encabezado, Volver } from "../../components/ui";
import Camino from "../../components/fases/Camino";
import Contexto from "../proyecto/Contexto";
import Entrevistas from "./Entrevistas";
import Lexico from "./Lexico";
import Mapa from "./Mapa";
import Metas from "./Metas";
import Requisitos from "./Requisitos";

/*
 * Un proyecto en la versión 2 (ADR 0024): de la entrevista a los requisitos.
 *
 *   Entrevista  lo que dijo el cliente; los agentes la procesan
 *   Léxico      el LEL interactivo: cada término con su intención, validado por la persona experta
 *   Mapa        el mapa conceptual con propósito, editable
 *   Metas       de la organización, estratégicas y específicas
 *   Requisitos  el producto final, con su trazabilidad
 *
 * Cada fase se abre cuando la anterior quedó validada (el camino lo dice). La fase va en
 * ?fase=; si no viene, se abre la que sigue. Mientras una entrevista se procesa, el estado
 * se refresca solo: este es el único sondeo de /fases (las fases solo avisan con onCambio
 * cuando algo cambió). Al terminar, lo que comparten las fases en la caché (léxico, turnos) se
 * vuelve a pedir.
 */
const SONDEO_MS = 2500;
const IDS = FASES.map((f) => f.id);

export default function Proyecto() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const orb = useOrb();
  const { datos: p, setDatos: setP, error } = useApi(() => obtenerProyecto(id), [id]);
  const { datos: estado, recargar } = useApi(() => fasesDeProyecto(id), [id]);
  const { datos: v1 } = useApi(() => resumenProyecto(id).catch(() => null), [id]);
  const [editarPedido, setEditarPedido] = useState(0);
  const [borrando, setBorrando] = useState(false);
  const fase = IDS.includes(params.get("fase")) ? params.get("fase") : null;
  const procesando = estado?.entrevistas.en_proceso ?? 0;

  useEffect(() => recordarProyecto(id), [id]);
  // sin ?fase=, la que sigue (o requisitos, si todo está hecho)
  useEffect(() => {
    if (!fase && estado) setParams({ fase: estado.siguiente ?? "requisitos" }, { replace: true });
  }, [fase, estado, setParams]);
  useEffect(() => {
    if (!procesando) return undefined;
    const t = setInterval(recargar, SONDEO_MS);
    return () => clearInterval(t);
  }, [procesando, recargar]);
  const procesaba = useRef(procesando);
  useEffect(() => {
    if (procesaba.current > procesando) invalidarCache(`${id}:`);
    procesaba.current = procesando;
  }, [procesando, id]);

  if (error) return <div className="space-y-4"><Volver a="/proyectos">Proyectos</Volver><Aviso error={error} /></div>;
  if (!p || !estado) return <Cargando>Cargando el proyecto…</Cargando>;
  if (p.tipo === "evaluacion") return <Navigate to={`/proyectos/${id}/v1`} replace />;

  const ir = (f) => setParams({ fase: f });
  const requisitosV1 = v1?.contadores?.requisitos ?? 0;

  return (
    <div className="space-y-8">
      <Encabezado
        volver={<Volver a="/proyectos">Proyectos</Volver>}
        antetitulo={p.proyecto_id}
        titulo={p.nombre}
        acciones={(
          <>
            <Link className="pill" to={`/proyectos/${id}/entrevista`}>+ Entrevista</Link>
            <button className="pill ghost" onClick={() => setEditarPedido((n) => n + 1)}>Editar</button>
            <button className="pill ghost" onClick={() => setBorrando(true)}>Borrar</button>
          </>
        )}
      >
        {borrando && (
          <Confirmar
            pregunta={`¿Borrar el proyecto «${p.nombre}»?`}
            detalle="Se borran también sus entrevistas, su léxico, lo que aprendió, el mapa, las metas y los requisitos. No se puede deshacer."
            accion="Borrar proyecto"
            onCancelar={() => setBorrando(false)}
            onConfirmar={async () => {
              await borrarProyecto(id);
              olvidarProyecto();
              orb.setMood("idle");
              navigate("/proyectos", { replace: true });
            }}
          />
        )}
        <Contexto p={p} editable pedirEdicion={editarPedido} onGuardado={setP} />
        {requisitosV1 > 0 && (
          <p className="mono text-[10px] text-[var(--bone-faint)]">
            <Link className="hover:text-[var(--bone)]" to={`/proyectos/${id}/v1`}>
              {requisitosV1} requisito{requisitosV1 === 1 ? "" : "s"} analizado{requisitosV1 === 1 ? "" : "s"} con la versión 1 →
            </Link>
          </p>
        )}
      </Encabezado>

      <Camino fases={estado.fases} actual={fase ?? "entrevista"} onElegir={ir} />

      {fase === "entrevista" && <Entrevistas proyectoId={id} onCambio={recargar} />}
      {fase === "lexico" && <Lexico proyectoId={id} estado={estado} onCambio={recargar} onSeguir={() => ir("mapa")} />}
      {fase === "mapa" && <Mapa proyectoId={id} estado={estado} onCambio={recargar} onSeguir={() => ir("metas")} />}
      {fase === "metas" && <Metas proyectoId={id} estado={estado} onCambio={recargar} onSeguir={() => ir("requisitos")} />}
      {fase === "requisitos" && <Requisitos proyecto={p} estado={estado} onCambio={recargar} />}
    </div>
  );
}
