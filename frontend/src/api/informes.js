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

export const obtenerProveedores = (filtros = {}) =>
  api(`/informes/proveedores${query(filtros)}`);

export const exportarProveedores = (filtros = {}) =>
  descargar(`/informes/proveedores/export.xlsx${query(filtros)}`);

export const obtenerCentros = (filtros = {}) =>
  api(`/informes/centros-costos${query(filtros)}`);

export const exportarCentros = (filtros = {}) =>
  descargar(`/informes/centros-costos/export.xlsx${query(filtros)}`);

export const obtenerResultados = (filtros = {}) =>
  api(`/informes/resultados${query(filtros)}`);

export const exportarResultados = (filtros = {}) =>
  descargar(`/informes/resultados/export.xlsx${query(filtros)}`);

export const exportarCompras = (filtros = {}) =>
  descargar(`/compras/export.xlsx${query(filtros)}`);

export const obtenerClavesFiscales = (filtros = {}) =>
  api(`/informes/claves-fiscales${query(filtros)}`);

export const exportarClavesFiscales = (filtros = {}) =>
  descargar(`/informes/claves-fiscales/export.xlsx${query(filtros)}`);

/* La cuenta corriente de TODOS los clientes: las partidas abiertas agrupadas,
   con teléfono. Es el informe para ir a cobrar, no el detalle de una factura. */
export const obtenerCuentaCorriente = (filtros = {}) =>
  api(`/informes/cuenta-corriente${query(filtros)}`);

export const exportarCuentaCorriente = (filtros = {}) =>
  descargar(`/informes/cuenta-corriente/export.xlsx${query(filtros)}`);