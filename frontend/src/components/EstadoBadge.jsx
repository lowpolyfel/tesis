import { INFO_ESTADO } from "../constants/estados";

export default function EstadoBadge({ estado, className = "" }) {
  const info = INFO_ESTADO[estado];
  if (!info) return null;
  return (
    <span
      title={info.descripcion}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${info.clase} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${info.punto}`} />
      {info.etiqueta}
    </span>
  );
}
