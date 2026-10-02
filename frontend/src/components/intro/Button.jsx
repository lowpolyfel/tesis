import { useApp } from "./useApp";

/* Botón que hace reaccionar al orbe al pasar por encima */
export default function Button({ variant = "primary", className = "", children, ...props }) {
  const { orb } = useApp();
  return (
    <button
      type="button"
      className={`btn btn-${variant} ${className}`}
      onPointerEnter={() => orb.poke(0.22)}
      {...props}
    >
      {children}
    </button>
  );
}
