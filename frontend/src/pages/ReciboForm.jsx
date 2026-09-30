import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import { listarFacturas } from "../api/facturas.js";
import {
  FORMAS,
  aPayload,
  actualizarRecibo,
  crearRecibo,
  obtenerRecibo,
  listarAplicaciones,
  aplicarRecibo,
  desaplicarRecibo,
} from "../api/recibos.js";

const HOY = new Date().toISOString().slice(0, 10);

const VACIO = {
  cliente_id: "",
  fecha: HOY,
  numero: "",
  importe: "",
  forma_pago: "transferencia",
};

export default function ReciboForm({ reciboId, onGuardado, onCancelar }) {
  const esEdicion = Boolean(reciboId);
  const [datos, setDatos] = useState(VACIO);
  const [clientes, setClientes] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [aplicaciones, setAplicaciones] = useState([]);
  const [cargando, setCargando] = useState(esEdicion);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [nuevaAplicacion, setNuevaAplicacion] = useState({ factura_id: "", importe: "" });

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
    obtenerRecibo(reciboId)
      .then((r) => {
        setDatos({
          cliente_id: String(r.cliente_id),
          fecha: r.fecha,
          numero: r.numero,
          importe: r.importe,
          forma_pago: r.forma_pago,
        });
        cargarFacturas(r.cliente_id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [reciboId, esEdicion]);

  useEffect(() => {
    if (!esEdicion || !datos.cliente_id) return;
    cargarFacturas(datos.cliente_id);
  }, [datos.cliente_id, esEdicion]);

  const cargarAplicaciones = async () => {
    if (!reciboId) return;
    try {
      const apps = await listarAplicaciones(reciboId);
      setAplicaciones(apps);
    } catch {
      setAplicaciones([]);
    }
  };

  useEffect(() => {
    cargarAplicaciones();
  }, [reciboId]);

  const set = (campo) => (e) => setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const setApp = (campo) => (e) =>
    setNuevaAplicacion((a) => ({ ...a, [campo]: e.target.value }));

  const importeAplicado = aplicaciones.reduce((s, a) => s + a.importe, 0);
  const libre = Number(datos.importe || 0) - importeAplicado;

  const guardar = async () => {
    const cuerpo = aPayload(datos);
    return esEdicion
      ? await actualizarRecibo(reciboId, cuerpo)
      : await crearRecibo(cuerpo);
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
      setError(`El recibo solo tiene $${libre.toFixed(2)} sin aplicar`);
      return;
    }
    setError("");
    try {
      await aplicarRecibo(reciboId, {
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
    if (!window.confirm("¿Quitar esta aplicación?")) return;
    try {
      await desaplicarRecibo(appId);
      await cargarAplicaciones();
    } catch (e2) {
      setError(e2.message);
    }
  };

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">Recibos</span>
      <h1>{esEdicion ? "Modificar recibo" : "Nuevo recibo"}</h1>
      <p className="lead">
        Los campos con <span style={{ color: "var(--accent-3)" }}>*</span> son
        obligatorios. El número se rellena solo a 8 dígitos.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={enviar}>
        <fieldset className="fieldset">
          <legend>Recibo</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Cliente <b className="obligatorio">*</b>
              </span>
              <select value={datos.cliente_id} onChange={set("cliente_id")}>
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

            <label className="campo">
              <span>
                Número <b className="obligatorio">*</b>
              </span>
              <input
                value={datos.numero}
                onChange={set("numero")}
                placeholder="00000001"
              />
            </label>

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

            <label className="campo">
              <span>
                Forma de pago <b className="obligatorio">*</b>
              </span>
              <select value={datos.forma_pago} onChange={set("forma_pago")}>
                {Object.entries(FORMAS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        {esEdicion && (
          <>
            <fieldset className="fieldset">
              <legend>
                Aplicar a facturas <small>(pendientes o parciales del cliente)</small>
              </legend>
              <p className="nota">
                Importe del recibo: <b>{Number(datos.importe || 0).toFixed(2)}</b> ·
                Ya aplicado: <b>{importeAplicado.toFixed(2)}</b> ·
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
                      <option value="">Elegí factura a pagar…</option>
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
                      + Aplicar
                    </button>
                  </form>

                  {aplicaciones.length > 0 && (
                    <div className="tabla-envoltura">
                      <table className="tabla">
                        <thead>
                          <tr>
                            <th>Factura</th>
                            <th>Concepto</th>
                            <th className="derecha">Importe aplicado</th>
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