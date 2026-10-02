import { useEffect, useRef, useState } from "react";
import { useApp } from "../hooks/useApp";
import Button from "../components/ui/Button";
import Field from "../components/ui/Field";
import Steps from "../components/ui/Steps";
import { register } from "../services/auth";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ROLES = ["Estudiante", "Analista de requisitos", "Docente o investigador", "Otro"];
// El formulario cambia de lado en cada paso y el orbe cruza la pantalla
const SIDE = { 1: "left", 2: "right", 3: "left" };
const STEP_EXIT_MS = 380;

function strength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s;
}
const STRENGTH_LABEL = ["Muy débil", "Débil", "Aceptable", "Buena", "Excelente"];

export default function Register() {
  const { go, orb, pose, setSession } = useApp();
  const [step, setStep] = useState(1);
  const [leaving, setLeaving] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "", role: "", terms: false });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(0);
  const timer = useRef();
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  useEffect(() => () => clearTimeout(timer.current), []);

  const fail = (errs) => {
    setErrors(errs);
    setShake((n) => n + 1);
    orb.setMood("error", { revertAfter: 1600 });
  };

  const toStep = (n, errs = {}) => {
    setErrors(errs);
    pose(`register${n}`);
    orb.setShy(false);
    orb.poke(0.9);
    setLeaving(true);
    timer.current = setTimeout(() => { setStep(n); setLeaving(false); }, STEP_EXIT_MS);
  };

  const validate = () => {
    const e = {};
    if (step === 1) {
      if (form.name.trim().length < 2) e.name = "¿Cómo te llamamos?";
      if (!EMAIL_RE.test(form.email)) e.email = "Escribe un correo válido.";
    }
    if (step === 2) {
      if (form.password.length < 8) e.password = "Usa al menos 8 caracteres.";
      if (form.confirm !== form.password) e.confirm = "Las contraseñas no coinciden.";
    }
    if (step === 3) {
      if (!form.role) e.role = "Elige una opción.";
      if (!form.terms) e.terms = "Necesitamos tu aceptación para continuar.";
    }
    return e;
  };

  const next = async (ev) => {
    ev.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) return fail(errs);
    if (step < 3) return toStep(step + 1);

    setBusy(true);
    orb.setMood("thinking");
    try {
      const session = await register(form);
      orb.setMood("success");
      setSession(session);
      setTimeout(() => go("home"), 1100);
    } catch (err) {
      setBusy(false);
      // El correo ya existe: regresa al paso donde se corrige
      orb.setMood("error", { revertAfter: 1600 });
      toStep(1, { email: err.message });
    }
  };

  const back = () => (step === 1 ? go("landing") : toStep(step - 1));
  const pw = strength(form.password);

  return (
    <section className={`panel panel-${SIDE[step]}${leaving ? " is-leaving" : ""}`} key={step}>
      <div className="eyebrow rise" style={{ "--i": 0 }}>
        <Steps current={step} total={3} />
        <span className="rule" />
        Paso {step} de 3
      </div>

      {step === 1 && <h1 className="rise" style={{ "--i": 1 }}>Empecemos por tu <em>nombre</em>.</h1>}
      {step === 2 && <h1 className="rise" style={{ "--i": 1 }}>Protege tu <em>cuenta</em>.</h1>}
      {step === 3 && <h1 className="rise" style={{ "--i": 1 }}>¿Cómo usarás <em>Dudamel</em>?</h1>}

      <form key={shake} className={`form rise${shake ? " shake" : ""}`} style={{ "--i": 2 }} onSubmit={next} noValidate>
        {step === 1 && (
          <>
            <Field label="Nombre" autoComplete="name" value={form.name} onChange={set("name")} error={errors.name} autoFocus />
            <Field label="Correo" type="email" autoComplete="email" value={form.email} onChange={set("email")} error={errors.email} />
          </>
        )}

        {step === 2 && (
          <>
            <Field label="Contraseña" type="password" autoComplete="new-password" value={form.password} onChange={set("password")} error={errors.password} autoFocus />
            <div className="meter" data-level={pw} aria-label={`Seguridad: ${STRENGTH_LABEL[pw]}`}>
              {[1, 2, 3, 4].map((n) => <span key={n} className={n <= pw ? "on" : ""} />)}
              <em>{form.password ? STRENGTH_LABEL[pw] : "Mínimo 8 caracteres"}</em>
            </div>
            <Field label="Confirmar contraseña" type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} error={errors.confirm} />
          </>
        )}

        {step === 3 && (
          <>
            <div className={`chips${errors.role ? " has-error" : ""}`} role="radiogroup" aria-label="Rol">
              {ROLES.map((r) => (
                <button
                  key={r}
                  type="button"
                  role="radio"
                  aria-checked={form.role === r}
                  className={form.role === r ? "chip active" : "chip"}
                  onClick={() => { setForm((f) => ({ ...f, role: r })); orb.poke(0.5); }}
                >
                  {r}
                </button>
              ))}
            </div>
            <span className="field-msg chips-msg">{errors.role || " "}</span>
            <label className={`check${errors.terms ? " has-error" : ""}`}>
              <input type="checkbox" checked={form.terms} onChange={set("terms")} />
              <span className="box" />
              Acepto los términos de uso y el aviso de privacidad.
            </label>
            <span className="field-msg">{errors.terms || " "}</span>
          </>
        )}

        <div className="actions">
          <Button type="submit" disabled={busy}>
            {step < 3 ? "Continuar" : busy ? "Creando cuenta…" : "Crear cuenta"}
          </Button>
          <Button variant="ghost" onClick={back} disabled={busy}>Atrás</Button>
        </div>
      </form>

      <p className="switch rise" style={{ "--i": 3 }}>
        ¿Ya tienes cuenta?{" "}
        <button type="button" className="link" onClick={() => go("login")}>Inicia sesión</button>
      </p>
    </section>
  );
}
