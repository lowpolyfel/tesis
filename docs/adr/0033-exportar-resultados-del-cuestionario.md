# 0033. Exportar los resultados del cuestionario: CSV, LaTeX y PDF con gráficas

- **Fecha:** 2026-11-11
- **Estado:** Aceptada

## Contexto

El cuestionario de evaluación (ADR 0032) ya guardaba las respuestas y daba lo agregado dentro de
su propia pantalla, junto con un CSV. Para la tesis hace falta llevar esos resultados al
documento, con gráficas. Se pidió una página aparte en el menú para exportarlos en CSV, PDF o
LaTeX.

## Decisión

### Una página aparte

La página `/cuestionario/resultados` aparece en el menú de la esfera («Resultados») para quien
coordina la evaluación. También aparece en «Más», en el grupo «Evaluación con usuarios».

- **Quién coordina:** la cuenta trae `coordina_evaluacion`, que es verdadero si su correo está en
  `CUESTIONARIO_ADMINS`. Con eso la interfaz sabe si mostrar la entrada del menú; el permiso lo
  sigue exigiendo el backend (403).
- **En la pantalla del cuestionario** queda solo un acceso a esta página, para no tener los
  resultados en dos lugares.

### Las gráficas

- **SUS:** un histograma por decenas, con la media y la referencia de 68.
- **Escalas:** barras apiladas al 100 % por pregunta, en cuatro grupos: la comparación (P9–P20),
  los ítems del SUS (P25–P34), las etapas (P35–P39) y la ambigüedad (P42–P47).
- **Opciones y casillas:** barras de un solo tono.
- **Tablas:** conteos, escalas (mediana y RIC) y respuestas abiertas.

**La paleta.** Es divergente: naranja para «a mano» o «en desacuerdo», gris en el punto medio y
azul para «con DUDAMEL» o «de acuerdo».

- Se validó en claro y en oscuro con el validador de dataviz: los pares vecinos tienen ΔE ≥ 15 y
  pasan la prueba de daltonismo.
- Los dos fallos que marca el validador (luminosidad y croma del gris) son el punto medio neutro
  que pide una escala divergente.
- Como el contraste de los tonos claros es bajo, cada tramo lleva su porcentaje y su texto al
  pasar el cursor, y abajo está la tabla completa.

### Los formatos

- **CSV:** el que ya existía. Trae una fila por persona (R01, R02…) y no incluye la cuenta.
- **LaTeX:** un .zip para Overleaf (`/cuestionario/resultados/overleaf.zip`) con el mismo
  formato que los de calibración (ADR 0026):
  - `main.tex` y el estilo común;
  - figuras en pgfplots que leen sus datos de `datos/*.csv`;
  - tablas booktabs y longtable;
  - `resultados.json`.

  Compila con pdfLaTeX y con XeLaTeX; la prueba lo compila si encuentra `pdflatex`. Las
  respuestas abiertas van escapadas y sin los caracteres que pdfLaTeX no conoce, como los emojis.
- **PDF:** la misma página impresa con «Guardar como PDF». La hoja de impresión fuerza papel
  blanco y tinta oscura, oculta la esfera y la barra, conserva los colores de las gráficas y no
  separa un título de su gráfica.

### Actualización (2.8.1): para todas las cuentas

A pedido, los resultados se habilitaron para todas las cuentas. `CUESTIONARIO_ADMINS` vacío o `*`
(lo de omisión) deja ver y exportar a cualquier cuenta con sesión; una lista de correos los
limita a esos. Lo que se muestra sigue siendo anónimo, pero las respuestas abiertas quedan a la
vista de cualquier cuenta: si alguien escribe algo que lo identifique, lo verán todos.

## Alternativas consideradas

- **Generar el PDF en el servidor con LaTeX:** se descarta porque Render no trae TeX. El .zip
  compila en Overleaf y la impresión de la página sirve sin instalar nada.
- **Generar el PDF con matplotlib o reportlab:** se descarta. Serían dependencias nuevas y una
  tercera forma de dibujar las mismas gráficas.
- **Escalas centradas en el punto medio (Likert divergente):** se descarta por ahora. El 100 %
  apilado se lee igual en la pantalla y en pgfplots, y el orden de los niveles ya muestra la
  dirección.

## Consecuencias

- `resultados()` ahora incluye los puntajes SUS y los conteos ordenados (`valores`). Al estar
  ordenados no siguen el orden de envío, así que no se ligan a nadie. Los usan el histograma y el
  rango.
- La versión pasa a **2.8.0**.
