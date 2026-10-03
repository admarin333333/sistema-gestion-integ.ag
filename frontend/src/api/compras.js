import { api } from "./client.js";
import { descargar } from "./client.js";

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

export const ESTADOS = {
  pendiente: "Pendiente",
  anulada: "Anulada",
};

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listarCompras = (f) => api(`/compras${query(f)}`);
export const totalCompras = (f) => api(`/compras/total${query(f)}`);
export const obtenerCompra = (id) => api(`/compras/${id}`);

export const crearCompra = (cuerpo) =>
  api("/compras", { method: "POST", body: cuerpo });

export const actualizarCompra = (id, cuerpo) =>
  api(`/compras/${id}`, { method: "PUT", body: cuerpo });

export const eliminarCompra = (id) => api(`/compras/${id}`, { method: "DELETE" });

export const anularCompra = (id) => api(`/compras/${id}/anular`, { method: "POST" });

export const reabrirCompra = (id) => api(`/compras/${id}/reabrir`, { method: "POST" });

/** Los centros y sus cuentas de gasto, SIN importes. */
export const listarCentrosCuentas = () => api("/informes/centros-cuentas");

/**
 * El asiento que VA a quedar, sin guardar nada. Usa la misma función del
 * backend que el asiento real, así que lo que se muestra es lo que se guarda.
 */
export const previewAsientoCompra = (cuerpo) =>
  api("/compras/preview-asiento", { method: "POST", body: cuerpo });

export const generarAsientoCompra = (id) =>
  api(`/compras/${id}/asiento`, { method: "POST" });

export const anularAsientoCompra = (id) =>
  api(`/compras/${id}/asiento/anular`, { method: "POST" });

export const exportarExcel = (filtros) =>
  descargar(`/compras/export.xlsx${query(filtros)}`);

/** El POST y el PUT esperan los mismos campos (IVA y total los calcula el backend). */
export const aPayload = (c) => ({
  proveedor_id: Number(c.proveedor_id),
  fecha: c.fecha,
  tipo_comprobante: c.tipo_comprobante,
  punto_venta: c.punto_venta,
  numero: c.numero,
  concepto: c.concepto ? c.concepto.trim() : null,
  neto: Number(c.neto),
  alicuota_iva_id: Number(c.alicuota_iva_id),
  percepcion_iva: Number(c.percepcion_iva || 0),
  // La cuenta de gasto del plan. Reemplaza a centro_costo_id + tipo_gasto_id:
  // el centro sale de esta cuenta, así que no puede contradecir al plan.
  cuenta_gasto_id: Number(c.cuenta_gasto_id),
  fecha_vencimiento: c.fecha_vencimiento || null,
});
