import { api } from "./client.js";

export const query = (filtros = {}) => {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listarTiposGasto = (f = {}) => api(`/tipos-gasto${query(f)}`);

export const crearTipoGasto = (cuerpo) =>
  api("/tipos-gasto", { method: "POST", body: cuerpo });

export const eliminarTipoGasto = (id) =>
  api(`/tipos-gasto/${id}`, { method: "DELETE" });
