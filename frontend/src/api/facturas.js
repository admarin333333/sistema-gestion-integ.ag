import { api } from "./client.js";

/* Las mismas opciones que acepta el backend. */
export const TIPOS = {
  factura_a: "Factura A",
  factura_b: "Factura B",
  factura_c: "Factura C",
  nota_credito_a: "Nota de crédito A",
  nota_credito_b: "Nota de crédito B",
  nota_credito_c: "Nota de crédito C",
  nota_debito_a: "Nota de débito A",
  nota_debito_b: "Nota de débito B",
  nota_debito_c: "Nota de débito C",
};

export const CONDICIONES = {
  contado: "Contado",
  cta_corriente_15: "Cta. corriente 15 días",
  cta_corriente_30: "Cta. corriente 30 días",
};

export const ESTADOS = {
  pendiente: "Pendiente",
  parcial: "Parcialmente pagada",
  pagada: "Pagada",
  anulada: "Anulada",
};

/** Armá la parte de la URL con los filtros, dejando afuera los vacíos. */
export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listarFacturas = (f) => api(`/facturas${query(f)}`);
export const totalFacturas = (f) => api(`/facturas/total${query(f)}`);
export const obtenerFactura = (id) => api(`/facturas/${id}`);

export const crearFactura = (cuerpo) =>
  api("/facturas", { method: "POST", body: cuerpo });

export const actualizarFactura = (id, cuerpo) =>
  api(`/facturas/${id}`, { method: "PUT", body: cuerpo });

export const eliminarFactura = (id) => api(`/facturas/${id}`, { method: "DELETE" });

export const anularFactura = (id) => api(`/facturas/${id}/anular`, { method: "POST" });

export const reabrirFactura = (id) => api(`/facturas/${id}/reabrir`, { method: "POST" });

/** Manda una o varias facturas por mail. Devuelve {enviadas, avisos}. */
export const enviarFacturas = (ids) =>
  api("/facturas/enviar", { method: "POST", body: { ids } });

/** El POST y el PUT esperan los mismos campos. */
export const aPayload = (f) => ({
  cliente_id: Number(f.cliente_id),
  fecha: f.fecha,
  tipo_comprobante: f.tipo_comprobante,
  punto_venta: f.punto_venta,
  numero: f.numero,
  concepto: f.concepto ? f.concepto.trim() : null,
  importe: Number(f.importe),
  fecha_vencimiento: f.fecha_vencimiento || null,
  condicion_venta: f.condicion_venta,
  cae: f.cae ? f.cae.trim() : null,
  cae_vencimiento: f.cae_vencimiento || null,
});
