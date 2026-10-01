import { api, descargar } from "./client.js";

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const obtenerEstadoDeuda = (filtros = {}) =>
  api(`/informes/estado-deuda${query(filtros)}`);

export const exportarEstadoDeuda = (filtros = {}) =>
  descargar(`/informes/estado-deuda/export.xlsx${query(filtros)}`);

export const obtenerAnticiposPendientes = (filtros = {}) =>
  api(`/informes/anticipos-pendientes${query(filtros)}`);

export const exportarAnticiposPendientes = (filtros = {}) =>
  descargar(`/informes/anticipos-pendientes/export.xlsx${query(filtros)}`);