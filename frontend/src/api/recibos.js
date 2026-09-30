import { api } from "./client.js";

export const FORMAS = {
  transferencia: "Transferencia",
  efectivo: "Efectivo",
  tarjeta_credito: "Tarjeta de crédito",
  tarjeta_debito: "Tarjeta de débito",
  cheque: "Cheque",
  otro: "Otro",
};

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listarRecibos = (f) => api(`/recibos${query(f)}`);
export const totalRecibos = (f) => api(`/recibos/total${query(f)}`);
export const obtenerRecibo = (id) => api(`/recibos/${id}`);

export const crearRecibo = (cuerpo) =>
  api("/recibos", { method: "POST", body: cuerpo });

export const actualizarRecibo = (id, cuerpo) =>
  api(`/recibos/${id}`, { method: "PUT", body: cuerpo });

export const eliminarRecibo = (id) => api(`/recibos/${id}`, { method: "DELETE" });

// aplicaciones
export const listarAplicaciones = (reciboId) =>
  api(`/recibos/${reciboId}/aplicaciones`);

export const aplicarRecibo = (reciboId, cuerpo) =>
  api(`/recibos/${reciboId}/aplicaciones`, { method: "POST", body: cuerpo });

export const desaplicarRecibo = (aplicacionId) =>
  api(`/recibos/aplicaciones/${aplicacionId}`, { method: "DELETE" });

// payload helper
export const aPayload = (r) => ({
  cliente_id: Number(r.cliente_id),
  fecha: r.fecha,
  numero: r.numero,
  importe: Number(r.importe),
  forma_pago: r.forma_pago,
});