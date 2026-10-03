import { api } from "./client.js";

export const getKPIs = () => api("/dashboard/kpis");
export const getAlertas = (dias = 30) => api(`/dashboard/alertas?dias=${dias}`);
export const getProximasVencimientos = (dias = 7) => api(`/dashboard/proximas-vencimientos?dias=${dias}`);

/* Ingresos y gastos de los 12 meses del EJERCICIO vigente, para el gráfico del
   dashboard. Sin parámetro de ejercicio: el gráfico es "cómo va el año". */
export const getResultadoPorPeriodo = () => api("/dashboard/resultado-por-periodo");