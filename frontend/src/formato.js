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

/** Genera link de WhatsApp con el número formateado.
 *  Recibe código de área y teléfono, devuelve URL de WhatsApp Web. */
export const whatsappLink = (codArea, telefono) => {
  if (!codArea || !telefono) return null;
  const numeros = (codArea + telefono).replace(/\D/g, "");
  if (!numeros) return null;
  // Argentina: 54 + código de área (sin 0) + número
  // Si el código de área empieza con 0, quitarlo
  let cod = String(codArea).replace(/^0/, "");
  const tel = String(telefono).replace(/\D/g, "");
  const numeroCompleto = "54" + cod + tel;
  return `https://wa.me/${numeroCompleto}`;
};

/** Formatea teléfono para mostrar: "(0XXX) XXXX-XXXX" */
export const formatearTelefono = (codArea, telefono) => {
  if (!codArea || !telefono) return "—";
  const cod = String(codArea).replace(/^0/, "");
  const tel = String(telefono).replace(/\D/g, "");
  if (tel.length === 8) {
    return `(0${cod}) ${tel.slice(0,4)}-${tel.slice(4)}`;
  }
  if (tel.length === 7) {
    return `(0${cod}) ${tel.slice(0,3)}-${tel.slice(3)}`;
  }
  return `(0${cod}) ${tel}`;
};
