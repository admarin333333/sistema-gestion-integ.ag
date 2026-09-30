import { api, descargar } from "./client.js";

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const obtenerCuentaCorriente = (clienteId, filtros = {}) =>
  api(`/clientes/${clienteId}/cuenta-corriente${query(filtros)}`);

export const exportarCuentaCorriente = (clienteId, filtros = {}) =>
  descargar(`/clientes/${clienteId}/cuenta-corriente/export.xlsx${query(filtros)}`);