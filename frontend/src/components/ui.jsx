import { useState } from "react";
import { Link } from "react-router";
import { estadoSimple } from "../constants/estados";
import { useOrb } from "./orb/useOrb";

/*
 * Piezas comunes de las pantallas. Una sola forma de decir cada cosa: volver,
 * pestañas, estado de un requisito, secciones plegables y avisos de carga.
 */

/* «← Proyecto X»: siempre arriba, siempre al padre lógico (no al historial) */
export function Volver({ a, children }) {
  return (
    <Link to={a} className="mono inline-flex items-center gap-2 text-[10.5px] text-[var(--bone-dim)] hover:text-[var(--bone)]">
      <span aria-hidden="true">←</span> {children}
    </Link>
  );
}

/* Encabezado de pantalla: volver, título y acciones a la derecha */
export function Encabezado({ volver, antetitulo, titulo, children, acciones }) {
  return (
    <header className="space-y-4">
      {volver}
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
          {antetitulo && <p className="etiqueta mb-2">{antetitulo}</p>}
          <h1 className="break-words">{titulo}</h1>
        </div>
        {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
      </div>
      {children}
    </header>
  );
}

/*
 * Pestañas. Al pasar el cursor, la esfera toma el tono de la pestaña: la sección
 * se anuncia antes de entrar. Es una vista previa: solo cambia la esfera, no el fondo
 * (`ambiente: false`), que sigue siendo el de la sección.
 */
export function Pestanas({ opciones, valor, onCambio, etiqueta }) {
  const orb = useOrb();
  const actual = opciones.find((o) => o.id === valor);
  return (
    <div role="tablist" aria-label={etiqueta} className="pestanas" onPointerLeave={() => actual?.mood && orb.setMood(actual.mood, { ambiente: false })}>
      {opciones.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={o.id === valor}
          className="pestana"
          onClick={() => onCambio(o.id)}
          onPointerEnter={() => { if (o.mood) orb.setMood(o.mood, { ambiente: false }); orb.poke(0.25); }}
        >
          {o.texto}{o.cuenta != null && <span className="ml-1.5 opacity-60">{o.cuenta}</span>}
        </button>
      ))}
    </div>
  );
}

export function Chip({ tono, children, titulo, className = "" }) {
  return (
    <span className={`chip ${className}`} style={{ "--tono": tono }} title={titulo}>
      <span className="punto" />{children}
    </span>
  );
}

/* Estado de un requisito en lenguaje claro */
export function EstadoChip({ estado, className = "" }) {
  const s = estadoSimple(estado);
  return (
    <Chip tono={s.tono} titulo={s.descripcion} className={className}>
      {s.id === "analizando" && <span className="gira -ml-0.5 h-2.5 w-2.5" />}
      {s.texto}
    </Chip>
  );
}

/*
 * Sección plegada por omisión: lo técnico no está a la vista de primeras. Con `alAbrir`, lo de
 * adentro se monta la primera vez que se abre (para lo que cuesta dibujar, como un diagrama) y
 * luego se queda montado.
 */
export function Plegable({ titulo, nota, children, abierto = false, alAbrir = false, className = "" }) {
  const [visto, setVisto] = useState(abierto);
  return (
    <details className={`plegable ${className}`} open={abierto}
      onToggle={alAbrir && !visto ? (e) => e.currentTarget.open && setVisto(true) : undefined}>
      <summary className="flex items-center gap-3 py-2">
        <span className="flecha text-[var(--bone-faint)]" aria-hidden="true">▸</span>
        <span className="etiqueta text-[var(--bone-dim)]">{titulo}</span>
        {nota && <span className="text-[12px] text-[var(--bone-faint)]">{nota}</span>}
      </summary>
      <div className="pt-3">{!alAbrir || visto ? children : null}</div>
    </details>
  );
}

export function Cargando({ children = "Cargando…" }) {
  return <p className="mono flex items-center gap-2 text-[10.5px] text-[var(--bone-dim)]"><span className="gira" /> {children}</p>;
}

export function Aviso({ error, children }) {
  if (!error && !children) return null;
  return <p className="text-sm text-[var(--danger)]">{children ?? error?.message}</p>;
}

/* Lo que se muestra cuando una lista está vacía: una frase y, si hay, una acción */
export function Vacio({ children, accion }) {
  return (
    <div className="tarjeta flex flex-wrap items-center justify-between gap-4 px-6 py-6">
      <p className="text-[15px] text-[var(--bone-dim)]">{children}</p>
      {accion}
    </div>
  );
}

/* Confirmación en el sitio para algo que no se puede deshacer (borrar) */
export function Confirmar({ pregunta, detalle, accion = "Borrar", enviando: textoEnviando = "Borrando…", volver = "Cancelar",
  onConfirmar, onCancelar }) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const confirmar = async () => {
    setEnviando(true);
    setError(null);
    try {
      await onConfirmar();
    } catch (e) {
      setError(e);
      setEnviando(false);
    }
  };
  return (
    <div role="alertdialog" aria-label={pregunta} className="tarjeta confirmar space-y-3 p-5">
      <p className="text-[15px]">{pregunta}</p>
      {detalle && <p className="text-[13.5px] leading-relaxed text-[var(--bone-dim)]">{detalle}</p>}
      <Aviso error={error} />
      <div className="flex flex-wrap gap-2">
        <button className="pill sm peligro" onClick={confirmar} disabled={enviando} autoFocus>{enviando ? textoEnviando : accion}</button>
        <button className="pill ghost sm" onClick={onCancelar} disabled={enviando}>{volver}</button>
      </div>
    </div>
  );
}

/* Cifra corta con su nombre */
export function Cifra({ valor, nombre, tono }) {
  return (
    <div>
      <p className="text-[26px] leading-none" style={tono && valor ? { color: tono } : undefined}>{valor ?? "—"}</p>
      <p className="etiqueta mt-1.5">{nombre}</p>
    </div>
  );
}
