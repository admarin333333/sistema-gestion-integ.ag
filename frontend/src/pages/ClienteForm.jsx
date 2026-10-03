import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  actualizarCliente,
  actualizarProveedor,
  aPayload,
  buscarLocalidad,
  crearCliente,
  crearProveedor,
  listarServicios,
  obtenerCliente,
  obtenerProveedor,
  ETIQUETAS_CONDICION_IVA,
  ETIQUETAS_TIPO,
} from "../api/clientes.js";
import { listarAlicuotas } from "../api/alicuotas.js";

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
  clave_fiscal: "",
  email: "",
  cod_area: "",
  telefono: "",
  calle: "",
  numero_calle: "",
  localidad: "",
  codigo_postal: "",
  provincia: "",
  actividad_economica: "",
  tipo_actividad: "",
  condicion_iva: "",
  alicuota_iva_id: "",
  observaciones: "",
  fecha_cierre_ejercicio: "",
  servicios: [],
};

export default function ClienteForm({ tipo = "cliente" }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const esProveedor = tipo === "proveedor";
  const pref = esProveedor ? "proveedor" : "cliente";
  const plural = esProveedor ? "proveedores" : "clientes";
  const esEdicion = Boolean(id);
  // Cada módulo tiene su propio endpoint: clientes y proveedores no se mezclan.
  const obtener = esProveedor ? obtenerProveedor : obtenerCliente;
  const crearRegistro = esProveedor ? crearProveedor : crearCliente;
  const actualizarRegistro = esProveedor ? actualizarProveedor : actualizarCliente;
  const [cliente, setCliente] = useState(null);
  const [servicios, setServicios] = useState([]);
  const [alicuotas, setAlicuotas] = useState([]);
  const [datos, setDatos] = useState(VACIO);
  const [cargando, setCargando] = useState(esEdicion);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    listarServicios()
      .then(setServicios)
      .catch(() => setServicios([]));
    listarAlicuotas()
      .then(setAlicuotas)
      .catch(() => setAlicuotas([]));
  }, []);

  useEffect(() => {
    if (!esEdicion) return;
    obtener(id)
      .then((c) => {
        setCliente(c);
        setDatos({
          tipo_persona: c.tipo_persona,
          nombre: c.nombre,
          apellido: c.apellido || "",
          cuit: c.cuit || "",
          dni: c.dni || "",
          clave_fiscal: c.clave_fiscal || "",
          email: c.email || "",
          cod_area: c.cod_area || "",
          telefono: c.telefono || "",
          calle: c.calle || "",
          numero_calle: c.numero_calle || "",
          localidad: c.localidad || "",
          codigo_postal: c.codigo_postal || "",
          provincia: c.provincia || "",
          actividad_economica: c.actividad_economica,
          tipo_actividad: c.tipo_actividad,
          condicion_iva: c.condicion_iva || "",
          alicuota_iva_id: c.alicuota_iva ? String(c.alicuota_iva.id) : "",
          observaciones: c.observaciones || "",
          fecha_cierre_ejercicio: c.fecha_cierre_ejercicio || "",
          servicios: (c.servicios || []).map((s) => s.id),
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [id, esEdicion]);

  const fisica = datos.tipo_persona === "fisica";
  const esRI = datos.condicion_iva === "responsable_inscripto";

  const set = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }));

  const cambiarCondicionIva = (valor) =>
    setDatos((d) => ({
      ...d,
      condicion_iva: valor,
      alicuota_iva_id: valor === "responsable_inscripto" ? d.alicuota_iva_id : "",
    }));

  /** Si la actividad es monotributo o RI, la condición se completa sola. */
  const cambiarTipoActividad = (valor) =>
    setDatos((d) => ({
      ...d,
      tipo_actividad: valor,
      ...(valor === "monotributista" || valor === "responsable_inscripto"
        ? {
            condicion_iva: valor,
            alicuota_iva_id:
              valor === "responsable_inscripto" ? d.alicuota_iva_id : "",
          }
        : {}),
    }));

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
      clave_fiscal: datos.clave_fiscal.trim() || null,
      email: datos.email.trim() || null,
      cod_area: datos.cod_area.trim() || null,
      telefono: datos.telefono.trim() || null,
      calle: datos.calle.trim() || null,
      numero_calle: datos.numero_calle.trim() || null,
      localidad: datos.localidad.trim() || null,
      codigo_postal: datos.codigo_postal.trim() || null,
      provincia: datos.provincia.trim() || null,
      observaciones: datos.observaciones.trim() || null,
      fecha_cierre_ejercicio: datos.fecha_cierre_ejercicio || null,
      actividad_economica: datos.actividad_economica,
      tipo_actividad: datos.tipo_actividad,
      condicion_iva: datos.condicion_iva,
      alicuota_iva_id: esRI ? Number(datos.alicuota_iva_id) : null,
      // Los servicios son solo del módulo cliente.
      ...(esProveedor ? {} : { servicios: datos.servicios }),
    };
    try {
      const guardado = esEdicion
        ? await actualizarRegistro(id, cuerpo)
        : await crearRegistro(cuerpo);
      navigate(`/${pref}-ficha/${guardado.id}`);
    } catch (err) {
      setError(err.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setEnviando(false);
    }
  };

  const cancelar = () => navigate(esEdicion ? `/${pref}-ficha/${id}` : `/${plural}`);

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">{ETIQUETAS_TIPO[tipo]}</span>
      <h1>{esEdicion ? `Modificar ${ETIQUETAS_TIPO[tipo].toLowerCase()}` : `Nuevo ${ETIQUETAS_TIPO[tipo].toLowerCase()}`}</h1>
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

            {esEdicion && cliente && (
              <label className="campo">
                <span>N° de cuenta (automático)</span>
                <input value={cliente.nro_cuenta} readOnly />
              </label>
            )}

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

          <div className="form-grid">
            <label className="campo">
              <span>
                Clave fiscal de ARCA{" "}
                <i style={{ fontStyle: "normal" }}>(opcional)</i>
              </span>
              <input
                value={datos.clave_fiscal}
                onChange={(e) => set("clave_fiscal", e.target.value)}
                placeholder="ABC123DEF45"
                maxLength={11}
              />
              <small className="ayuda">
                11 caracteres, para trabajar en ARCA en nombre de{" "}
                {esProveedor ? "este proveedor" : "este cliente"}. El sistema
                guarda cuándo la cargaste y cada vez que la cambies.
              </small>
            </label>
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
              <span>Calle</span>
              <input
                value={datos.calle}
                onChange={(e) => set("calle", e.target.value)}
                placeholder="Av. Siempreviva"
                maxLength={30}
              />
            </label>

            <label className="campo">
              <span>Número</span>
              <input
                value={datos.numero_calle}
                onChange={(e) => set("numero_calle", e.target.value)}
                placeholder="742"
                maxLength={10}
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
                onChange={(e) => cambiarTipoActividad(e.target.value)}
              >
                <option value="">Elegí uno…</option>
                {TIPOS.map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Condición ante el IVA <b className="obligatorio">*</b>
              </span>
              <select
                required
                value={datos.condicion_iva}
                onChange={(e) => cambiarCondicionIva(e.target.value)}
              >
                <option value="">Elegí una…</option>
                {Object.entries(ETIQUETAS_CONDICION_IVA).map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            {esRI && (
              <label className="campo">
                <span>
                  Alícuota de IVA <b className="obligatorio">*</b>
                </span>
                <select
                  required
                  value={datos.alicuota_iva_id}
                  onChange={(e) => set("alicuota_iva_id", e.target.value)}
                >
                  <option value="">Elegí una…</option>
                  {alicuotas.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.nombre}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </fieldset>

        {/* Los servicios son solo del módulo cliente: los proveedores no contratan
            servicios del estudio, así que el bloque no se muestra. */}
        {!esProveedor && (
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
        )}

        <label className="campo">
          <span>Fecha de cierre de ejercicio — día y mes (para el Balance RT54)</span>
          <input
            type="date"
            value={datos.fecha_cierre_ejercicio}
            onChange={(e) => set("fecha_cierre_ejercicio", e.target.value)}
          />
        </label>

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
          <button className="btn fantasma" type="button" onClick={cancelar}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}
