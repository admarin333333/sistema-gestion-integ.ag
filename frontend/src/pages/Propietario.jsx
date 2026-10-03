import { useEffect, useState } from "react";

const VACIO = {
  nombre: "",
  cuit: "",
  actividad: "",
  calle: "",
  numero_calle: "",
  localidad: "",
  provincia: "",
  codigo_postal: "",
  cod_area: "",
  telefono: "",
  email_1: "",
  email_2: "",
  email_3: "",
  email_4: "",
  observaciones: "",
};

export default function Propietario({ obtener, guardar }) {
  const [datos, setDatos] = useState(VACIO);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    obtener()
      .then((p) => {
        const nuevo = { ...VACIO };
        [
          "nombre", "cuit", "actividad", "calle", "numero_calle", "localidad",
          "provincia", "codigo_postal", "cod_area", "telefono",
          "email_1", "email_2", "email_3", "email_4", "observaciones",
        ].forEach((k) => {
          if (p && p[k]) nuevo[k] = p[k];
        });
        setDatos(nuevo);
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (campo) => (e) =>
    setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const enviar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setMensaje("");
    setError("");
    try {
      await guardar(datos);
      setMensaje("Datos del propietario guardados ✓");
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  const campo = (etiqueta, nombre, opciones = {}) => (
    <label className="campo">
      <span>{etiqueta}</span>
      <input
        value={datos[nombre]}
        onChange={set(nombre)}
        type={opciones.tipo || "text"}
        placeholder={opciones.placeholder || ""}
      />
    </label>
  );

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <form className="panel" onSubmit={enviar}>
      <h3>Datos del propietario del software</h3>
      <p className="nota">
        Se usan en los encabezados de los Excel y para mandar los avisos de
        vencimientos.
      </p>

      <fieldset className="fieldset">
        <legend>Quién es</legend>
        <div className="buscador">
          {campo("Nombre o razón social", "nombre")}
          {campo("CUIT", "cuit", { placeholder: "30-12345678-9" })}
          {campo("Actividad", "actividad")}
        </div>
      </fieldset>

      <fieldset className="fieldset">
        <legend>Dónde está</legend>
        <div className="buscador">
          {campo("Calle", "calle")}
          {campo("Número", "numero_calle")}
          {campo("Localidad", "localidad")}
          {campo("Provincia", "provincia")}
          {campo("Código postal", "codigo_postal")}
          {campo("Código de área", "cod_area")}
          {campo("Teléfono", "telefono")}
        </div>
      </fieldset>

      <fieldset className="fieldset">
        <legend>A quién se le avisa</legend>
        <p className="nota">
          Carga hasta 4 correos: si el estudio lo administran varias personas,
          los avisos se mandan a todos.
        </p>
        <div className="buscador">
          {campo("Correo 1", "email_1", { tipo: "email", placeholder: "administra@estudio.com" })}
          {campo("Correo 2", "email_2", { tipo: "email" })}
          {campo("Correo 3", "email_3", { tipo: "email" })}
          {campo("Correo 4", "email_4", { tipo: "email" })}
        </div>
      </fieldset>

      <fieldset className="fieldset">
        <legend>Otros datos</legend>
        <div className="buscador">
          <label className="campo">
            <span>Observaciones</span>
            <textarea
              value={datos.observaciones}
              onChange={set("observaciones")}
              rows={2}
            />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="eecc-estado ok">{mensaje}</p>}

      <div className="form-acciones">
        <button className="btn" type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar datos del propietario"}
        </button>
      </div>
    </form>
  );
}