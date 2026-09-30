import { api } from "./client.js";

/* ------------------------------------------------------------------ clientes */

export const listarClientes = (q) =>
  api(`/clientes${q ? `?q=${encodeURIComponent(q)}` : ""}`);

export const obtenerCliente = (id) => api(`/clientes/${id}`);

export const crearCliente = (cuerpo) =>
  api("/clientes", { method: "POST", body: cuerpo });

export const actualizarCliente = (id, cuerpo) =>
  api(`/clientes/${id}`, { method: "PUT", body: cuerpo });

export const eliminarCliente = (id) =>
  api(`/clientes/${id}`, { method: "DELETE" });

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
 */
export const aPayload = (c) => ({
  tipo_persona: c.tipo_persona,
  nombre: c.nombre,
  apellido: c.apellido ?? null,
  cuit: c.cuit ?? null,
  dni: c.dni ?? null,
  email: c.email ?? null,
  cod_area: c.cod_area ?? null,
  telefono: c.telefono ?? null,
  domicilio: c.domicilio ?? null,
  localidad: c.localidad ?? null,
  codigo_postal: c.codigo_postal ?? null,
  provincia: c.provincia ?? null,
  actividad_economica: c.actividad_economica,
  tipo_actividad: c.tipo_actividad,
  observaciones: c.observaciones ?? null,
  servicios: (c.servicios || []).map((s) => s.id),
});
