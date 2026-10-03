import { api } from "./client.js";

export const listarCentros = (todos = false) =>
  api(`/centros-costos${todos ? "?todos=true" : ""}`);

export const crearCentro = (cuerpo) =>
  api("/centros-costos", { method: "POST", body: cuerpo });

export const eliminarCentro = (id) =>
  api(`/centros-costos/${id}`, { method: "DELETE" });
