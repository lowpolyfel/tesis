# 0018. Interfaz segmentada por proyecto y las esferas como centro

- **Fecha:** 2026-10-07
- **Estado:** Aceptada

## Contexto

La primera versión conectada al backend (ADR 0016) mostraba todo a la vez: el
menú tenía catorce destinos, cada pantalla explicaba el método en párrafos, la
traza de un requisito (fases, matrices, bitácora) era lo primero que se veía y
los nombres internos se colaban a la vista («anáfora → Clasificador»,
«aceptado directo», «pendiente de validación»). Los proyectos no tenían un lugar
claro para crear otro o cambiar de uno a otro, no había botones para regresar y
el Big Picture no se podía pedir para unos requisitos. Además, casi todo se
animaba (grano, entradas escalonadas con desenfoque, subrayados), y la esfera,
que es la identidad de Dudamel, quedaba como un emblema pequeño en una esquina.

## Decisión

1. **Todo vive dentro de un proyecto.** `/proyectos` lista los proyectos en una
   cuadrícula pareja y crea uno nuevo con su nombre y su contexto general. Un
   proyecto (`/proyectos/:id`) tiene cuatro vistas: **Requisitos** (estado de
   cada uno; se eligen varios para su mapa o su especificación),
   **Especificación** (RF/RNF reescritos, corregibles, descargables en
   Markdown), **Léxico** (el LEL, corregible) y **Mapa** (Big Picture y modelo de
   metas, de todos o de los elegidos). Analizar es `/proyectos/:id/analizar`.
2. **Lo técnico no está a la vista de primeras.** En un requisito se ve primero
   el resultado (original → versión completa, qué significado quedó para cada
   término); la traza completa por fases va plegada en «Detalles técnicos». En la
   escena en vivo se lee un paso por mensaje en una frase (`escena/pasoSimple.js`)
   y la bitácora va plegada. Ambigüedades, comparaciones, flujo, historial,
   calibración, evaluación y catálogos van en **Más**, con una línea cada uno.
3. **Lenguaje claro.** Cinco estados para la persona (en cola, analizando, por
   revisar, listo, descartado, error); los doce de la máquina siguen en la traza.
   Los tipos de ambigüedad, las vías y lo que hicieron los filtros se dicen sin
   jerga (`constants/estados.js`, `constants/agentes.js`).
4. **Siempre se puede regresar**: cada pantalla empieza con «← su padre» (no el
   historial del navegador).
5. **Las esferas son el centro.**
   - La esfera principal vive **enorme** en el margen de la sección, con su
     centro más allá del borde, y toma el color de la sección. Las secciones
     vecinas alternan de lado: al cambiar de sección la esfera cruza la pantalla
     (`components/orb/secciones.js`); en reposo deriva despacio a lo largo del
     borde.
   - **Responde a la interfaz**: al pasar por una pestaña toma su color; al pasar
     por un requisito, el de su estado.
   - **Es el menú**: tocarla (o «Menú») la lleva al centro y la divide, por
     mitosis, en una esfera por destino (`components/orb/Orbita.jsx`).
   - En la escena en vivo cada agente nace por mitosis cuando interviene (ADR
     0016), y si la validación fue automática lo acordado pasa directo al
     Modelador sin que aparezca la esfera humana.
6. **Se mueve solo lo que significa algo.** Fuera de las esferas no hay
   animaciones: el grano es fijo y las pantallas entran con un fundido corto.

## Justificación

- La persona que usa la herramienta quiere sus requisitos claros; la traza es
  para la tesis y para auditar. Separarlas permite las dos lecturas sin que una
  tape a la otra.
- La esfera ya era la metáfora del sistema (se divide en agentes). Usarla como
  navegación y como indicador de sección la vuelve funcional en vez de
  decorativa.

## Alternativas consideradas

- **Satélites permanentes como pestañas.** Se cruzaban con el contenido en
  pantallas medianas; el menú por mitosis aparece sobre un velo y no compite.
- **Mover la columna de contenido con la esfera.** Desorientaba al cambiar de
  pestaña; el contenido queda fijo al centro y la esfera ocupa el margen.

## Consecuencias

- Rutas nuevas (`/proyectos/:id/analizar`, `/mas`); las anteriores (`/inicio`,
  `/big-picture`, `/cargar`) redirigen.
- `?figura=1` sigue mostrando la traza clara a ancho fijo, para las capturas de
  la tesis.
