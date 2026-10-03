import { api } from "./client.js";

export const listarVariantes = (pantalla) =>
  api(`/variantes?pantalla=${encodeURIComponent(pantalla)}`);

export const guardarVariante = (cuerpo) =>
  api("/variantes", { method: "POST", body: cuerpo });

export const eliminarVariante = (id) =>
  api(`/variantes/${id}`, { method: "DELETE" });
