import { api } from "./client.js";

/** Índices de moneda homogénea (FACPCE), del mes más nuevo al más viejo. */
export const listarIndices = () => api("/indices-moneda");

/** Da de alta el índice de un mes; si el mes ya existe, lo corrige. */
export const guardarIndice = (cuerpo) =>
  api("/indices-moneda", { method: "POST", body: cuerpo });

export const eliminarIndice = (id) =>
  api(`/indices-moneda/${id}`, { method: "DELETE" });
