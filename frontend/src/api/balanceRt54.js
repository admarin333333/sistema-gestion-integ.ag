import { api, descargar } from "./client.js";

/** Ejercicios de balance de un cliente (la tabla que se ve al elegirlo). */
export const listarEjercicios = (clienteId) =>
  api(`/balance-rt54/ejercicios?cliente_id=${clienteId}`);

/** Crea un ejercicio; la carátula se copia de la ficha del cliente. */
export const crearEjercicio = (cuerpo) =>
  api("/balance-rt54/ejercicios", { method: "POST", body: cuerpo });

/** Los tres estados con los totales ya calculados por el backend. */
export const obtenerBalance = (ejercicioId) =>
  api(`/balance-rt54/ejercicios/${ejercicioId}`);

/** Guarda carátula e importes; devuelve todo recalculado. */
export const guardarBalance = (ejercicioId, cuerpo) =>
  api(`/balance-rt54/ejercicios/${ejercicioId}`, { method: "PUT", body: cuerpo });

/** Sumatorias de los cuadros de notas con estos importes, sin guardar. */
export const recalcularCuadros = (celdas) =>
  api("/balance-rt54/cuadros-notas", { method: "POST", body: { celdas_nota: celdas } });

export const eliminarEjercicio = (ejercicioId) =>
  api(`/balance-rt54/ejercicios/${ejercicioId}`, { method: "DELETE" });

/** Emite el Excel del modelo RT54 (descarga con token). */
export const emitirExcel = (ejercicioId) =>
  descargar(`/balance-rt54/ejercicios/${ejercicioId}/export.xlsx`);

/** Balance al cierre actualizado con el índice FACPCE (sin guardar). */
export const monedaHomogenea = (ejercicioId) =>
  api(`/balance-rt54/ejercicios/${ejercicioId}/moneda-homogenea`);

/** Excel aparte con el balance actualizado por moneda homogénea. */
export const descargarMonedaHomogenea = (ejercicioId) =>
  descargar(`/balance-rt54/ejercicios/${ejercicioId}/moneda-homogenea.xlsx`);
