import { useCallback, useEffect, useState } from "react";
import { useApi } from "../../hooks/useApi";
import { lexicoDeProyecto, urlMermaidMapa } from "../../services/backend";
import { seccion } from "../../components/orb/secciones";
import EditorMapa from "../../components/fases/EditorMapa";
import GeneracionFase from "../../components/fases/GeneracionFase";
import { Avisos, Desactualizado, Hecho, Historial, Regenerar, SinGenerar, useFase } from "../../components/fases/Fase";
import Diagrama from "../../components/artefactos/Diagrama";
import { Aviso, Cargando, Plegable } from "../../components/ui";

/*
 * Fase 3 (ADR 0024): el mapa conceptual con propósito. Lo arma el Modelador con el LEL
 * validado: una pregunta de enfoque y conceptos —cada uno ligado a su término del LEL—
 * unidos por proposiciones. La persona experta lo edita sobre el propio mapa y valida cada
 * componente; con todo validado se abren las metas.
 */
export default function Mapa({ proyectoId, onCambio, onSeguir }) {
  const { vista, setVista, error, guardar, conservar } = useFase(proyectoId, "mapa", onCambio);
  const { datos: lex } = useApi(() => lexicoDeProyecto(proyectoId), [proyectoId]);
  const [generando, setGenerando] = useState(false);
  const [completa, setCompleta] = useState(false);
  const [version, setVersion] = useState(0); // el editor se vuelve a montar con un mapa nuevo
  const sec = seccion("mapa");

  useEffect(() => {
    if (!completa) return undefined;
    const esc = (e) => e.key === "Escape" && setCompleta(false);
    addEventListener("keydown", esc);
    return () => removeEventListener("keydown", esc);
  }, [completa]);

  const alGuardar = useCallback((contenido) => guardar(contenido), [guardar]);

  if (error) return <Aviso error={error} />;
  if (!vista || !lex) return <Cargando>Cargando el mapa…</Cargando>;
  const doc = vista.documento;
  const simbolosLel = lex.entradas.filter((e) => ["validado", "corregido"].includes(e.estado))
    .map((e) => ({ simbolo: e.simbolo, tipo: e.tipo, intencion: e.intencion }))
    .sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));

  const generacion = generando && (
    <GeneracionFase proyectoId={proyectoId} fase="mapa" seccionId="mapa" moodGenerando="mapa_generando" moodSeccion={sec.mood}
      onListo={(d) => { setGenerando(false); setVista((v) => ({ ...v, documento: d, al_dia: true })); setVersion((n) => n + 1); onCambio?.(); }}
      onCancelar={() => setGenerando(false)} />
  );

  if (!doc) {
    return (
      <>
        <SinGenerar disponible={vista.disponible} motivo={vista.motivo} generando={vista.generando}
          titulo="El mapa conceptual del dominio"
          texto="Con el léxico validado, el Modelador arma un mapa con propósito: la pregunta que el sistema debe responder y los conceptos del dominio unidos por proposiciones que se leen como oraciones («doctor — registra → consulta»). Cada concepto viene de un término del LEL. Luego lo ajustas sobre el propio mapa."
          onGenerar={() => setGenerando(true)} />
        {generacion}
      </>
    );
  }

  return (
    <div className="space-y-5">
      {!vista.al_dia && <Desactualizado que="el mapa" onRegenerar={() => setGenerando(true)} onConservar={conservar} />}
      {vista.hecho && <Hecho texto="El mapa conceptual está validado. Con él y el léxico, los agentes proponen las metas." accion="Seguir a las metas" onAccion={onSeguir} />}
      <EditorMapa key={`${doc.generado}-${version}`} inicial={doc.contenido} simbolosLel={simbolosLel} onGuardar={alGuardar}
        completa={completa} onCompleta={() => setCompleta((x) => !x)} />
      <Avisos avisos={doc.avisos} />
      <Plegable titulo="Exportar" nota="PNG, SVG o Mermaid">
        <ExportarMapa proyectoId={proyectoId} actualizado={doc.actualizado} />
      </Plegable>
      <Historial doc={doc} />
      <div className="flex justify-end"><Regenerar que="el mapa" onConfirmar={() => setGenerando(true)} /></div>
      {generacion}
    </div>
  );
}

/* El mapa guardado como Mermaid (lo arma el backend), dibujado para descargarlo */
function ExportarMapa({ proyectoId, actualizado }) {
  const [mermaid, setMermaid] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetch(urlMermaidMapa(proyectoId), { credentials: "include" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`)))).then(setMermaid).catch(setError);
  }, [proyectoId, actualizado]);
  if (error) return <Aviso error={error} />;
  if (!mermaid) return <Cargando>Preparando…</Cargando>;
  return <Diagrama mermaid={mermaid} nombre="mapa-conceptual" />;
}
