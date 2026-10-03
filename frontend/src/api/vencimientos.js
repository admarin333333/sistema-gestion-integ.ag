import { api } from "./client.js";

/** Catálogo de impuestos que se pueden cargar (los que define ARCA). */
export const listarImpuestos = () => api("/vencimientos-impositivos/impuestos");

/** Vencimientos cargados de un mes/año (para pintar la grilla). */
export const listarVencimientos = (anio, mes) =>
  api(`/vencimientos-impositivos?anio=${anio}&mes=${mes}`);

/**
 * Guarda la grilla del mes: reemplaza todo lo que había.
 * `filas` es una lista de { ultimo_digito, impuesto, fecha_vencimiento }.
 *
 * `vaciar` tiene que ir en true SOLO cuando el usuario confirmó que quiere
 * dejar el mes vacío. Si no, el backend responde 409 y no borra nada.
 */
export const guardarVencimientos = (anio, mes, filas, vaciar = false) =>
  api(
    `/vencimientos-impositivos?anio=${anio}&mes=${mes}&vaciar=${vaciar ? "true" : "false"}`,
    { method: "POST", body: filas }
  );

/** Calendario del mes: vencimientos agrupados por dígito de CUIT + clientes. */
export const detalleVencimientos = (anio, mes) =>
  api(`/vencimientos-impositivos/detalle?anio=${anio}&mes=${mes}`);

/* ------------------------------------------------------------------ */
/* Catálogo de conceptos (se edita desde Configuración)                 */
/* ------------------------------------------------------------------ */

/**
 * Todos los conceptos, con los apagados incluidos.
 *
 * Ojo el `incluir_inactivos=true`: sin eso el backend esconde los apagados y
 * en Configuración no se verían (ni se podrían volver a activar).
 */
export const listarConceptos = () =>
  api("/vencimientos-impositivos/conceptos?incluir_inactivos=true");

/** Alta de un concepto nuevo. El backend le arma la clave. */
export const crearConcepto = (nombre) =>
  api("/vencimientos-impositivos/conceptos", {
    method: "POST",
    body: { nombre },
  });

/** Renombra un concepto (la clave no se toca). */
export const editarConcepto = (id, nombre) =>
  api(`/vencimientos-impositivos/conceptos/${id}`, {
    method: "PUT",
    body: { nombre },
  });

/** Vuelve a encender un concepto que estaba apagado. */
export const activarConcepto = (id) =>
  api(`/vencimientos-impositivos/conceptos/${id}`, {
    method: "PUT",
    body: { activo: true },
  });

/**
 * Apaga un concepto. No lo borra: los vencimientos viejos que lo usan siguen
 * en la base y muestran la clave como nombre.
 */
export const desactivarConcepto = (id) =>
  api(`/vencimientos-impositivos/conceptos/${id}`, { method: "DELETE" });

/* ------------------------------------------------------------------ */
/* Meses guardados (para el árbol año -> mes de Configuración)          */
/* ------------------------------------------------------------------ */

/** Un registro por mes guardado: cuántos vencimientos tiene y cuándo se guardó. */
export const listarMeses = () => api("/vencimientos-impositivos/meses");

/** Vuelve a poner el último guardado de un mes (desde el respaldo). */
export const restaurarMes = (anio, mes) =>
  api("/vencimientos-impositivos/meses/restaurar", {
    method: "POST",
    body: { anio, mes },
  });