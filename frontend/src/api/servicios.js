import { api } from "./client.js";

/**
 * El catálogo de servicios del ESTUDIO.
 *
 * Son los servicios que el estudio ofrece (contabilidad, impositivo, liquidaciones,
 * balances...). Cada cliente elige de esta lista cuáles tiene.
 *
 * El alta es solo del ADMIN: es un catálogo compartido, y si un operador lo
 * modificara podría cambiarle el servicio a todos los clientes.
 */

/** Todos los servicios, en el orden en que aparecen en el formulario. */
export const listarServicios = () => api("/servicios");

/** Carga un servicio nuevo. Si el nombre ya existe, el backend avisa con 409. */
export const crearServicio = (nombre, orden) =>
  api("/servicios", {
    method: "POST",
    body: { nombre, orden: orden === "" || orden == null ? null : Number(orden) },
  });

/** Borra un servicio. Si tiene clientes asignados, el backend avisa con 409. */
export const eliminarServicio = (id) => api(`/servicios/${id}`, { method: "DELETE" });