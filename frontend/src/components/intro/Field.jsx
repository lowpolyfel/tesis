import { useId } from "react";
import { useApp } from "./useApp";

/*
 * Campo de formulario. Al enfocarlo el orbe escucha; al escribir reacciona a
 * cada tecla; en campos de contraseña aparta la mirada.
 */
export default function Field({ label, error, type = "text", hint, ...props }) {
  const id = useId();
  const { orb } = useApp();
  const secret = type === "password";

  return (
    <label className={`field${error ? " has-error" : ""}`} htmlFor={id}>
      <span className="field-label">{label}</span>
      <input
        id={id}
        type={type}
        onFocus={() => {
          if (orb.state.mood === "idle" || orb.state.mood === "error") orb.setMood("listening");
          orb.setShy(secret);
        }}
        onBlur={() => {
          if (orb.state.mood === "listening") orb.setMood("idle");
          orb.setShy(false);
        }}
        onInput={() => orb.poke(0.07)}
        aria-invalid={error ? "true" : undefined}
        {...props}
      />
      <span className="field-msg">{error || hint || " "}</span>
    </label>
  );
}
