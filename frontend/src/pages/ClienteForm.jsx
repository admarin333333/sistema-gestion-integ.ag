import { useState } from "react";
import {
  actualizarCliente,
  aPayload,
  buscarLocalidad,
  crearCliente,
} from "../api/clientes.js";

const ACTIVIDADES = [
  ["profesional", "Profesional"],
  ["comercio", "Comercio"],
  ["industria", "Industria"],
  ["cabanas", "Cabañas"],
  ["inmobiliaria", "Inmobiliaria"],
  ["servicios", "Servicios"],
];

const TIPOS = [
  ["monotributista", "Monotributista"],
  ["responsable_inscripto", "Responsable inscripto"],
  ["autonomo", "Autónomo"],
  ["cooperativa", "Cooperativa"],
  ["asociacion_civil", "Asociación civil"],
];

const VACIO = {
  tipo_persona: "fisica",
  nombre: "",
  apellido: "",
  cuit: "",
  dni: "",
  email: "",
  cod_area: "",
  telefono: "",
  domicilio: "",
  localidad: "",
  codigo_postal: "",
  provincia: "",
  actividad_economica: "",
  tipo_actividad: "",
  observaciones: "",
  servicios: [],
};

export default function ClienteForm({ cliente, servicios, onGuardado, onCancelar }) {
  const esEdicion = Boolean(cliente);
  const [datos, setDatos] = useState(() =>
    cliente
      ? {
          tipo_persona: cliente.tipo_persona,
          nombre: cliente.nombre,
          apellido: cliente.apellido || "",
          cuit: cliente.cuit || "",
          dni: cliente.dni || "",
          email: cliente.email || "",
          cod_area: cliente.cod_area || "",
          telefono: cliente.telefono || "",
          domicilio: cliente.domicilio || "",
          localidad: cliente.localidad || "",
          codigo_postal: cliente.codigo_postal || "",
          provincia: cliente.provincia || "",
          actividad_economica: cliente.actividad_economica,
          tipo_actividad: cliente.tipo_actividad,
          observaciones: cliente.observaciones || "",
          servicios: cliente.servicios.map((s) => s.id),
        }
      : VACIO
  );
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const fisica = datos.tipo_persona === "fisica";

  const set = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }));

  const cambiarPersona = (valor) =>
    setDatos((d) => ({ ...d, tipo_persona: valor, dni: valor === "juridica" ? "" : d.dni }));

  const alternarServicio = (id) =>
    setDatos((d) => ({
      ...d,
      servicios: d.servicios.includes(id)
        ? d.servicios.filter((s) => s !== id)
        : [...d.servicios, id],
    }));

  /** Con 4 dígitos de CP completo la localidad y la provincia. */
  const cambiarCodigoPostal = async (valor) => {
    set("codigo_postal", valor);
    if (!/^\d{4}$/.test(valor)) return;
    try {
      const encontradas = await buscarLocalidad(valor);
      if (encontradas.length > 0) {
        const l = encontradas[0];
        setDatos((d) => ({ ...d, localidad: l.nombre, provincia: l.provincia }));
      }
    } catch {
      /* si falla, se carga la localidad a mano */
    }
  };

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    const cuerpo = {
      ...datos,
      nombre: datos.nombre.trim(),
      apellido: fisica ? datos.apellido.trim() : null,
      cuit: datos.cuit.trim() || null,
      dni: fisica ? datos.dni.trim() || null : null,
      email: datos.email.trim() || null,
      cod_area: datos.cod_area.trim() || null,
      telefono: datos.telefono.trim() || null,
      domicilio: datos.domicilio.trim() || null,
      localidad: datos.localidad.trim() || null,
      codigo_postal: datos.codigo_postal.trim() || null,
      provincia: datos.provincia.trim() || null,
      observaciones: datos.observaciones.trim() || null,
      actividad_economica: datos.actividad_economica,
      tipo_actividad: datos.tipo_actividad,
      servicios: datos.servicios,
    };
    try {
      const guardado = esEdicion
        ? await actualizarCliente(cliente.id, cuerpo)
        : await crearCliente(cuerpo);
      onGuardado(guardado);
    } catch (err) {
      setError(err.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section>
      <span className="kicker">Clientes</span>
      <h1>{esEdicion ? "Modificar cliente" : "Nuevo cliente"}</h1>
      <p className="lead">
        Los campos con <span style={{ color: "var(--accent-3)" }}>*</span> son
        obligatorios.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={enviar}>
        <fieldset className="fieldset">
          <legend>Quién es</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Tipo de persona <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.tipo_persona}
                onChange={(e) => cambiarPersona(e.target.value)}
              >
                <option value="fisica">Persona física</option>
                <option value="juridica">Persona jurídica</option>
              </select>
            </label>

            <label className="campo">
              <span>
                {fisica ? "Nombre" : "Razón social"} <b className="obligatorio">*</b>
              </span>
              <input
                required
                value={datos.nombre}
                onChange={(e) => set("nombre", e.target.value)}
                placeholder={fisica ? "Juan" : "Distribuidora Norte SRL"}
              />
            </label>

            {fisica && (
              <label className="campo">
                <span>
                  Apellido <b className="obligatorio">*</b>
                </span>
                <input
                  required
                  value={datos.apellido}
                  onChange={(e) => set("apellido", e.target.value)}
                  placeholder="Pérez"
                />
              </label>
            )}

            <label className="campo">
              <span>
                CUIT {fisica ? "" : <b className="obligatorio">*</b>}
                {!fisica && " "}
                {fisica && <i style={{ fontStyle: "normal" }}>(opcional)</i>}
              </span>
              <input
                required={!fisica}
                value={datos.cuit}
                onChange={(e) => set("cuit", e.target.value)}
                placeholder="20-26473674-2"
                inputMode="numeric"
              />
            </label>

            {fisica && (
              <label className="campo">
                <span>
                  DNI <b className="obligatorio">*</b>
                </span>
                <input
                  required
                  value={datos.dni}
                  onChange={(e) => set("dni", e.target.value)}
                  placeholder="26473674"
                  inputMode="numeric"
                />
              </label>
            )}
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <legend>Dónde vive y a qué se dedica</legend>
          <div className="form-grid">
            <label className="campo">
              <span>Email</span>
              <input
                type="email"
                value={datos.email}
                onChange={(e) => set("email", e.target.value)}
                placeholder="cliente@ejemplo.com"
              />
            </label>

            <label className="campo">
              <span>Código de área</span>
              <input
                value={datos.cod_area}
                onChange={(e) => set("cod_area", e.target.value)}
                placeholder="351"
                inputMode="numeric"
                maxLength={5}
              />
            </label>

            <label className="campo">
              <span>Teléfono</span>
              <input
                value={datos.telefono}
                onChange={(e) => set("telefono", e.target.value)}
                placeholder="1234567"
                inputMode="numeric"
                maxLength={11}
              />
            </label>

            <label className="campo">
              <span>Domicilio</span>
              <input
                value={datos.domicilio}
                onChange={(e) => set("domicilio", e.target.value)}
                placeholder="Av. Siempreviva 742"
              />
            </label>

            <label className="campo">
              <span>Localidad</span>
              <input
                value={datos.localidad}
                onChange={(e) => set("localidad", e.target.value)}
                placeholder="Córdoba"
              />
            </label>

            <label className="campo">
              <span>Código postal</span>
              <input
                value={datos.codigo_postal}
                onChange={(e) => cambiarCodigoPostal(e.target.value)}
                placeholder="5854"
                inputMode="numeric"
                maxLength={4}
                title="Con 4 dígitos se completa solo la localidad"
              />
            </label>

            <label className="campo">
              <span>Provincia</span>
              <input
                value={datos.provincia}
                onChange={(e) => set("provincia", e.target.value)}
                placeholder="Córdoba"
              />
            </label>

            <label className="campo">
              <span>
                Actividad económica <b className="obligatorio">*</b>
              </span>
              <select
                required
                value={datos.actividad_economica}
                onChange={(e) => set("actividad_economica", e.target.value)}
              >
                <option value="">Elegí una…</option>
                {ACTIVIDADES.map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Tipo de actividad <b className="obligatorio">*</b>
              </span>
              <select
                required
                value={datos.tipo_actividad}
                onChange={(e) => set("tipo_actividad", e.target.value)}
              >
                <option value="">Elegí uno…</option>
                {TIPOS.map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <legend>Servicios que contrata</legend>
          <div className="checks">
            {servicios.map((s) => (
              <label className="check" key={s.id}>
                <input
                  type="checkbox"
                  checked={datos.servicios.includes(s.id)}
                  onChange={() => alternarServicio(s.id)}
                />
                {s.nombre}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="campo">
          <span>Observaciones — un solo texto</span>
          <textarea
            value={datos.observaciones}
            onChange={(e) => set("observaciones", e.target.value)}
            placeholder="Descripción del servicio que solicita el cliente…"
          />
        </label>

        <div className="form-acciones">
          <button className="btn" type="submit" disabled={enviando}>
            {enviando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Dar de alta"}
          </button>
          <button className="btn fantasma" type="button" onClick={onCancelar}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}
