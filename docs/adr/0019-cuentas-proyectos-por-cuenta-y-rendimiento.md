# 0019. Cuentas con código por correo, proyectos por cuenta, borrar, tema claro y una interfaz más ligera

- **Fecha:** 2026-10-12
- **Estado:** Aceptada

## Contexto

El prototipo era de un solo usuario en una sola máquina: no había cuentas, el
backend creaba solo un proyecto `P00 General` y la carga ofrecía un texto de
ejemplo. Con la base en MongoDB Atlas varias personas pueden usar el mismo
backend, y cada una debe ver solo lo suyo. Además, los proyectos y requisitos no
se podían borrar, y la interfaz se sentía lenta: la esfera animada se volvía a
pintar entera en cada cuadro.

## Decisión

1. **Cuentas** (`app/auth`, rutas `/auth/*`). Registro con nombre, correo y
   contraseña. La cuenta queda sin verificar hasta escribir un código de 6
   dígitos que llega por correo. Si se olvida la contraseña, otro código permite
   elegir una nueva. Con `AUTH_CODIGO_AL_ENTRAR=true` también se pide un código
   cada vez que se entra.
   - Contraseñas con scrypt (biblioteca estándar, parámetros de OWASP). Los
     códigos y tokens se guardan como sha256, nunca en claro.
   - Los códigos vencen (`CODIGO_MINUTOS`), admiten pocos intentos
     (`CODIGO_INTENTOS`) y no se reenvían antes de `CODIGO_REENVIO_S`. Tras
     varias contraseñas incorrectas seguidas, la cuenta se bloquea unos minutos.
   - La sesión es una cookie HttpOnly y SameSite=Lax (`dudamel_sesion`) con
     `<usuario_id>.<token>`. El frontend no ve el token y `EventSource` la manda
     sola. «Salir» borra esa sesión en el servidor; restablecer la contraseña
     borra todas.
   - El correo sale por SMTP (`SMTP_*`). Sin `SMTP_HOST` (desarrollo) no se
     envía: el backend escribe el código en su consola y la pantalla lo avisa.
2. **Todo pide sesión** salvo `/auth/*` y `/salud`. **Cada proyecto es de una
   cuenta** (`Proyecto.propietario`). Lo de otra cuenta responde 404, igual que
   lo que no existe: proyectos, requisitos, eventos, documentos, comparaciones,
   evaluaciones y LEL. Los listados (`/proyectos`, `/trazas`, `/lel`, `/cola`,
   `/calibracion`, `/evaluaciones`) muestran solo lo de la cuenta. La cola sigue
   siendo una sola para todos (`de_otras_cuentas` cuenta los trabajos ajenos).
3. **Nada se crea solo.** La API ya no crea `P00 General`, `/procesar` exige un
   `proyecto_id` de la cuenta y se quitó el texto de ejemplo de la carga. Una
   cuenta nueva empieza sin proyectos. `Proyectos.asegurar_general()` queda solo
   para scripts y pruebas.
4. **Borrar.** `DELETE /proyectos/{id}` borra el proyecto con sus requisitos, su
   LEL, documentos, comparaciones, evaluaciones y formalizados.
   `DELETE /requisitos/{id}` borra la traza, las entradas del LEL que salieron de
   ella, su documento formalizado, una validación en espera y el checkpoint de su
   grafo. Si algo se está analizando o espera turno, responde 409.
5. **Tema claro** además del oscuro (`<html data-tema>`, guardado en el
   navegador). Los colores salen de variables CSS y la esfera pinta el fondo
   según el tema.
6. **Animación más ligera.**
   - Lo que cambia en cada cuadro solo toca `transform` y `opacity`.
   - Se quitaron los `backdrop-filter` de tarjetas, pestañas y botones, los
     filtros SVG de las ondas, la máscara y los modos de mezcla de la esfera y
     de la niebla, la animación del `border-radius` y la inclinación 3D.
   - Las variables de color de la raíz se escriben a 30 Hz.
   - Las entradas duran la mitad y no animan desenfoque.
   - La escena en vivo arranca a 2×.

## Justificación

- **Cookie HttpOnly, no un token en `localStorage`.** Un script de terceros no
  puede leerla. Además el SSE (`EventSource`) no permite cabeceras propias, y la
  cookie viaja sola. SameSite=Lax y CORS con lista de orígenes cierran el paso a
  peticiones desde otros sitios.
- **404 y no 403** para lo ajeno: no se revela qué ids existen en otras cuentas.
- **Borrar también el checkpoint.** Los ids se vuelven a usar (`max + 1`). Si
  quedara el checkpoint, un requisito nuevo con el mismo id heredaría el estado
  del grafo anterior.
- **Por qué esos efectos.** El hilo principal no era el cuello de botella: en
  Chromium sin GPU pasaba del 4 al 8 % del tiempo trabajando. Lo caro era
  repintar áreas grandes en cada cuadro: el desenfoque detrás de cada tarjeta
  mientras la esfera se movía y los filtros sobre una SVG escalada hasta 2.6×.
  Con el mismo navegador, las pantallas de herramientas pasaron de ~10 a 60
  cuadros por segundo, y la portada de ~19 a 60.

## Alternativas consideradas

- **JWT sin estado:** no se puede cerrar una sesión antes de que venza sin una
  lista de revocación, que es lo mismo que guardar sesiones.
- **Proyectos compartidos entre todas las cuentas:** más simple, pero una cuenta
  vería y borraría lo de otra.
- **Asignar a la primera cuenta los proyectos sin dueño:** magia implícita. Los
  proyectos anteriores a las cuentas quedan sin dueño y nadie los ve; la base de
  Atlas empezó vacía.
- **Bajar la calidad de la esfera según el equipo:** más código y más difícil de
  reproducir. Quitar lo caro bastó.

## Consecuencias

- Para que el correo salga de verdad hay que configurar SMTP en el `.env` de la
  raíz. En Gmail: `smtp.gmail.com`, puerto 587, `starttls` y una contraseña de
  aplicación.
- En HTTPS, `SESION_COOKIE_SEGURA=true`.
- Las pruebas de la API responden como una cuenta de prueba
  (`tests/fakes.py: como_usuario`). Las de `tests/auth` prueban la sesión de
  verdad.
- Los proyectos y trazas creados antes de esta versión no son de ninguna cuenta
  y no aparecen.
