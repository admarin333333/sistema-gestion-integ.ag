import { api, descargar } from "./client.js";

export const ESTADOS = {
  disponible: "Disponible",
  parcial: "Parcial",
  aplicado: "Aplicado",
  eliminado: "Eliminado",
};

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listarAnticipos = (f) => api(`/anticipos${query(f)}`);
export const obtenerAnticipo = (id) => api(`/anticipos/${id}`);
export const crearAnticipo = (cuerpo) => api("/anticipos", { method: "POST", body: cuerpo });
export const actualizarAnticipo = (id, cuerpo) => api(`/anticipos/${id}`, { method: "PUT", body: cuerpo });
export const eliminarAnticipo = (id) => api(`/anticipos/${id}`, { method: "DELETE" });

// aplicaciones (imputaciones a facturas)
export const listarAplicaciones = (anticipoId) => api(`/anticipos/${anticipoId}/aplicaciones`);
export const aplicarAnticipo = (anticipoId, cuerpo) =>
  api(`/anticipos/${anticipoId}/aplicaciones`, { method: "POST", body: cuerpo });
export const desaplicarAnticipo = (aplicacionId) =>
  api(`/anticipos/aplicaciones/${aplicacionId}`, { method: "DELETE" });

// informes
export const exportarExcel = (filtros) => descargar(`/anticipos/informe.xlsx${query(filtros)}`);
export const exportarPdf = (filtros) => descargar(`/anticipos/informe.pdf${query(filtros)}`);

// payload helper
export const aPayload = (a) => ({
  cliente_id: Number(a.cliente_id),
  fecha: a.fecha,
  numero: a.numero,
  importe: Number(a.importe),
});