import { api } from "./client.js";

export const listarAlicuotas = (todas = false) =>
  api(`/alicuotas-iva${todas ? "?todas=true" : ""}`);

export const crearAlicuota = (cuerpo) =>
  api("/alicuotas-iva", { method: "POST", body: cuerpo });

export const eliminarAlicuota = (id) =>
  api(`/alicuotas-iva/${id}`, { method: "DELETE" });
