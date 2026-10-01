import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import {
  obtenerEstadoDeuda,
  exportarEstadoDeuda,
} from "../api/informes.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

export default function EstadoDeuda({ ir }) {
  const [clientes, setClientes] = useState([]);
  const [clienteId, setClienteId] = useState("");
  const [filtros, setFiltros] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  const cargar = async () => {
    if (!clienteId) return;
    setCargando(true);
    setError("");
    try {
      const data = await obtenerEstadoDeuda({
        cliente_id: Number(clienteId),
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
      });
      setData(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (clienteId) {
      cargar();
    } else {
      setData(null);
    }
  }, [clienteId, filtros.desde, filtros.hasta]);

  const cambiarFiltro = (k) => (e) => setFiltros({ ...filtros, [k]: e.target.value });

  const limpiarFiltros = () => setFiltros({ desde: "", hasta: "" });

  const exportar = async () => {
    if (!clienteId) return;
    try {
      await exportarEstadoDeuda({
        cliente_id: Number(clienteId),
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
      });
    } catch (e) {
      setError(e.message);
    }
  };

  const clienteSel = clientes.find((c) => c.id === Number(clienteId));

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Estado de deuda total</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Estado de deuda total</h1>
      <p className="lead">
        Facturas, notas de crédito y notas de débito pendientes de pago.
        Filtrá por cliente y rango de fechas.
      </p>

      <form className="buscador" onSubmit={(e) => { e.preventDefault(); if (clienteId) cargar(); }}>
        <select
          value={clienteId}
          onChange={(e) => { setClienteId(e.target.value); cargar(); }}
          aria-label="Cliente"
        >
          <option value="">— Seleccionar cliente —</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre_completo}
            </option>
          ))}
        </select>

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiarFiltro("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiarFiltro("hasta")} />
        </label>

        <button className="btn btn-sm" type="submit">Filtrar</button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiarFiltros}>Limpiar</button>
      </form>

      {clienteId && (
        <div className="buscador">
          <button className="btn btn-sm" onClick={exportar} disabled={cargando || !data}>
            Descargar Excel
          </button>
          <button className="btn btn-sm fantasma" onClick={() => window.print()}>Imprimir</button>
          <button className="btn btn-sm fantasma" onClick={() => ir("cliente-ficha", clienteId)}>Ver ficha</button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {clienteSel && data && (
        <>
          {/* Cabecera del cliente */}
          <div className="panel cc-cabecera" style={{ marginBottom: "1.5rem" }}>
            <div>
              <h3>{clienteSel.nombre_completo}</h3>
              <p className="nota">
                {clienteSel.tipo_persona === "juridica" ? "Persona jurídica" : "Persona física"} ·
                CUIT: {clienteSel.cuit || "—"} · DNI: {clienteSel.dni || "—"}
              </p>
            </div>
            <div className="cc-datos">
              <div><b>Condición IVA:</b> {clienteSel.tipo_actividad.replace(/_/g, " ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}</div>
              <div><b>Email:</b> {clienteSel.email || "—"}</div>
              <div><b>Teléfono:</b> {[clienteSel.cod_area, clienteSel.telefono].filter(Boolean).join(" ") || "—"}</div>
            </div>
          </div>

          {/* Resumen por tipo */}
          <div className="panel" style={{ marginBottom: "1.5rem" }}>
            <h3>Resumen por tipo de comprobante</h3>
            <div className="tabla-envoltura">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th className="derecha">Cantidad</th>
                    <th className="derecha">Total</th>
                    <th className="derecha">Pendiente</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.resumen).map(([tipo, r]) => (
                    <tr key={tipo}>
                      <td>{tipo}</td>
                      <td className="mono derecha">{r.cantidad}</td>
                      <td className="mono derecha"><b>{pesos(r.total)}</b></td>
                      <td className="mono derecha"><b>{pesos(r.pendiente)}</b></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td><b>TOTALES</b></td>
                    <td className="mono derecha"><b>{data.cantidad_total}</b></td>
                    <td className="mono derecha"><b>{pesos(data.total_general)}</b></td>
                    <td className="mono derecha"><b>{pesos(data.pendiente_general)}</b></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Detalle */}
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>P.V.</th>
                  <th>Número</th>
                  <th>Cliente</th>
                  <th>Concepto</th>
                  <th className="derecha">Importe</th>
                  <th className="derecha">Pendiente</th>
                  <th>Estado</th>
                  <th>Vencimiento</th>
                </tr>
              </thead>
              <tbody>
                {cargando ? (
                  <tr><td colSpan="10" className="vacio">Cargando…</td></tr>
                ) : data.items.length === 0 ? (
                  <tr><td colSpan="10" className="vacio">No hay comprobantes pendientes en el período seleccionado.</td></tr>
                ) : (
                  data.items.map((m) => (
                    <tr key={`${m.fecha}-${m.tipo}-${m.punto_venta}-${m.numero}`}>
                      <td className="mono">{fecha(m.fecha)}</td>
                      <td>{m.tipo}</td>
                      <td className="mono">{m.punto_venta}</td>
                      <td className="mono">{m.numero}</td>
                      <td>{m.cliente}</td>
                      <td>{m.concepto}</td>
                      <td className="mono derecha">{pesos(m.importe)}</td>
                      <td className="mono derecha"><b>{pesos(m.pendiente)}</b></td>
                      <td><span className={`chip ${m.estado.toLowerCase()}`}>{m.estado}</span></td>
                      <td className="mono">{m.fecha_vencimiento ? fecha(m.fecha_vencimiento) : "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="6"><b>TOTALES</b></td>
                  <td className="mono derecha"><b>{pesos(data.total_general)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.pendiente_general)}</b></td>
                  <td colSpan="2"></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="nota">Pendiente total: <b>{pesos(data.pendiente_general)}</b></p>
        </>
      )}

      {!clienteId && (
        <div className="panel">
          <p className="lista-vacia">Seleccioná un cliente para ver su estado de deuda.</p>
        </div>
      )}

      <style jsx>{`
        .cc-cabecera {
          display: flex;
          flex-wrap: wrap;
          gap: 2rem;
          margin-bottom: 1rem;
          padding-bottom: 1rem;
          border-bottom: 1px solid var(--line);
        }
        .cc-cabecera h3 { margin: 0 0 0.3rem; }
        .cc-datos { display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 0.85rem; color: var(--muted); }
        .cc-datos b { color: var(--text); }
        @media print {
          .buscador { display: none !important; }
          .solo-impresion { display: block; border-bottom: 2px solid #000; padding-bottom: 0.4rem; margin-bottom: 1.2rem; }
          .solo-impresion b { display: block; font-size: 1.25rem; letter-spacing: 0.06em; color: #000; }
        }
      `}</style>
    </section>
  );
}