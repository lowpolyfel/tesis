import { useState } from "react";
import { useApp } from "../../components/intro/useApp";
import Button from "../../components/intro/Button";
import Field from "../../components/intro/Field";

/* Acceso sin validación: cualquier dato (o ninguno) deja pasar */
export default function Login() {
  const { go, orb, enter } = useApp();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = (e) => {
    e.preventDefault();
    setBusy(true);
    orb.setShy(false);
    orb.setMood("thinking");
    setTimeout(() => {
      orb.setMood("success");
      setTimeout(enter, 700);
    }, 700);
  };

  return (
    <section className="panel panel-right">
      <div className="eyebrow rise" style={{ "--i": 0 }}>
        <span className="idx">02</span>
        <span className="rule" />
        Iniciar sesión
      </div>
      <h1 className="rise" style={{ "--i": 1 }}>
        Hola de <em>nuevo</em>.
      </h1>
      <form className="form rise" style={{ "--i": 2 }} onSubmit={submit} noValidate>
        <Field label="Correo" type="email" autoComplete="email" value={form.email} onChange={set("email")} />
        <Field label="Contraseña" type="password" autoComplete="current-password" value={form.password} onChange={set("password")} />
        <div className="actions">
          <Button type="submit" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</Button>
          <Button variant="ghost" onClick={() => go("landing")} disabled={busy}>Volver</Button>
        </div>
      </form>
      <p className="switch rise" style={{ "--i": 3 }}>
        ¿Aún no tienes cuenta?{" "}
        <button type="button" className="link" onClick={() => go("register", { poseKey: "register1" })}>Crea una</button>
      </p>
    </section>
  );
}
