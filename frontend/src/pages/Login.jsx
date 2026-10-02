import { useState } from "react";
import { useApp } from "../hooks/useApp";
import Button from "../components/ui/Button";
import Field from "../components/ui/Field";
import { login } from "../services/auth";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Login() {
  const { go, orb, setSession } = useApp();
  const [form, setForm] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(0);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const fail = (errs) => {
    setErrors(errs);
    setShake((n) => n + 1);
    orb.setMood("error", { revertAfter: 1600 });
  };

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!EMAIL_RE.test(form.email)) errs.email = "Escribe un correo válido.";
    if (!form.password) errs.password = "Escribe tu contraseña.";
    if (Object.keys(errs).length) return fail(errs);

    setErrors({});
    setBusy(true);
    orb.setShy(false);
    orb.setMood("thinking");
    try {
      const session = await login(form);
      orb.setMood("success");
      setSession(session);
      setTimeout(() => go("home"), 1000);
    } catch (err) {
      setBusy(false);
      fail({ form: err.message });
    }
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
      <form key={shake} className={`form rise${shake ? " shake" : ""}`} style={{ "--i": 2 }} onSubmit={submit} noValidate>
        <Field label="Correo" type="email" autoComplete="email" value={form.email} onChange={set("email")} error={errors.email} />
        <Field label="Contraseña" type="password" autoComplete="current-password" value={form.password} onChange={set("password")} error={errors.password} />
        <p className="form-error" role="alert">{errors.form}</p>
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
