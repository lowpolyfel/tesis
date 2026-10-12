# 0021. Cada cuenta elige el proveedor y el modelo de cada agente

- **Fecha:** 2026-10-12
- **Estado:** Aceptada

## Contexto

Los modelos se fijaban en el `.env` del servidor: Ollama para todos los agentes y,
para el Crítico, opcionalmente Anthropic u OpenAI con una clave en el mismo archivo.
Cambiar de modelo o usar un servicio externo (Gemini, por ejemplo) exigía tocar el
servidor, y todas las cuentas usaban lo mismo.

## Decisión

1. **Configuración por cuenta** en la colección `perfiles_llm`, un documento por
   usuario: `agentes: {rol: {proveedor, modelo}}` y `proveedores: {id: {base_url,
   clave_cifrada, final}}`. Los roles son Extractor, Clasificador, Crítico, Modelador
   y Revisor (ADR 0022). Un agente sin elección usa lo del `.env`.
2. **Catálogo fijo de proveedores** (`app/llm/proveedores.py`): Ollama, Google Gemini,
   OpenAI, Anthropic, Groq, OpenRouter, DeepSeek, Mistral y «otro compatible con
   OpenAI». Cada uno dice qué pide (clave, URL), dónde se saca la clave y qué modelos
   sugiere; el modelo se escribe libre.
3. **Clientes HTTP propios** con `httpx` (ya era dependencia): el formato
   `/chat/completions` (OpenAI y los compatibles, incluido el endpoint «openai» de
   Gemini) y `/v1/messages` de Anthropic. Se pide JSON (`response_format`); si el
   servicio no lo acepta, se reintenta sin él. La validación con Pydantic y el
   reintento con el error (ADR 0001) no cambian.
4. **Las claves no salen.** Se cifran con Fernet (`CLAVE_CIFRADO`; si falta, se crea
   una en `CLAVE_CIFRADO_PATH`, fuera de git). La API solo dice si hay una y sus
   últimos cuatro caracteres. Los errores de un proveedor nunca incluyen la clave.
5. **El cliente sigue a la cuenta.** Cada agente recibe un `ClienteDinamico`. El
   servicio fija el perfil de la cuenta dueña del proyecto (`con_perfil`) antes de
   correr el grafo, y lo mismo hacen el mapa conceptual, la ficha y el triaje. La
   traza anota en `config.modelos` el proveedor y el modelo que se usaron
   (`google:gemini-2.5-flash`).
6. **La similitud (embeddings) sigue en Ollama**, para no cambiar el umbral calibrado
   (ADR 0013).
7. **La preparación** (pantalla antes de analizar) revisa los modelos de la cuenta:
   los de Ollama, que estén descargados y en memoria; los externos, que tengan clave.
   **Configuración** tiene «probar», que hace una llamada mínima con lo del formulario.

## Consecuencias

- Una cuenta puede analizar con modelos grandes en la nube, y otra en local con el
  mismo servidor. Para la tesis, cada traza dice con qué modelos se hizo.
- Con un servicio externo, los requisitos y el contexto salen de la máquina. Además,
  la misma corrida no siempre da lo mismo, aunque se fije la temperatura.
- Si varias máquinas comparten la base (Atlas), todas necesitan la misma
  `CLAVE_CIFRADO` para leer las claves guardadas.
