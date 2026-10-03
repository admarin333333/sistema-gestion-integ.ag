import { api } from "./client.js";

/** Los ejercicios del ESTUDIO. Ojo: no es el de cada cliente (ese va aparte). */
export const listarEjercicios = () => api("/ejercicios");

export const ejercicioVigente = () => api("/ejercicios/vigente");

export const crearEjercicio = (cuerpo) =>
  api("/ejercicios", { method: "POST", body: cuerpo });

export const editarEjercicio = (id, cuerpo) =>
  api(`/ejercicios/${id}`, { method: "PUT", body: cuerpo });

export const cerrarEjercicio = (id) =>
  api(`/ejercicios/${id}/cerrar`, { method: "POST" });

export const abrirEjercicio = (id) =>
  api(`/ejercicios/${id}/abrir`, { method: "POST" });

/* ------------------------------------------------------------------ períodos */

/** Los 12 períodos (los meses) de un ejercicio, con cuántos documentos tienen. */
export const listarPeriodos = (ejercicioId) =>
  api(`/ejercicios/periodos/${ejercicioId}`);

/**
 * Abre o cierra un período.
 *
 * `forzar` es lo que permite cerrar un mes que ya tiene documentos: la primera
 * vez el backend contesta "tiene 47 documentos, ¿lo cerrás igual?", la pantalla
 * lo muestra y vuelve a llamar con `forzar: true`. Sin ese segundo paso, un clic
 * de más cerraría un mes con toda la contabilidad de arriba.
 */
export const cambiarPeriodo = (periodoId, cerrado, forzar = false) =>
  api(`/ejercicios/periodos/${periodoId}/estado`, {
    method: "POST",
    body: { cerrado, forzar },
  });

/** En qué período cae una fecha (y si está abierto). */
export const periodoDeFecha = (fecha) =>
  api(`/ejercicios/periodo-de-fecha?fecha=${fecha}`);