import { api } from "./client.js";

/* Los asientos van agrupados por día: el backend los agrupa y suma. Acá no se
 * cuenta nada, se pinta lo que viene. */
export const listarAsientos = (f = {}) => {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return api(`/asientos${s ? `?${s}` : ""}`);
};

export const obtenerAsiento = (id) => api(`/asientos/${id}`);

/** Asiento manual. El comprobante se numera solo con el código que va acá. */
export const crearAsiento = (cuerpo) =>
  api("/asientos", { method: "POST", body: cuerpo });

/** Reemplaza las líneas y deja el asiento contabilizado. */
export const guardarAsiento = (id, detalle) =>
  api(`/asientos/${id}`, { method: "PUT", body: { detalle } });

export const contabilizarAsiento = (id) =>
  api(`/asientos/${id}/contabilizar`, { method: "POST" });

export const aBorradorAsiento = (id) =>
  api(`/asientos/${id}/borrador`, { method: "POST" });

export const anularAsiento = (id) =>
  api(`/asientos/${id}/anular`, { method: "POST" });

/** Los códigos internos dados de alta (FV, RC, AB, OP…). */
export const listarCodigos = () => api("/comprobantes-internos/codigos");

/** Buscador de cuentas para las líneas. Solo devuelve las imputables. */
export const buscarCuentas = (q) =>
  api(`/plan-cuentas/buscar${q ? `?q=${encodeURIComponent(q)}` : ""}`);

/** El mayor de UNA cuenta: sus movimientos con el saldo acumulado. */
export const listarMayor = (idCuenta, f = {}) => {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return api(`/mayores/${idCuenta}${s ? `?${s}` : ""}`);
};

/** Los saldos de todas las cuentas, para elegir cuál abrir como mayor. */
export const listarSaldos = (f = {}) => {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return api(`/saldos${s ? `?${s}` : ""}`);
};

/* --- Configuración: qué cuenta va en cada asiento ------------------------
 *
 * Esto es lo que hace que cambiar "Documentos a cobrar" por "Clientes" sea un
 * cambio de DATOS y no de código. Si un día el contador decide otra cosa, se
 * corrige acá, no se toca el programa.
 */

/** Las filas de config_asientos con el código y nombre de cada cuenta. */
export const listarConfigAsientos = () => api("/config-asientos");

/** Cambia las CUENTAS de un caso. Solo el admin. */
export const guardarConfigAsiento = (clave, cuentas) =>
  api(`/config-asientos/${clave}`, { method: "PUT", body: cuentas });

/** Los códigos internos (FV, NC, ND, RC…) con cuántos hay emitidos de cada uno. */
export const listarConfigComprobantes = () => api("/config-comprobantes");

/** Cambia el nombre o activa/desactiva un código interno. Solo el admin. */
export const guardarConfigComprobante = (codigo, datos) =>
  api(`/config-comprobantes/${codigo}`, { method: "PUT", body: datos });