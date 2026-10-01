import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import { listarFacturas } from "../api/facturas.js";
import {
  ESTADOS,
  aPayload,
  actualizarAnticipo,
  crearAnticipo,
  obtenerAnticipo,
  listarAplicaciones,
  aplicarAnticipo,
  desaplicarAnticipo,
} from "../api/anticipos.js";

const HOY = new Date().toISOString().slice(0, 10);

const VACIO = {
  cliente_id: "",
  fecha: HOY,
  importe: "",
};

export default function AnticipoForm({ anticipoId, onGuardado, onCancelar }) {
  const esEdicion = Boolean(anticipoId);
  const [datos, setDatos] = useState(VACIO);
  const [clientes, setClientes] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [aplicaciones, setAplicaciones] = useState([]);
  const [cargando, setCargando] = useState(esEdicion);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [nuevaAplicacion, setNuevaAplicacion] = useState({ factura_id: "", importe: "" });
  const [anticipo, setAnticipo] = useState(null);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  const cargarFacturas = async (clienteId) => {
    if (!clienteId) {
      setFacturas([]);
      return;
    }
    try {
      const items = await listarFacturas({
        cliente_id: clienteId,
        estado: "pendiente",
      });
      const pendientes = items.filter((f) => f.estado === "pendiente" || f.estado === "parcial");
      setFacturas(pendientes);
    } catch {
      setFacturas([]);
    }
  };

  useEffect(() => {
    if (!esEdicion) return;
    obtenerAnticipo(anticipoId)
      .then((a) => {
        setAnticipo(a);
        setDatos({
          cliente_id: String(a.cliente_id),
          fecha: a.fecha,
          importe: a.importe,
        });
        cargarFacturas(a.cliente_id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [anticipoId, esEdicion]);

  useEffect(() => {
    if (!esEdicion || !datos.cliente_id) return;
    cargarFacturas(datos.cliente_id);
  }, [datos.cliente_id, esEdicion]);

  const cargarAplicaciones = async () => {
    if (!anticipoId) return;
    try {
      const apps = await listarAplicaciones(anticipoId);
      setAplicaciones(apps);
    } catch {
      setAplicaciones([]);
    }
  };

  useEffect(() => {
    cargarAplicaciones();
  }, [anticipoId]);

  const set = (campo) => (e) => setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const setApp = (campo) => (e) =>
    setNuevaAplicacion((a) => ({ ...a, [campo]: e.target.value }));

  const importeAplicado = aplicaciones.reduce((s, a) => s + a.importe, 0);
  const libre = Number(datos.importe || 0) - importeAplicado;

  const guardar = async () => {
    const cuerpo = aPayload(datos);
    return esEdicion
      ? await actualizarAnticipo(anticipoId, cuerpo)
      : await crearAnticipo(cuerpo);
  };

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      const r = await guardar();
      onGuardado(r);
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  const agregarAplicacion = async (e) => {
    e.preventDefault();
    if (!nuevaAplicacion.factura_id || !nuevaAplicacion.importe) return;
    const importe = Number(nuevaAplicacion.importe);
    if (importe > libre + 0.005) {
      setError(`El anticipo solo tiene $${libre.toFixed(2)} sin imputar`);
      return;
    }
    setError("");
    try {
      await aplicarAnticipo(anticipoId, {
        factura_id: Number(nuevaAplicacion.factura_id),
        importe,
      });
      setNuevaAplicacion({ factura_id: "", importe: "" });
      await cargarAplicaciones();
    } catch (e2) {
      setError(e2.message);
    }
  };

  const quitarAplicacion = async (appId) => {
    if (!window.confirm("¿Quitar esta imputación?")) return;
    try {
      await desaplicarAnticipo(appId);
      await cargarAplicaciones();
    } catch (e2) {
      setError(e2.message);
    }
  };

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">Anticipos</span>
      <h1>{esEdicion ? "Modificar anticipo" : "Nuevo anticipo"}</h1>
      <p className="lead">
        Los campos con <span style={{ color: "var(--accent-3)" }}>*</span> son
        obligatorios. El número se genera automáticamente.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={enviar}>
        <fieldset className="fieldset">
          <legend>Anticipo</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Cliente <b className="obligatorio">*</b>
              </span>
              <select value={datos.cliente_id} onChange={set("cliente_id")} disabled={esEdicion}>
                <option value="">Elegí un cliente…</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre_completo}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Fecha <b className="obligatorio">*</b>
              </span>
              <input type="date" value={datos.fecha} onChange={set("fecha")} />
            </label>

            {esEdicion && anticipo && (
              <label className="campo">
                <span>Número (automático)</span>
                <input value={anticipo.numero} readOnly style={{ background: "var(--bg-2)" }} />
              </label>
            )}

            <label className="campo">
              <span>
                Importe <b className="obligatorio">*</b>
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={datos.importe}
                onChange={set("importe")}
                placeholder="0,00"
              />
            </label>
          </div>
        </fieldset>

        {esEdicion && anticipo && (
          <fieldset className="fieldset">
            <legend>Estado: <span className={`chip ${anticipo.estado}`}>{anticipo.estado}</span></legend>
          </fieldset>
        )}

        {esEdicion && anticipo && anticipo.estado !== "aplicado" && (
          <>
            <fieldset className="fieldset">
              <legend>
                Imputar a facturas <small>(pendientes o parciales del cliente)</small>
              </legend>
              <p className="nota">
                Importe del anticipo: <b>{Number(datos.importe || 0).toFixed(2)}</b> ·
                Ya imputado: <b>{importeAplicado.toFixed(2)}</b> ·
                Disponible: <b style={{ color: "var(--accent-3)" }}>{libre.toFixed(2)}</b>
              </p>

              {facturas.length === 0 ? (
                <p className="lista-vacia">
                  Este cliente no tiene facturas pendientes o parciales.
                </p>
              ) : (
                <>
                  <form className="buscador" onSubmit={agregarAplicacion}>
                    <select
                      value={nuevaAplicacion.factura_id}
                      onChange={setApp("factura_id")}
                      aria-label="Factura"
                    >
                      <option value="">Elegí factura a imputar…</option>
                      {facturas.map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.tipo_comprobante} {f.punto_venta}-{f.numero} —
                          {f.concepto || "Sin concepto"} —
                          $ {Number(f.importe).toFixed(2)} —
                          {f.estado === "pendiente"
                            ? "Pendiente"
                            : `Parcial ($${(f.importe - f.aplicado || 0).toFixed(2)} pend)`}
                        </option>
                      ))}
                    </select>
                    <label className="campo" style={{ flex: "0 0 140px" }}>
                      <span>Importe</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={nuevaAplicacion.importe}
                        onChange={setApp("importe")}
                        placeholder="0,00"
                      />
                    </label>
                    <button className="btn btn-sm" type="submit" disabled={libre <= 0.005}>
                      + Imputar
                    </button>
                  </form>

                  {aplicaciones.length > 0 && (
                    <div className="tabla-envoltura">
                      <table className="tabla">
                        <thead>
                          <tr>
                            <th>Factura</th>
                            <th>Concepto</th>
                            <th className="derecha">Importe imputado</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {aplicaciones.map((a) => (
                            <tr key={a.id}>
                              <td className="mono">
                                {a.factura.tipo_comprobante} {a.factura.punto_venta}-{a.factura.numero}
                              </td>
                              <td>{a.factura.concepto || "—"}</td>
                              <td className="mono derecha">{Number(a.importe).toFixed(2)}</td>
                              <td className="acciones">
                                <button
                                  className="btn btn-sm peligro"
                                  onClick={() => quitarAplicacion(a.id)}
                                >
                                  Quitar
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </fieldset>
          </>
        )}

        {esEdicion && anticipo && anticipo.estado === "aplicado" && (
          <div className="panel" style={{ marginTop: "1rem", textAlign: "center" }}>
            <span className="chip aplicado">Anticipo totalmente imputado (Aplicado)</span>
            <p className="nota" style={{ marginTop: "0.5rem" }}>
              Este anticipo ya fue imputado en su totalidad. No se pueden agregar más imputaciones.
              <br />
              Si necesitás imputar a otra factura, quitá alguna imputación existente.
            </p>
          </div>
        )}

        {esEdicion && anticipo && anticipo.estado === "eliminado" && (
          <div className="panel" style={{ marginTop: "1rem", textAlign: "center" }}>
            <span className="chip eliminado">Anticipo eliminado</span>
            <p className="nota" style={{ marginTop: "0.5rem" }}>
              Este anticipo fue eliminado. No se pueden realizar modificaciones ni imputaciones.
            </p>
          </div>
        )}

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