import { api } from "./client.js";

/**
 * Cuentas bancarias de los CLIENTES. Un cliente puede tener todas las que
 * quiera, así que esto devuelve una lista y no un objeto.
 *
 * Ojo: son cuentas de cliente, no las cuentas propias del estudio (esas están en
 * `propietario`).
 */
export const listarCuentas = (clienteId, incluirInactivas = false) =>
  api(
    `/ctas-bancarias/clientes/${clienteId}` +
      (incluirInactivas ? "?incluir_inactivas=true" : "")
  );

export const crearCuenta = (clienteId, cuerpo) =>
  api(`/ctas-bancarias/clientes/${clienteId}`, { method: "POST", body: cuerpo });

export const actualizarCuenta = (cuentaId, cuerpo) =>
  api(`/ctas-bancarias/${cuentaId}`, { method: "PUT", body: cuerpo });

/** Dar de baja, NO borrar: la cuenta puede estar usada en un recibo emitido. */
export const darDeBajaCuenta = (cuentaId) =>
  api(`/ctas-bancarias/${cuentaId}/baja`, { method: "POST" });

export const reactivarCuenta = (cuentaId) =>
  api(`/ctas-bancarias/${cuentaId}/reactivar`, { method: "POST" });

/* ------------------------------------------------------------------ bancos */

/** El catálogo para el selector. El código es el del BCRA, de 8 dígitos. */
export const listarBancos = () => api("/ctas-bancarias/bancos");

export const crearBanco = (cuerpo) =>
  api("/ctas-bancarias/bancos", { method: "POST", body: cuerpo });

/**
 * Le pone (o le corrige) el nombre a un banco.
 *
 * El **código no se puede cambiar**: es la clave primaria y sale del CBU. Si se
 * pudiera cambiar, las cuentas que apuntan al código viejo quedarían huérfanas.
 * Lo único que se escribe a mano es el nombre.
 */
export const renombrarBanco = (codigo, nombre) =>
  api(`/ctas-bancarias/bancos/${codigo}`, { method: "PUT", body: { codigo, nombre } });

/**
 * Qué banco es este CBU. Los primeros 8 dígitos lo dicen.
 *
 * Sirve para cargar el catálogo: el catálogo arranca vacío (los códigos de los
 * bancos no se inventan) y se llena con los CBU que el contador pega.
 */
export const bancoDesdeCBU = (cbu) =>
  api(`/ctas-bancarias/bancos/desde-cbu?cbu=${cbu}`);