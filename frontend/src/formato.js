/** Nombre del estudio: tiene que coincidir con `nombre_estudio`
 *  de backend/app/config.py (de ahí sale el encabezado de los PDF y Excel). */
export const NOMBRE_ESTUDIO = "ESTUDIO INTEGRAL AM";

/** 1234.5 -> "1.234,50" (formato argentino). */
export const pesos = (v) =>
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(v) || 0);

/** "2026-09-30" -> "30/09/2026". */
export const fecha = (iso) => (iso ? String(iso).split("-").reverse().join("/") : "—");
