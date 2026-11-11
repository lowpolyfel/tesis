import { useEffect } from "react";
import { Link } from "react-router";
import { useApi } from "../hooks/useApi";
import { resultadosCuestionario, urlCuestionarioCsv, urlCuestionarioOverleaf } from "../services/backend";
import { Aviso, Cargando, Encabezado, Volver } from "../components/ui";

/*
 * Resultados del cuestionario de evaluación (ADR 0033): lo agregado y anónimo, con sus gráficas,
 * y la exportación en CSV (una fila por persona), LaTeX para Overleaf (figuras en pgfplots,
 * tablas booktabs) y PDF (esta misma página impresa: «Guardar como PDF»). Para todas las cuentas,
 * salvo que CUESTIONARIO_ADMINS dé una lista de correos.
 *
 * Las escalas van en barras apiladas al 100 %: naranja = «a mano» o «en desacuerdo», gris = el
 * punto medio, azul = «con DUDAMEL» o «de acuerdo». La paleta divergente se validó con el
 * validador de dataviz en claro y oscuro (pares vecinos ΔE ≥ 15); cada tramo lleva además su
 * número y su porcentaje en el texto al pasar el cursor, y abajo está la tabla completa.
 */
const f1 = (x) => (x == null ? "—" : Number.isInteger(x) ? String(x) : x.toFixed(1));
const pct = (k, n) => (n ? Math.round((100 * k) / n) : 0);

export default function ResultadosCuestionario() {
  const { datos: r, error } = useApi(resultadosCuestionario);
  const fecha = new Date().toISOString().slice(0, 10);

  // el nombre que propone el navegador al «Guardar como PDF»
  useEffect(() => {
    const antes = document.title;
    document.title = `cuestionario-dudamel-${fecha}`;
    return () => { document.title = antes; };
  }, [fecha]);

  const preguntas = r ? Object.fromEntries(r.cuestionario.secciones.flatMap((s) => s.preguntas).map((p) => [p.id, p])) : {};
  const lista = r ? r.cuestionario.secciones.flatMap((s) => s.preguntas) : [];

  return (
    <div className="reporte space-y-10">
      <Encabezado
        volver={<span className="no-print"><Volver a="/mas">Más</Volver></span>}
        antetitulo="Evaluación con usuarios"
        titulo="Resultados del cuestionario"
        acciones={r && (
          <div className="no-print flex flex-wrap gap-2">
            <a className="pill ghost sm" href={urlCuestionarioCsv()} download>CSV</a>
            <a className="pill ghost sm" href={urlCuestionarioOverleaf()} download>LaTeX (Overleaf)</a>
            <button className="pill sm" onClick={() => window.print()} disabled={!r.enviados}>PDF</button>
          </div>
        )}
      >
        <p className="max-w-2xl text-[14.5px] leading-relaxed text-[var(--bone-dim)]">
          Solo cuentan los cuestionarios enviados. Es anónimo: ni la cuenta ni el correo; en el CSV cada persona es R01, R02… por orden de envío.
          {r && <> Al {fecha}.</>}
        </p>
      </Encabezado>

      {error?.status === 403 ? <SinPermiso /> : <Aviso error={error} />}
      {!r && !error && <Cargando>Calculando los resultados…</Cargando>}

      {r && (
        <>
          <Exportar r={r} />
          <section className="space-y-4" aria-label="Resumen">
            <div className="flex flex-wrap gap-x-10 gap-y-4">
              <Dato valor={r.enviados} nombre="enviados" />
              <Dato valor={r.borradores} nombre="a medias (no cuentan)" />
              <Dato valor={f1(r.sus.media)} nombre="SUS media" />
              <Dato valor={f1(r.sus.mediana)} nombre="SUS mediana" />
              <Dato valor={f1(r.sus.de)} nombre="SUS desv. estándar" />
              <Dato valor={r.con_fallas_de_infraestructura} nombre="con fallas (P50)" />
            </div>
            {r.con_fallas_de_infraestructura > 0 && (
              <p className="max-w-2xl text-[13.5px] leading-relaxed text-[var(--aviso)]">
                {r.con_fallas_de_infraestructura} de {r.enviados} persona(s) dijeron haber tenido fallas de infraestructura (P50). El protocolo pide declararlo antes de concluir sobre la usabilidad.
              </p>
            )}
          </section>

          {r.enviados === 0 ? (
            <div className="tarjeta p-6 text-[15px] text-[var(--bone-dim)]">Todavía no hay cuestionarios enviados. Las gráficas aparecen con el primero.</div>
          ) : (
            <>
              <Figura titulo="Puntaje SUS" nota="Un punto por persona, agrupado por decenas. El SUS va de 0 a 100 y no es un porcentaje; 68 es el promedio de referencia que se suele citar.">
                <HistogramaSus valores={r.sus.valores} media={r.sus.media} />
              </Figura>

              {r.grupos.map((g) => (
                <Figura key={g.id} titulo={g.titulo}
                  nota={g.id === "sus" ? "Los ítems pares del SUS están redactados en negativo: ahí, «de acuerdo» es malo." : "% de quienes contestaron cada pregunta."}>
                  <Apiladas grupo={g} preguntas={preguntas} r={r} />
                </Figura>
              ))}

              <Figura titulo="Preguntas de opción" nota="Personas que eligieron cada opción. En las de casillas se podían marcar varias.">
                <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
                  {lista.filter((p) => p.tipo === "opcion" || p.tipo === "casillas").map((p) => (
                    <Opciones key={p.id} p={p} x={r.preguntas[p.id]} />
                  ))}
                </div>
              </Figura>

              <Figura titulo="Conteos" nota="Media, mediana y rango.">
                <Tabla encabezado={["P", "Pregunta", "n", "Media", "Mediana", "Rango"]}
                  filas={lista.filter((p) => p.tipo === "numero").map((p) => {
                    const x = r.preguntas[p.id];
                    return [p.n, p.texto, x.n, f1(x.media), f1(x.mediana), x.n ? `${x.minimo}–${x.maximo}` : "—"];
                  })} />
              </Figura>

              <Figura titulo="Escalas (tabla)" nota="Mediana y rango intercuartílico (RIC). En P9–P20, el % que quedó arriba del punto medio (mejor con DUDAMEL).">
                <Tabla encabezado={["P", "Pregunta", "n", "Mediana", "RIC", "> 3"]}
                  filas={lista.filter((p) => p.tipo === "escala").map((p) => {
                    const x = r.preguntas[p.id];
                    return [p.n, p.texto, x.n, f1(x.mediana), x.n ? `${f1(x.q1)}–${f1(x.q3)}` : "—",
                      x.arriba_del_medio != null ? `${Math.round(100 * x.arriba_del_medio)} %` : "—"];
                  })} />
              </Figura>

              <Figura titulo="Respuestas abiertas" nota="Sin la cuenta, para la codificación temática.">
                <div className="space-y-6">
                  {lista.filter((p) => p.tipo === "texto").map((p) => (
                    <div key={p.id} className="evitar-corte space-y-2">
                      <p className="text-[14.5px]"><span className="mono mr-2 text-[11px] text-[var(--bone-faint)]">P{p.n}</span>{p.texto}</p>
                      {r.preguntas[p.id].respuestas.length ? (
                        <ul className="list-disc space-y-1 pl-5 text-[14px] leading-relaxed text-[var(--bone-dim)]">
                          {r.preguntas[p.id].respuestas.map((t, i) => <li key={i}>{t}</li>)}
                        </ul>
                      ) : <p className="text-[13px] italic text-[var(--bone-faint)]">Sin respuestas.</p>}
                    </div>
                  ))}
                </div>
              </Figura>
            </>
          )}
        </>
      )}
    </div>
  );
}

function SinPermiso() {
  return (
    <div className="tarjeta space-y-2 p-6">
      <p className="text-[15px]">En este servidor, los resultados están restringidos a algunas cuentas.</p>
      <p className="max-w-2xl text-[14px] leading-relaxed text-[var(--bone-dim)]">
        Los limita la variable <code className="mono text-[12.5px]">CUESTIONARIO_ADMINS</code> (en Render, en «Environment»): con una lista de correos, solo esos los ven; vacía o con <code className="mono text-[12.5px]">*</code>, todas las cuentas. Si quieres contestar el cuestionario, está en <Link className="enlace" to="/cuestionario">el lobby de proyectos</Link>.
      </p>
    </div>
  );
}

function Exportar({ r }) {
  const formatos = [
    { a: urlCuestionarioCsv(), nombre: "CSV", que: "Una fila por persona (R01, R02…) con las 60 respuestas y su SUS. Para Excel, SPSS o R." },
    { a: urlCuestionarioOverleaf(), nombre: "LaTeX para Overleaf", que: "Un .zip con main.tex, las figuras en pgfplots, tablas booktabs y los datos. Compila con pdfLaTeX o XeLaTeX." },
    { imprimir: true, nombre: "PDF", que: "Esta página con sus gráficas: elige «Guardar como PDF» en el diálogo de impresión." },
  ];
  return (
    <section className="no-print grid gap-3 sm:grid-cols-3" aria-label="Exportar">
      {formatos.map((f) => {
        const cuerpo = (
          <>
            <p className="etiqueta">Exportar</p>
            <p className="serif mt-1 text-[22px] leading-tight">{f.nombre}</p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-[var(--bone-dim)]">{f.que}</p>
          </>
        );
        const clase = "tarjeta tarjeta-viva block h-full p-5 text-left";
        return f.imprimir
          ? <button key={f.nombre} className={clase} onClick={() => window.print()} disabled={!r.enviados}>{cuerpo}</button>
          : <a key={f.nombre} className={clase} href={f.a} download>{cuerpo}</a>;
      })}
    </section>
  );
}

function Figura({ titulo, nota, children }) {
  return (
    <section className="figura-reporte evitar-corte space-y-4">
      <header className="space-y-1">
        <p role="heading" aria-level={2} className="serif text-[24px] leading-tight">{titulo}</p>
        {nota && <p className="max-w-2xl text-[13px] leading-relaxed text-[var(--bone-faint)]">{nota}</p>}
      </header>
      {children}
    </section>
  );
}

function Dato({ valor, nombre }) {
  return (
    <div>
      <p className="text-[28px] leading-none">{valor ?? "—"}</p>
      <p className="etiqueta mt-1.5">{nombre}</p>
    </div>
  );
}

/* ---------------------------------------------------------------- gráficas */

/* Histograma por decenas (0–10 … 90–100), con la media y la referencia de 68 */
function HistogramaSus({ valores, media }) {
  const cuentas = Array(10).fill(0);
  for (const v of valores) cuentas[Math.min(Math.floor(v / 10), 9)] += 1;
  const tope = Math.max(2, ...cuentas);
  const W = 640, H = 264, iz = 34, ab = 34, ar = 38, de = 10; // arriba, el margen para rotular la media y el 68
  const x = (v) => iz + ((W - iz - de) * v) / 100;
  const y = (k) => ar + (H - ar - ab) * (1 - k / tope);
  const marcas = Array.from({ length: tope + 1 }, (_, k) => k).filter((k) => tope <= 6 || k % Math.ceil(tope / 5) === 0);
  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-3xl" role="img"
        aria-label={`Histograma del SUS: ${valores.length} personas, media ${f1(media)}`}>
        {marcas.map((k) => (
          <g key={k}>
            <line x1={iz} x2={W - de} y1={y(k)} y2={y(k)} className="reja" />
            <text x={iz - 8} y={y(k) + 4} textAnchor="end" className="eje-texto">{k}</text>
          </g>
        ))}
        {cuentas.map((k, i) => (
          <g key={i} className="marca">
            <title>{`${i * 10}–${i === 9 ? 100 : i * 10 + 9}: ${k} persona(s)`}</title>
            <rect x={x(i * 10)} y={ar} width={x(10) - x(0)} height={H - ar - ab} fill="transparent" />
            {k > 0 && <rect x={x(i * 10) + 2} y={y(k)} width={x(10) - x(0) - 4} height={y(0) - y(k)} rx={4} className="barra-una" />}
          </g>
        ))}
        <line x1={iz} x2={W - de} y1={y(0)} y2={y(0)} className="eje" />
        {[0, 20, 40, 60, 80, 100].map((v) => <text key={v} x={x(v)} y={H - ab + 18} textAnchor="middle" className="eje-texto">{v}</text>)}
        <line x1={x(68)} x2={x(68)} y1={ar - 8} y2={y(0)} className="referencia" />
        <text x={x(68) + 5} y={ar - 2} className="eje-texto">68 referencia</text>
        {media != null && (
          <>
            <line x1={x(media)} x2={x(media)} y1={ar - 22} y2={y(0)} className="media" />
            <text x={x(media) + 5} y={ar - 16} className="eje-texto fuerte">media {f1(media)}</text>
          </>
        )}
      </svg>
      <p className="mono text-[10.5px] text-[var(--bone-faint)]">Puntajes: {valores.map(f1).join(" · ")}</p>
    </div>
  );
}

/* Barras apiladas al 100 % por pregunta, con su leyenda arriba */
function Apiladas({ grupo, preguntas, r }) {
  return (
    <div className="space-y-4">
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5" aria-label="Leyenda">
        {grupo.niveles.map((nv, i) => (
          <li key={nv} className="flex items-center gap-2 text-[12.5px] text-[var(--bone-dim)]">
            <span className="h-3 w-3 flex-none rounded-[3px]" style={{ background: `var(--div${i + 1})` }} />{i + 1} · {nv}
          </li>
        ))}
      </ul>
      <div className="space-y-3">
        {grupo.preguntas.map((qid) => {
          const p = preguntas[qid], x = r.preguntas[qid];
          return (
            <div key={qid} className="grid gap-1.5 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:items-center md:gap-5">
              <p className="text-[13.5px] leading-snug text-[var(--bone-dim)]">
                <span className="mono mr-1.5 text-[10.5px] text-[var(--bone-faint)]">P{p.n}</span>{p.texto}
              </p>
              <div className="flex items-center gap-3">
                <div className="flex h-6 flex-1 gap-[2px]" role="img"
                  aria-label={`P${p.n}: ${[1, 2, 3, 4, 5].map((v) => `${grupo.niveles[v - 1]} ${x.frecuencias?.[v] ?? 0}`).join(", ")}`}>
                  {[1, 2, 3, 4, 5].map((v) => {
                    const k = x.frecuencias?.[v] ?? 0;
                    if (!k) return null;
                    const q = pct(k, x.n);
                    return (
                      <div key={v} title={`P${p.n} · ${grupo.niveles[v - 1]}: ${k} persona(s), ${q} %`}
                        className="tramo flex items-center justify-center first:rounded-l-[4px] last:rounded-r-[4px]"
                        style={{ width: `${(100 * k) / x.n}%`, background: `var(--div${v})`, color: `var(--div${v}-tinta)` }}>
                        {q >= 10 && <span className="mono text-[10px]">{q}</span>}
                      </div>
                    );
                  })}
                </div>
                <span className="mono w-16 flex-none text-right text-[10.5px] text-[var(--bone-faint)]">Md {f1(x.mediana)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* Una pregunta de opción o casillas: barras horizontales de un solo tono con su cuenta */
function Opciones({ p, x }) {
  const max = Math.max(1, ...Object.values(x.frecuencias ?? {}));
  return (
    <div className="evitar-corte space-y-2">
      <p className="text-[14px] leading-snug">
        <span className="mono mr-1.5 text-[10.5px] text-[var(--bone-faint)]">P{p.n}</span>{p.texto}
        {p.tipo === "casillas" && <span className="ml-1.5 text-[12px] text-[var(--bone-faint)]">(varias)</span>}
      </p>
      <ul className="space-y-1.5">
        {p.opciones.map((o) => {
          const k = x.frecuencias?.[o] ?? 0;
          return (
            <li key={o} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-3" title={`${o}: ${k} persona(s), ${pct(k, x.n)} % de ${x.n}`}>
              <span className="text-[12.5px] leading-snug text-[var(--bone-dim)]">{o}</span>
              <span className="flex items-center gap-2">
                <span className="h-3.5 rounded-r-[4px] barra-una-fondo" style={{ width: `${(85 * k) / max}%`, minWidth: k ? 3 : 0 }} />
                <span className="mono text-[10.5px] text-[var(--bone-dim)]">{k}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Tabla({ encabezado, filas }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-[13px]">
        <thead className="etiqueta"><tr>{encabezado.map((h) => <th key={h} className="py-2 pr-3 font-normal">{h}</th>)}</tr></thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f[0]} className="border-t border-[var(--line)] align-top">
              {f.map((c, i) => (
                <td key={i} className={`py-2 pr-3 ${i === 1 ? "text-[var(--bone-dim)]" : "mono whitespace-nowrap text-[11.5px]"}`}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
