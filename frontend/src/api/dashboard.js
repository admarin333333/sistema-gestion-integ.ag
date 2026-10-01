import { api } from "./client.js";

export const getKPIs = () => api("/dashboard/kpis");
export const getAlertas = (dias = 30) => api(`/dashboard/alertas?dias=${dias}`);
export const getProximasVencimientos = (dias = 7) => api(`/dashboard/proximas-vencimientos?dias=${dias}`);