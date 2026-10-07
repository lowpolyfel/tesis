# 0010. Tipo de ambigüedad, detectores de alcance y anáfora, y formalización por tipo

- **Fecha:** 2026-10-06
- **Estado:** Aceptada (los detectores son v1 y se calibran con el corpus)

## Contexto

CONTEXTO §6 pone en el núcleo tres tipos de ambigüedad: léxica, de alcance y
anafórica. Hasta ahora el sistema solo detectaba de verdad la léxica: el
Extractor separa vocabulario del dominio y no devuelve pronombres, posesivos,
cuantificadores ni coordinaciones, que es justo donde viven la anáfora y el
alcance. Además, la interfaz debe listar las ambigüedades por tipo, y una
anáfora resuelta no es vocabulario: no tiene sentido formalizar «su cuenta» como
símbolo del LEL.

## Decisión

1. **Detectores deterministas** (`app/nlp/detectores.py`) con rasgos de spaCy,
   que agregan candidatos a los filtros con decisiones nuevas `alcance` y
   `anafora` (siempre pasan al Clasificador, como `regional`):
   - anáfora: posesivo (`Poss=Yes`) o demostrativo pronominal con **dos o más**
     antecedentes posibles antes de él en la oración (el demostrativo además
     debe concordar en género y número);
   - alcance: universal + negación, universal + indefinido, partícula de foco
     (*solo*, *únicamente*), *y/o*, y coordinación mixta *y … o*.
   Buscan cobertura; el Clasificador puede marcarlos unívocos. El `detalle`
   (patrón y antecedentes) le llega al Clasificador.
2. **Tipo de ambigüedad en el contrato**: `ResultadoTermino.tipo_ambiguedad`
   (`lexica | alcance | anaforica | sintactica`), obligatorio si el término no
   es unívoco y prohibido si lo es. La vaguedad no es un tipo aquí: no produce
   interpretaciones discretas y la marca el catálogo (ADR 0003).
3. **Prompt `clasificador_v2`** con la taxonomía y el campo nuevo. `v1` se
   conserva para reproducir corridas anteriores (ADR 0001: los prompts no se
   editan, se versionan).
4. **Formalización por tipo:**
   - léxica → una entrada del LEL por término (como antes, `modelador_v1`);
   - alcance, anafórica, sintáctica → **no** entran al LEL: se resuelven en el
     requisito reescrito;
   - el requisito completo → `modelador_requisito_v1` produce el **requisito
     reescrito** con todas las interpretaciones validadas y sus **metas** (ver
     ADR 0011). Se guarda en la colección `formalizados` (un documento por
     requisito) y en un mensaje `formalizacion` con `alcance: requisito`.
5. Las trazas anteriores, sin `tipo_ambiguedad`, se tratan como léxicas.

## Alternativas consideradas

- **Pedirle al Extractor que también devuelva pronombres y cuantificadores:**
  mezcla su rol (vocabulario del dominio) con análisis estructural, y su
  cobertura dependería del LLM. Lo determinista es reproducible y explicable.
- **Formalizar todo como entrada del LEL:** llenaría el LEL de símbolos que no
  son del dominio («su», «todos los usuarios») y debilitaría R1 (ADR 0007).
- **Tipo de ambigüedad inferido en código a partir del origen:** un candidato
  del Extractor puede tener ambigüedad de alcance («usuarios inactivos»); que
  lo decida el Clasificador y se registre.

## Consecuencias

- Los detectores tienen limitaciones conocidas: no separan clíticos pegados al
  verbo («firmarlo»), no ven antecedentes posteriores (catáfora) y cuentan
  «sistema» como antecedente posible. Se miden con el corpus.
- Un mismo pronombre repetido en el requisito se agrupa en un solo candidato.
- Hay una llamada más al LLM por requisito aprobado (`modelador_requisito_v1`).
