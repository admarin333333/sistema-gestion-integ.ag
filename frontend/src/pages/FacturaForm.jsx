import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import {
  CONDICIONES,
  TIPOS,
  aPayload,
  actualizarFactura,
  crearFactura,
  enviarFacturas,
  obtenerFactura,
} from "../api/facturas.js";

const HOY = new Date().toISOString().slice(0, 10);

const VACIO = {
  cliente_id: "",
  fecha: HOY,
  tipo_comprobante: "factura_b",
  punto_venta: "0001",
  numero: "",
  concepto: "",
  importe: "",
  fecha_vencimiento: "",
  condicion_venta: "contado",
  cae: "",
  cae_vencimiento: "",
};

export default function FacturaForm({ facturaId, onGuardado, onCancelar }) {
  const esEdicion = Boolean(facturaId);
  const [datos, setDatos] = useState(VACIO);
  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(esEdicion);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  useEffect(() => {
    if (!esEdicion) return;
    obtenerFactura(facturaId)
      .then((f) => {
        setDatos({
          cliente_id: String(f.cliente_id),
          fecha: f.fecha,
          tipo_comprobante: f.tipo_comprobante,
          punto_venta: f.punto_venta,
          numero: f.numero,
          concepto: f.concepto || "",
          importe: f.importe,
          fecha_vencimiento: f.fecha_vencimiento || "",
          condicion_venta: f.condicion_venta,
          cae: f.cae || "",
          cae_vencimiento: f.cae_vencimiento || "",
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [facturaId, esEdicion]);

  const set = (campo) => (e) => setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const guardar = async () => {
    const cuerpo = aPayload(datos);
    return esEdicion
      ? await actualizarFactura(facturaId, cuerpo)
      : await crearFactura(cuerpo);
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

  /** Guarda y manda la factura al cliente con el PDF adjunto. */
  const guardarYEnviar = async () => {
    setEnviando(true);
    setError("");
    try {
      const r = await guardar();
      const res = await enviarFacturas([r.id]);
      onGuardado(r, res.avisos.join(" · ") || null);
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">Facturas</span>
      <h1>{esEdicion ? "Modificar factura" : "Nueva factura"}</h1>
      <p className="lead">
        Los campos con <span style={{ color: "var(--accent-3)" }}>*</span> son
        obligatorios. El número se rellena solo: PV de 4 y comprobante de 8.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={enviar}>
        <fieldset className="fieldset">
          <legend>Comprobante</legend>
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
                Tipo <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.tipo_comprobante}
                onChange={set("tipo_comprobante")}
              >
                {Object.entries(TIPOS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Punto de venta <b className="obligatorio">*</b>
              </span>
              <input value={datos.punto_venta} onChange={set("punto_venta")} />
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
                Fecha <b className="obligatorio">*</b>
              </span>
              <input type="date" value={datos.fecha} onChange={set("fecha")} />
            </label>

            <label className="campo">
              <span>Vencimiento</span>
              <input
                type="date"
                value={datos.fecha_vencimiento}
                onChange={set("fecha_vencimiento")}
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
                Condición de venta <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.condicion_venta}
                onChange={set("condicion_venta")}
              >
                {Object.entries(CONDICIONES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <legend>Datos interno</legend>
          <div className="form-grid">
            <label className="campo">
              <span>Concepto</span>
              <input
                value={datos.concepto}
                onChange={set("concepto")}
                placeholder="Honorarios de mes…"
              />
            </label>

            <label className="campo">
              <span>CAE — opcional</span>
              <input value={datos.cae} onChange={set("cae")} />
            </label>

            <label className="campo">
              <span>Vto. CAE — opcional</span>
              <input
                type="date"
                value={datos.cae_vencimiento}
                onChange={set("cae_vencimiento")}
              />
            </label>
          </div>
        </fieldset>

        <div className="form-acciones">
          <button className="btn" type="submit" disabled={enviando}>
            {enviando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Dar de alta"}
          </button>
          <button
            className="btn fantasma"
            type="button"
            disabled={enviando}
            onClick={guardarYEnviar}
          >
            Guardar y enviar por mail
          </button>
          <button className="btn fantasma" type="button" onClick={onCancelar}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}
