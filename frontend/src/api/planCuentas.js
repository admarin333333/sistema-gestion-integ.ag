import { api } from "./client.js";

/** El plan de cuentas completo. `todas` incluye las apagadas. */
export const listarPlanCuentas = ({ todas = false, q = "" } = {}) => {
  const p = new URLSearchParams();
  if (todas) p.set("todas", "true");
  if (q) p.set("q", q);
  const s = p.toString();
  return api(`/plan-cuentas${s ? `?${s}` : ""}`);
};

export const obtenerPlanCuenta = (id) => api(`/plan-cuentas/${id}`);

/** Alta de una cuenta colgando de otra. El código lo arma el backend. */
export const crearPlanCuenta = (datos) =>
  api("/plan-cuentas", { method: "POST", body: datos });

/** Renombra, cambia el tipo de auxiliar o apaga. El código no se toca. */
export const editarPlanCuenta = (id, datos) =>
  api(`/plan-cuentas/${id}`, { method: "PUT", body: datos });

/** Apaga una cuenta de detalle (no la borra). */
export const apagarPlanCuenta = (id) =>
  api(`/plan-cuentas/${id}`, { method: "DELETE" });