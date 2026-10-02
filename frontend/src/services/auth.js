/*
 * Autenticación simulada en el navegador (localStorage) mientras no existe
 * el backend. Misma forma de promesas que tendrá el cliente HTTP real.
 */
const USERS_KEY = "dudamel.users";
const SESSION_KEY = "dudamel.session";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const read = (k, fallback) => {
  try { return JSON.parse(localStorage.getItem(k)) ?? fallback; } catch { return fallback; }
};
const write = (k, v) => {
  try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* almacenamiento no disponible */ }
};

async function hash(text) {
  if (!crypto?.subtle) return text; // contexto no seguro (p. ej. abierto como archivo)
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function register({ name, email, password, role }) {
  await wait(1300);
  const users = read(USERS_KEY, {});
  const key = email.trim().toLowerCase();
  if (users[key]) throw new Error("Ya existe una cuenta con ese correo.");
  users[key] = { name: name.trim(), email: key, role, pass: await hash(password) };
  write(USERS_KEY, users);
  const session = { name: users[key].name, email: key };
  write(SESSION_KEY, session);
  return session;
}

export async function login({ email, password }) {
  await wait(1200);
  const user = read(USERS_KEY, {})[email.trim().toLowerCase()];
  if (!user || user.pass !== (await hash(password))) throw new Error("Correo o contraseña incorrectos.");
  const session = { name: user.name, email: user.email };
  write(SESSION_KEY, session);
  return session;
}

export function currentSession() {
  return read(SESSION_KEY, null);
}

export function logout() {
  try { localStorage.removeItem(SESSION_KEY); } catch { /* nada que borrar */ }
}
