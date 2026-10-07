import { hexToOklab } from "./color";

/* Estados de ánimo del orbe. Todo se interpola cuadro a cuadro. */
export const MOODS = {
  idle: {
    c1: "#7482ff", c2: "#bc6dff", bg: "#0a0908",
    scale: 1, fog: 1, glow: 0.5,
    amp: 1, speed: 1, turbulence: 0, pulse: 0, breathe: 0.03, wobble: 0,
  },
  thinking: {
    c1: "#ffd44f", c2: "#ff8f31", bg: "#0d0902",
    scale: 0.92, fog: 1.22, glow: 0.62,
    amp: 1.45, speed: 1.9, turbulence: 0.35, pulse: 0, breathe: 0.045, wobble: 0,
  },
  listening: {
    c1: "#41efff", c2: "#2d87ff", bg: "#02090e",
    scale: 1.02, fog: 1.14, glow: 0.58,
    amp: 1.2, speed: 1.4, turbulence: 0.12, pulse: 1, breathe: 0.03, wobble: 0,
  },
  success: {
    c1: "#57f7a7", c2: "#00cb89", bg: "#020b07",
    scale: 1.1, fog: 1.05, glow: 0.56,
    amp: 0.75, speed: 0.8, turbulence: 0, pulse: 0, breathe: 0.025, wobble: 0,
  },
  error: {
    c1: "#ff5265", c2: "#ff1f1f", bg: "#100204",
    scale: 1.04, fog: 1.25, glow: 0.68,
    amp: 1.6, speed: 2.3, turbulence: 0.7, pulse: 0, breathe: 0.02, wobble: 1,
  },
  /* ---- un tono por agente, para cuando la esfera se divide ---- */
  extractor: {
    c1: "#41efff", c2: "#2d87ff", bg: "#02090e",
    scale: 1, fog: 1.1, glow: 0.55,
    amp: 1.1, speed: 1.2, turbulence: 0.08, pulse: 0.6, breathe: 0.03, wobble: 0,
  },
  clasificador: {
    c1: "#8f8bff", c2: "#c46dff", bg: "#0a0812",
    scale: 1, fog: 1.1, glow: 0.55,
    amp: 1.1, speed: 1.2, turbulence: 0.1, pulse: 0, breathe: 0.035, wobble: 0,
  },
  critico: {
    c1: "#ffd44f", c2: "#ff8f31", bg: "#0d0902",
    scale: 1, fog: 1.15, glow: 0.6,
    amp: 1.2, speed: 1.4, turbulence: 0.2, pulse: 0, breathe: 0.04, wobble: 0,
  },
  modelador: {
    c1: "#57f7a7", c2: "#00cb89", bg: "#020b07",
    scale: 1, fog: 1.05, glow: 0.55,
    amp: 0.9, speed: 1, turbulence: 0, pulse: 0, breathe: 0.03, wobble: 0,
  },
  /* ---- nodos que no son agentes LLM: filtros, divergencia, humano, sistema ---- */
  filtros: {
    c1: "#7dd3fc", c2: "#38bdf8", bg: "#02080d",
    scale: 1, fog: 1.05, glow: 0.5,
    amp: 0.8, speed: 0.9, turbulence: 0, pulse: 0.4, breathe: 0.025, wobble: 0,
  },
  divergencia: {
    c1: "#f8fafc", c2: "#94a3b8", bg: "#07080a",
    scale: 1, fog: 1.05, glow: 0.62,
    amp: 0.9, speed: 1.1, turbulence: 0.05, pulse: 0.8, breathe: 0.03, wobble: 0,
  },
  humano: {
    c1: "#f9a8d4", c2: "#ec4899", bg: "#0e0309",
    scale: 1, fog: 1.08, glow: 0.58,
    amp: 1, speed: 0.9, turbulence: 0.05, pulse: 0.5, breathe: 0.04, wobble: 0,
  },
  sistema: {
    c1: "#cbd5e1", c2: "#64748b", bg: "#06070a",
    scale: 1, fog: 1, glow: 0.45,
    amp: 0.7, speed: 0.8, turbulence: 0, pulse: 0, breathe: 0.02, wobble: 0,
  },
  /* ---- interpretaciones I1…I6 (mismos colores que colorInterpretacion) ---- */
  interp1: { c1: "#7dd3fc", c2: "#0ea5e9", bg: "#030812", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  interp2: { c1: "#fcd34d", c2: "#f59e0b", bg: "#100602", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  interp3: { c1: "#c4b5fd", c2: "#8b5cf6", bg: "#0a0612", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  interp4: { c1: "#6ee7b7", c2: "#10b981", bg: "#020b07", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  interp5: { c1: "#f9a8d4", c2: "#ec4899", bg: "#0e0309", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  interp6: { c1: "#fda4af", c2: "#f43f5e", bg: "#100205", scale: 1, fog: 1.1, glow: 0.6, amp: 1.3, speed: 1.6, turbulence: 0.25, pulse: 0, breathe: 0.04, wobble: 0 },
  lecturaA: {
    c1: "#5cc8ff", c2: "#3b82f6", bg: "#030812",
    scale: 1, fog: 1.1, glow: 0.6,
    amp: 1.4, speed: 1.7, turbulence: 0.3, pulse: 0, breathe: 0.04, wobble: 0,
  },
  lecturaB: {
    c1: "#ffb347", c2: "#ff6a3d", bg: "#100602",
    scale: 1, fog: 1.1, glow: 0.6,
    amp: 1.4, speed: 1.7, turbulence: 0.3, pulse: 0, breathe: 0.04, wobble: 0,
  },
};

export const NUM_KEYS = ["scale", "fog", "glow", "amp", "speed", "turbulence", "pulse", "breathe", "wobble"];
export const COLOR_KEYS = ["c1", "c2", "bg"];

export const MOODS_LAB = Object.fromEntries(
  Object.entries(MOODS).map(([k, p]) => [k, Object.fromEntries(COLOR_KEYS.map((c) => [c, hexToOklab(p[c])]))])
);
