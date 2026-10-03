import { useEffect, useState } from "react";

export const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

/** El dígito que agrupa a los clientes: el último del CUIT. */
export const digitoDe = (cuit) => (cuit ? String(cuit).slice(-1) : null);

/** "hace 2 días", "en 5 días", "vence hoy"... */
export function diasPara(iso) {
  const f = new Date(`${iso}T00:00:00`);
  const hoyF = new Date();
  hoyF.setHours(0, 0, 0, 0);
  const d = Math.round((f - hoyF) / 86400000);
  if (d === 0) return "vence hoy";
  if (d === 1) return "mañana";
  if (d > 0) return `en ${d} días`;
  return `hace ${Math.abs(d)} días`;
}