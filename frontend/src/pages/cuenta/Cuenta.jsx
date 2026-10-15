import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router";
import { useOrb } from "../../components/orb/useOrb";
import { poseFor } from "../../components/orb/poses";
import { destinoSeguro, useSesion } from "../../components/sesion";
import { BotonTema } from "../../components/tema";
import {
  CONTRASENA_MIN,
  entrar,
  pedirRestablecer,
  reenviarCodigo,
  registrarCuenta,
  restablecerContrasena,
  verificarCodigo,
} from "../../services/backend";
import "../intro/intro.css";
import "./cuenta.css";

/*
 * Cuentas: entrar, crear cuenta, escribir el código que llega por correo y
 * restablecer la contraseña. Mismo escenario que la portada: el texto a la
 * izquierda y la esfera a la derecha, que escucha mientras se escribe.
 *
 *   /entrar?volver=     correo y contraseña
 *   /registro           nombre, correo y contraseña → código
 *   /verificar?correo=&para=registro|entrar&volver=   el código de 6 dígitos
 *   /recuperar          correo → código y contraseña nueva
 */

function Marco({ indice, eyebrow, titulo, children }) {
  const orb = useOrb();
  useEffect(() => {
    const colocar = () => orb.setPose(poseFor("landing"));
    colocar();
    orb.setMood("idle");
    orb.setShy(false);
    addEventListener("resize", colocar);
    return () => removeEventListener("resize", colocar);
  }, [orb]);

  return (
    <div className="app cuenta">
      <header className="topbar">
        <Link to="/" className="brand" aria-label="Dudamel, ir a la portada"><span className="dot" />Dudamel</Link>
        <BotonTema className="pointer-events-auto" />
      </header>
      <main className="page page-cuenta">
        <section className="panel panel-left">
          <div className="eyebrow rise" style={{ "--i": 0 }}>
            <span className="idx">{indice}</span><span className="rule" />{eyebrow}
          </div>
          <h1 className="rise" style={{ "--i": 1 }}>{titulo}</h1>
          {children}
        </section>
      </main>
    </div>
  );
}

function Campo({ etiqueta, error, nota, ...props }) {
  const orb = useOrb();
  return (
    <label className={`field${error ? " has-error" : ""}`}>
      <span className="field-label">{etiqueta}</span>
      <input {...props} onFocus={() => orb.setMood("listening", { ambiente: false })} onBlur={() => orb.setMood("idle", { ambiente: false })} />
      <span className="field-msg">{error || nota || ""}</span>
    </label>
  );
}

/* Envío con aviso de error, sacudida del formulario y reacción de la esfera */
function useEnvio() {
  const orb = useOrb();
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [sacude, setSacude] = useState(0);
  const enviar = async (accion) => {
    setEnviando(true);
    setError(null);
    try {
      const r = await accion();
      orb.setMood("success", { revertAfter: 900 });
      return r;
    } catch (e) {
      setError(e);
      setSacude((n) => n + 1);
      orb.setMood("error", { revertAfter: 900 });
      return undefined;
    } finally {
      setEnviando(false);
    }
  };
  return { error, setError, enviando, sacude, enviar };
}

function ErrorFormulario({ error }) {
  return <p className="form-error" role="alert">{error ? error.message : ""}</p>;
}

/* ------------------------------------------------------------------ entrar */

export function Entrar() {
  const { usuario, iniciar } = useSesion();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const volver = destinoSeguro(params.get("volver"));
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const { error, enviando, sacude, enviar } = useEnvio();

  if (usuario) return <Navigate to={volver} replace />;

  const alEnviar = async (e) => {
    e.preventDefault();
    const r = await enviar(async () => {
      try {
        return await entrar(correo, contrasena);
      } catch (err) {
        if (err.detalle?.codigo === "sin_verificar") return { pendiente: "registro", correo };
        throw err;
      }
    });
    if (!r) return;
    if (r.pendiente) {
      navigate(`/verificar?${new URLSearchParams({ correo: r.correo ?? correo, para: r.pendiente, volver })}`,
        { state: { sinSmtp: r.sin_smtp, minutos: r.minutos } });
    } else {
      iniciar(r);
      navigate(volver, { replace: true });
    }
  };

  return (
    <Marco indice="01" eyebrow="Tu cuenta" titulo={<>Bienvenido <em>de vuelta</em>.</>}>
      <form key={sacude} onSubmit={alEnviar} className={`form ${sacude ? "shake" : "rise"}`} style={{ "--i": 2 }}>
        <Campo etiqueta="Correo" type="email" autoComplete="email" required value={correo} onChange={(e) => setCorreo(e.target.value)} autoFocus />
        <Campo etiqueta="Contraseña" type="password" autoComplete="current-password" required value={contrasena} onChange={(e) => setContrasena(e.target.value)} />
        <ErrorFormulario error={error} />
        <div className="actions">
          <button className="btn btn-primary" disabled={enviando || !correo || !contrasena}>{enviando ? "Entrando…" : "Entrar"}</button>
          <Link className="btn btn-ghost" to="/registro">Crear cuenta</Link>
        </div>
      </form>
      <p className="switch rise" style={{ "--i": 3 }}>
        <Link className="link" to="/recuperar">¿Olvidaste tu contraseña?</Link>
      </p>
    </Marco>
  );
}

/* ------------------------------------------------------------------ registro */

/* Fuerza aproximada, solo como guía: el backend exige el mínimo de largo */
function fuerza(c) {
  if (!c) return 0;
  let n = c.length >= CONTRASENA_MIN ? 1 : 0;
  if (c.length >= 12) n++;
  if (/[a-z]/.test(c) && /[A-Z]/.test(c)) n++;
  if (/\d/.test(c) && /[^A-Za-z0-9]/.test(c)) n++;
  return n;
}
const NIVELES = ["muy corta", "débil", "aceptable", "buena", "fuerte"];

export function Registro() {
  const { usuario } = useSesion();
  const navigate = useNavigate();
  const [f, setF] = useState({ nombre: "", correo: "", contrasena: "", repetir: "" });
  const { error, enviando, sacude, enviar } = useEnvio();
  const cambia = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const corta = f.contrasena.length > 0 && f.contrasena.length < CONTRASENA_MIN;
  const distinta = f.repetir.length > 0 && f.repetir !== f.contrasena;
  const nivel = fuerza(f.contrasena);

  if (usuario) return <Navigate to="/proyectos" replace />;

  const alEnviar = async (e) => {
    e.preventDefault();
    if (corta || distinta) return;
    const r = await enviar(() => registrarCuenta(f));
    if (r) navigate(`/verificar?${new URLSearchParams({ correo: r.correo, para: "registro" })}`, { state: { sinSmtp: r.sin_smtp, minutos: r.minutos } });
  };

  return (
    <Marco indice="01" eyebrow="Cuenta nueva" titulo={<>Crea tu <em>cuenta</em>.</>}>
      <p className="lead rise" style={{ "--i": 2 }}>Te mandaremos un código a tu correo para confirmarlo. Tus proyectos y requisitos se guardan en tu cuenta.</p>
      <form key={sacude} onSubmit={alEnviar} className={`form ${sacude ? "shake" : "rise"}`} style={{ "--i": 3 }}>
        <Campo etiqueta="Nombre" autoComplete="name" required maxLength={80} value={f.nombre} onChange={cambia("nombre")} autoFocus />
        <Campo etiqueta="Correo" type="email" autoComplete="email" required value={f.correo} onChange={cambia("correo")} />
        <Campo etiqueta="Contraseña" type="password" autoComplete="new-password" required maxLength={128} value={f.contrasena} onChange={cambia("contrasena")}
          error={corta ? `Al menos ${CONTRASENA_MIN} caracteres.` : null} />
        <div className="meter" aria-hidden="true">
          {[1, 2, 3, 4].map((i) => <span key={i} className={nivel >= i ? "on" : ""} />)}
          <em>{f.contrasena ? NIVELES[nivel] : ""}</em>
        </div>
        <Campo etiqueta="Repite la contraseña" type="password" autoComplete="new-password" required value={f.repetir} onChange={cambia("repetir")}
          error={distinta ? "No coincide." : null} />
        <ErrorFormulario error={error} />
        <div className="actions">
          <button className="btn btn-primary" disabled={enviando || !f.nombre.trim() || !f.correo || corta || distinta || !f.repetir}>
            {enviando ? "Creando…" : "Crear cuenta"}
          </button>
        </div>
      </form>
      <p className="switch rise" style={{ "--i": 4 }}>¿Ya tienes cuenta? <Link className="link" to="/entrar">Entra</Link></p>
    </Marco>
  );
}

/* ------------------------------------------------------------------ código */

function AvisoCodigo({ correo, sinSmtp, minutos }) {
  return (
    <>
      <p className="lead rise" style={{ "--i": 2 }}>
        Te enviamos un código de 6 dígitos a <b className="font-medium text-[var(--bone)]">{correo}</b>{minutos ? `. Vence en ${minutos} minutos.` : "."}
      </p>
      {sinSmtp && (
        <p className="nota-dev rise" style={{ "--i": 2 }}>
          El backend no tiene correo configurado (SMTP_HOST): el código está en la consola donde corre uvicorn.
        </p>
      )}
    </>
  );
}

function CampoCodigo({ valor, onCambio }) {
  return (
    <Campo etiqueta="Código" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required
      className="codigo" value={valor} onChange={(e) => onCambio(e.target.value.replace(/\D/g, "").slice(0, 6))} autoFocus />
  );
}

/* «Reenviar código» con la espera que pide el backend */
function Reenviar({ correo }) {
  const [espera, setEspera] = useState(0);
  const [aviso, setAviso] = useState(null);
  const reloj = useRef();
  useEffect(() => () => clearInterval(reloj.current), []);
  const contar = (s) => {
    setEspera(s);
    clearInterval(reloj.current);
    reloj.current = setInterval(() => setEspera((x) => { if (x <= 1) clearInterval(reloj.current); return Math.max(0, x - 1); }), 1000);
  };
  const reenviar = async () => {
    setAviso(null);
    try {
      await reenviarCodigo(correo);
      setAviso("Listo: revisa tu correo.");
      contar(60);
    } catch (e) {
      if (e.detalle?.segundos) contar(e.detalle.segundos);
      else setAviso(e.message);
    }
  };
  return (
    <p className="switch rise" style={{ "--i": 4 }}>
      ¿No llegó?{" "}
      <button type="button" className="link" onClick={reenviar} disabled={espera > 0}>
        {espera > 0 ? `Reenviar en ${espera} s` : "Reenviar código"}
      </button>
      {aviso && <span className="ml-3">{aviso}</span>}
    </p>
  );
}

export function Verificar() {
  const { iniciar } = useSesion();
  const navigate = useNavigate();
  const { state } = useLocation();
  const [params] = useSearchParams();
  const correo = params.get("correo") ?? "";
  const para = params.get("para") === "entrar" ? "entrar" : "registro";
  const [codigo, setCodigo] = useState("");
  const { error, enviando, sacude, enviar } = useEnvio();

  if (!correo) return <Navigate to="/entrar" replace />;

  const alEnviar = async (e) => {
    e.preventDefault();
    const u = await enviar(() => verificarCodigo(correo, codigo));
    if (u) {
      iniciar(u);
      navigate(destinoSeguro(params.get("volver")), { replace: true });
    }
  };

  return (
    <Marco indice="02" eyebrow={para === "entrar" ? "Código de seguridad" : "Confirma tu correo"} titulo={<>Revisa tu <em>correo</em>.</>}>
      <AvisoCodigo correo={correo} sinSmtp={state?.sinSmtp} minutos={state?.minutos} />
      <form key={sacude} onSubmit={alEnviar} className={`form ${sacude ? "shake" : "rise"}`} style={{ "--i": 3 }}>
        <CampoCodigo valor={codigo} onCambio={setCodigo} />
        <ErrorFormulario error={error} />
        <div className="actions">
          <button className="btn btn-primary" disabled={enviando || codigo.length !== 6}>{enviando ? "Comprobando…" : "Confirmar"}</button>
          <Link className="btn btn-ghost" to="/entrar">Volver</Link>
        </div>
      </form>
      <Reenviar correo={correo} />
    </Marco>
  );
}

/* ------------------------------------------------------------------ restablecer */

export function Recuperar() {
  const { iniciar } = useSesion();
  const navigate = useNavigate();
  const [correo, setCorreo] = useState("");
  const [pendiente, setPendiente] = useState(null); // respuesta de /auth/recuperar
  const [f, setF] = useState({ codigo: "", contrasena: "", repetir: "" });
  const { error, enviando, sacude, enviar } = useEnvio();
  const corta = f.contrasena.length > 0 && f.contrasena.length < CONTRASENA_MIN;
  const distinta = f.repetir.length > 0 && f.repetir !== f.contrasena;

  const pedir = async (e) => {
    e.preventDefault();
    const r = await enviar(() => pedirRestablecer(correo));
    if (r) setPendiente(r);
  };
  const cambiar = async (e) => {
    e.preventDefault();
    if (corta || distinta) return;
    const u = await enviar(() => restablecerContrasena({ correo: pendiente.correo, codigo: f.codigo, contrasena: f.contrasena }));
    if (u) {
      iniciar(u);
      navigate("/proyectos", { replace: true });
    }
  };

  if (!pendiente) {
    return (
      <Marco indice="01" eyebrow="Restablecer" titulo={<>¿Olvidaste tu <em>contraseña</em>?</>}>
        <p className="lead rise" style={{ "--i": 2 }}>Escribe el correo de tu cuenta y te mandaremos un código para elegir otra.</p>
        <form key={sacude} onSubmit={pedir} className={`form ${sacude ? "shake" : "rise"}`} style={{ "--i": 3 }}>
          <Campo etiqueta="Correo" type="email" autoComplete="email" required value={correo} onChange={(e) => setCorreo(e.target.value)} autoFocus />
          <ErrorFormulario error={error} />
          <div className="actions">
            <button className="btn btn-primary" disabled={enviando || !correo}>{enviando ? "Enviando…" : "Enviar código"}</button>
            <Link className="btn btn-ghost" to="/entrar">Volver</Link>
          </div>
        </form>
      </Marco>
    );
  }
  return (
    <Marco indice="02" eyebrow="Restablecer" titulo={<>Elige otra <em>contraseña</em>.</>}>
      <AvisoCodigo correo={pendiente.correo} sinSmtp={pendiente.sin_smtp} minutos={pendiente.minutos} />
      <form key={sacude} onSubmit={cambiar} className={`form ${sacude ? "shake" : "rise"}`} style={{ "--i": 3 }}>
        <CampoCodigo valor={f.codigo} onCambio={(codigo) => setF((x) => ({ ...x, codigo }))} />
        <Campo etiqueta="Contraseña nueva" type="password" autoComplete="new-password" required maxLength={128} value={f.contrasena}
          onChange={(e) => setF((x) => ({ ...x, contrasena: e.target.value }))} error={corta ? `Al menos ${CONTRASENA_MIN} caracteres.` : null} />
        <Campo etiqueta="Repite la contraseña" type="password" autoComplete="new-password" required value={f.repetir}
          onChange={(e) => setF((x) => ({ ...x, repetir: e.target.value }))} error={distinta ? "No coincide." : null} />
        <ErrorFormulario error={error} />
        <div className="actions">
          <button className="btn btn-primary" disabled={enviando || f.codigo.length !== 6 || corta || distinta || !f.repetir}>
            {enviando ? "Guardando…" : "Guardar y entrar"}
          </button>
        </div>
      </form>
      <Reenviar correo={pendiente.correo} />
    </Marco>
  );
}
