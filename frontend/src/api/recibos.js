import { api } from "./client.js";

export const FORMAS = {
  transferencia: "Transferencia",
  efectivo: "Efectivo",
  tarjeta_credito: "Tarjeta de crédito",
  tarjeta_debito: "Tarjeta de débito",
  cheque: "Cheque",
  otro: "Otro",
};

export const ESTADOS = {
  emitido: "Emitido",
  anulado: "Anulado",
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

export const anularRecibo = (id) =>
  api(`/recibos/${id}/anular`, { method: "POST" });

export const reabrirRecibo = (id) =>
  api(`/recibos/${id}/reabrir`, { method: "POST" });

// aplicaciones
export const listarAplicaciones = (reciboId) =>
  api(`/recibos/${reciboId}/aplicaciones`);

export const aplicarRecibo = (reciboId, cuerpo) =>
  api(`/recibos/${reciboId}/aplicaciones`, { method: "POST", body: cuerpo });

export const desaplicarRecibo = (aplicacionId) =>
  api(`/recibos/aplicaciones/${aplicacionId}`, { method: "DELETE" });

// payload helper - SIN numero (se genera automático)
export const aPayload = (r) => ({
  cliente_id: Number(r.cliente_id),
  fecha: r.fecha,
  importe: Number(r.importe),
  forma_pago: r.forma_pago,
});

// ------------------------------------------------- cobro con varios documentos
// Todo esto NO hace cuentas en el navegador: el backend reparte el importe entre
// las facturas, calcula los saldos (con las notas de crédito restadas) y arma el
// asiento. Acá solo se mandan los ids tildados y los importes de cada pago.

/** Qué tiene este cliente para cobrar: facturas con saldo y notas de crédito. */
export const aCobrar = (clienteId) =>
  api(`/recibos/a-cobrar?cliente_id=${clienteId}`);

/** A qué cuenta va cada forma de pago, y cuáles necesitan que elijas el banco. */
export const formasPago = () => api("/recibos/formas-pago");

/** Las cuentas donde puede ENTRAR la plata (cajas y bancos), no las 200. */
export const cuentasIngreso = () => api("/recibos/cuentas-ingreso");

/** Muestra el recibo y el asiento armedados, SIN guardar nada. */
export const previewCobro = (cuerpo) =>
  api("/recibos/preview-cobro", { method: "POST", body: cuerpo });

/** Genera el asiento de cobranza del recibo. */
export const generarAsientoRecibo = (id) =>
  api(`/recibos/${id}/asiento`, { method: "POST" });

/** Anula el asiento del recibo (el recibo sigue como estaba). */
export const anularAsientoRecibo = (id) =>
  api(`/recibos/${id}/asiento/anular`, { method: "POST" });

/** Cambia las formas de pago de un recibo que todavía no tiene asiento. */
export const guardarPagosRecibo = (id, pagos) =>
  api(`/recibos/${id}/pagos`, { method: "PUT", body: pagos });

// Para armar el cuerpo de `crearRecibo` y de `previewCobro`, que comparten
// exactamente los mismos campos.
export const aCobroPayload = (r) => ({
  cliente_id: Number(r.cliente_id),
  fecha: r.fecha,
  importe: Number(r.importe),
  forma_pago: r.forma_pago,
  facturas: (r.facturas || []).map(Number),
  pagos: (r.pagos || []).map((p) => ({
    forma_pago: p.forma_pago,
    importe: Number(p.importe),
    cuenta_id: p.cuenta_id ? Number(p.cuenta_id) : null,
    detalle: p.detalle || null,
  })),
});