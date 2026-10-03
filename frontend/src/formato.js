/** Nombre del estudio: tiene que coincidir con `nombre_estudio`
 *  de backend/app/config.py (de ahí sale el encabezado de los PDF y Excel). */
export const NOMBRE_ESTUDIO = "ESTUDIO INTEGRAL AM";

/** 1234.5 -> "1.234,50" (formato argentino). */
export const pesos = (v) =>
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(v) || 0);

/** 12276.766 -> "12.276,7660" — índices y coeficiente con4 decimales. */
export const cuatro = (v) =>
  v === null || v === undefined || v === ""
    ? "—"
    : new Intl.NumberFormat("es-AR", {
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
      }).format(Number(v));

/** "2026-09-30" -> "30/09/2026". */
export const fecha = (iso) => (iso ? String(iso).split("-").reverse().join("/") : "—");

/** "2026-10-01T14:23:05" -> "01/10/2026 14:23".
 *  El backend guarda la hora en UTC (datetime.utcnow), así que se convierte a
 *  la hora local: si no, un cambio hecho a las 21 de Argentina saldría como
 *  "mañana 00:xx". Las fechas solas (sin hora) no se desplazan. */
export const fechaHora = (iso) => {
  if (!iso) return "—";
  const s = String(iso);
  if (s.length <= 10) return fecha(s); // solo fecha: se muestra tal cual
  const d = new Date(`${s.slice(0, 10)}T${s.slice(11, 19)}Z`);
  if (Number.isNaN(d.getTime())) return `${fecha(s.slice(0, 10))} ${s.slice(11, 16)}`;
  const dos = (n) => String(n).padStart(2, "0");
  return (
    `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ` +
    `${dos(d.getHours())}:${dos(d.getMinutes())}`
  );
};

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
