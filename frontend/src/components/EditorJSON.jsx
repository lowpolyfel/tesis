import { useState } from "react";

/* Edita un objeto como JSON; avisa errores de sintaxis sin perder lo escrito */
export default function EditorJSON({ valor, onChange, onErrorChange, filas = 16 }) {
  const [texto, setTexto] = useState(() => JSON.stringify(valor, null, 2));
  const [error, setError] = useState(null);

  const cambiar = (t) => {
    setTexto(t);
    try {
      const obj = JSON.parse(t);
      setError(null);
      onErrorChange?.(null);
      onChange(obj);
    } catch (e) {
      setError(e.message);
      onErrorChange?.(e.message);
    }
  };

  return (
    <div>
      <textarea
        value={texto}
        onChange={(e) => cambiar(e.target.value)}
        rows={filas}
        spellCheck={false}
        className={`w-full rounded border p-2 font-mono text-xs ${error ? "border-red-400 bg-red-50" : "border-slate-300"}`}
      />
      {error && <p className="text-xs text-red-600">JSON inválido: {error}</p>}
    </div>
  );
}
