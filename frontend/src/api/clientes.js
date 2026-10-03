import { api } from "./client.js";

export const ETIQUETAS_CONDICION_IVA = {
  consumidor_final: "Consumidor final",
  monotributista: "Monotributista",
  responsable_inscripto: "Responsable inscripto",
};

export const ETIQUETAS_TIPO = {
  cliente: "Cliente",
  proveedor: "Proveedor",
};

/* ------------------------------------------------------------------ clientes */

const conFiltros = (base, q, filtros = {}) => {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (filtros.desde) p.set("desde", filtros.desde);
  if (filtros.hasta) p.set("hasta", filtros.hasta);
  // El orden viaja al backend: el navegador solo elige la columna y el
  // backend arma el ORDER BY. Ordenar acá dejaría al contador esperando con
  // 5.000 filas y el papel (que sale del backend) no coincidiría con la pantalla.
  if (filtros.orden) p.set("orden", filtros.orden);
  if (filtros.orden && filtros.desc) p.set("desc", "1");
  const s = p.toString();
  return `${base}${s ? `?${s}` : ""}`;
};

export const listarClientes = (q, filtros = {}) =>
  api(conFiltros("/clientes", q, filtros));

export const obtenerCliente = (id) => api(`/clientes/${id}`);

export const crearCliente = (cuerpo) =>
  api("/clientes", { method: "POST", body: cuerpo });

export const actualizarCliente = (id, cuerpo) =>
  api(`/clientes/${id}`, { method: "PUT", body: cuerpo });

export const eliminarCliente = (id) =>
  api(`/clientes/${id}`, { method: "DELETE" });

/* --------------------------------------------------------------- proveedores */

export const listarProveedores = (q, filtros = {}) =>
  api(conFiltros("/proveedores", q, filtros));

export const obtenerProveedor = (id) => api(`/proveedores/${id}`);

export const crearProveedor = (cuerpo) =>
  api("/proveedores", { method: "POST", body: cuerpo });

export const actualizarProveedor = (id, cuerpo) =>
  api(`/proveedores/${id}`, { method: "PUT", body: cuerpo });

export const eliminarProveedor = (id) =>
  api(`/proveedores/${id}`, { method: "DELETE" });

/**
 * Historial de cambios de la clave fiscal de ARCA.
 * Solo tiene filas si la clave se cargó o se cambió alguna vez.
 */
export const listarHistorialClaveFiscal = (id, esProveedor) =>
  api(`/${esProveedor ? "proveedores" : "clientes"}/${id}/clave-fiscal/historial`);

/* -------------------------------------------------------------- localidades */

/** Localidades que tienen ese código postal (para autocompletar el cliente). */
export const buscarLocalidad = (codigoPostal) =>
  api(`/localidades?codigo_postal=${encodeURIComponent(codigoPostal)}`);

/* ----------------------------------------------------------------- servicios */

export const listarServicios = () => api("/servicios");

/* --------------------------------------------------------------- sugerencias */

export const crearSugerencia = (clienteId, cuerpo) =>
  api(`/clientes/${clienteId}/sugerencias`, { method: "POST", body: cuerpo });

export const actualizarSugerencia = (id, cuerpo) =>
  api(`/sugerencias/${id}`, { method: "PUT", body: cuerpo });

export const eliminarSugerencia = (id) =>
  api(`/sugerencias/${id}`, { method: "DELETE" });

/* ------------------------------------------------------------------ utilidad */

/**
 * Convierte lo que devuelve la API en el cuerpo que espera el PUT.
 * La API manda `servicios` como id; la respuesta los trae como objetos.
 * `servicios` solo aplica al módulo cliente (los proveedores no tienen).
 */
export const aPayload = (c, conServicios = true) => ({
  tipo_persona: c.tipo_persona,
  nombre: c.nombre,
  apellido: c.apellido ?? null,
  cuit: c.cuit ?? null,
  dni: c.dni ?? null,
  clave_fiscal: c.clave_fiscal ?? null,
  email: c.email ?? null,
  cod_area: c.cod_area ?? null,
  telefono: c.telefono ?? null,
  calle: c.calle ?? null,
  numero_calle: c.numero_calle ?? null,
  localidad: c.localidad ?? null,
  codigo_postal: c.codigo_postal ?? null,
  provincia: c.provincia ?? null,
  actividad_economica: c.actividad_economica,
  tipo_actividad: c.tipo_actividad,
  condicion_iva: c.condicion_iva,
  alicuota_iva_id: c.alicuota_iva?.id ?? c.alicuota_iva_id ?? null,
  observaciones: c.observaciones ?? null,
  fecha_cierre_ejercicio: c.fecha_cierre_ejercicio ?? null,
  ...(conServicios ? { servicios: (c.servicios || []).map((s) => s.id) } : {}),
});
