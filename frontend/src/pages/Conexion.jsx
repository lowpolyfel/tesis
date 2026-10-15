import { useApi } from "../hooks/useApi";
import { probarConexion } from "../services/backend";
import { Aviso, Cargando, Chip, Cifra, Encabezado, Vacio } from "../components/ui";

/*
 * A qué base de datos está conectado el backend (GET /conexion): Atlas, un Mongo
 * local o el respaldo JSON. «Probar otra vez» mide de nuevo el ping, la versión,
 * las colecciones y una escritura de prueba. La URI no se cambia desde aquí: vive
 * en el .env de la raíz y el backend la lee al arrancar (hay que reiniciarlo).
 */
// Con versión clara y oscura (styles/dudamel.css)
const VERDE = "var(--ok)";
const AMARILLO = "var(--aviso)";
const ROJO = "var(--danger)";

const FUENTE = {
  env_raiz: ".env de la raíz",
  env_backend: "backend/.env (gana al de la raíz)",
  variable_de_sistema: "variable de entorno del sistema (gana a los dos .env)",
  default: "valor por omisión (ningún .env define MONGO_URI)",
};

function estado(c) {
  if (c.persistencia === "json") {
    return { tono: ROJO, titulo: "Sin Mongo: usando JSON", nota: "El backend no pudo conectarse al arrancar y guarda todo en archivos JSON locales. Corrige MONGO_URI y reinicia uvicorn." };
  }
  if (c.tipo === "atlas") return { tono: VERDE, titulo: "Conectado a Atlas", nota: "La base de la nube." };
  if (c.tipo === "local") return { tono: AMARILLO, titulo: "Conectado a Mongo local", nota: "No es la base de la nube." };
  return { tono: AMARILLO, titulo: "Conectado a otro Mongo", nota: "No es Atlas ni un Mongo local." };
}

const ms = (x) => (x == null ? null : `${x} ms`);

export default function Conexion() {
  const { datos: c, error, cargando, recargar } = useApi(probarConexion, [], { silencioso: false });

  return (
    <div className="space-y-8">
      <Encabezado
        antetitulo="Base de datos del backend"
        titulo="Conexión."
        acciones={(
          <button className="pill ghost sm" onClick={recargar} disabled={cargando}>
            {cargando && c ? <><span className="gira" /> Probando…</> : "Probar otra vez"}
          </button>
        )}
      />

      {cargando && !c && !error && <Cargando>Probando la conexión…</Cargando>}
      <Aviso error={error} />
      {c && !error && <Detalle c={c} />}
    </div>
  );
}

function Detalle({ c }) {
  const e = estado(c);
  const mongo = c.persistencia === "mongo";
  const escritura = c.prueba_escritura;

  return (
    <>
      <section className="tarjeta space-y-3 p-6" style={{ borderColor: `color-mix(in oklab, ${e.tono} 55%, transparent)` }}>
        <p className="serif flex items-center gap-3 text-[34px] leading-tight" style={{ color: e.tono }}>
          <span className="punto h-3 w-3" style={{ background: e.tono, boxShadow: `0 0 14px ${e.tono}` }} />
          {e.titulo}
        </p>
        <p className="text-[15px] text-[var(--bone-dim)]">{e.nota}</p>
        {c.error && (
          <p className="font-mono text-[12.5px] leading-relaxed break-words whitespace-pre-wrap text-[var(--danger)]">
            {mongo ? "Ahora no responde: " : ""}{c.error}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2>Servidor</h2>
        <div className="flex flex-wrap gap-x-12 gap-y-5">
          <Cifra valor={ms(c.ping_ms)} nombre="Ping" />
          <Cifra valor={c.version_servidor} nombre="Versión del servidor" />
        </div>
        <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
          {[
            [mongo ? "Host" : "Intentó conectarse a", c.host || "—"],
            ["Base", c.base],
            ["MONGO_URI sale de", FUENTE[c.fuente_uri] ?? c.fuente_uri],
            ["Checkpoints", c.checkpoints],
          ].map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="etiqueta">{k}</dt>
              <dd className="mt-1 font-mono text-[12.5px] break-words">{v}</dd>
            </div>
          ))}
        </dl>
        {c.fuente_uri !== "env_raiz" && (
          <p className="text-[13px] text-[var(--aviso)]">MONGO_URI debería venir solo del .env de la raíz.</p>
        )}
      </section>

      {mongo && (
        <section className="space-y-3">
          <h2>Prueba de escritura</h2>
          {escritura ? (
            <div className="flex flex-wrap items-center gap-3">
              <Chip tono={escritura.ok ? VERDE : ROJO}>{escritura.ok ? "Escribe, lee y borra" : "Falló"}</Chip>
              <span className="mono text-[10.5px] text-[var(--bone-dim)]">{ms(escritura.ms)}</span>
              {escritura.error && <p className="basis-full font-mono text-[12.5px] break-words text-[var(--danger)]">{escritura.error}</p>}
            </div>
          ) : (
            <p className="text-[14px] text-[var(--bone-dim)]">No se intentó: el servidor no respondió al ping.</p>
          )}
        </section>
      )}

      {mongo && (
        <section className="space-y-3">
          <h2>Colecciones de {c.base}</h2>
          {c.colecciones.length ? (
            <div className="overflow-x-auto rounded-2xl border border-[var(--line)]">
              <table className="w-full text-left text-sm">
                <thead className="mono text-[9.5px] text-[var(--bone-faint)]">
                  <tr>
                    <th className="px-4 py-2 font-normal">Colección</th>
                    <th className="w-36 px-4 py-2 text-right font-normal">Documentos</th>
                  </tr>
                </thead>
                <tbody>
                  {c.colecciones.map((x) => (
                    <tr key={x.nombre} className="border-t border-[var(--line)]">
                      <td className="px-4 py-2 font-mono text-[12.5px]">{x.nombre}</td>
                      <td className="px-4 py-2 text-right font-mono text-[12.5px]">{x.documentos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Vacio>{c.error ? "No se pudieron leer las colecciones." : "La base no tiene colecciones todavía."}</Vacio>
          )}
        </section>
      )}
    </>
  );
}
