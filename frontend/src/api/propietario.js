import { api } from "./client.js";

/** Datos del propietario del software (una sola fila). */
export const obtenerPropietario = () => api("/propietario");

export const guardarPropietario = (cuerpo) =>
  api("/propietario", { method: "PUT", body: cuerpo });