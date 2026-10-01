import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import {
  obtenerAnticiposPendientes,
  exportarAnticiposPendientes,
} from "../api/informes.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

export default function AnticiposPendientes({ ir }) {
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
      const data = await obtenerAnticiposPendientes({
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

  const cambiarFiltro = (k) => (e) => {
    const valor = e.target.value;
    if (valor && !/^\d{4}-\d{2}-\d{2}$/.test(valor)) return;
    setFiltros({ ...filtros, [k]: valor });
  };

  const limpiarFiltros = () => {
    const nuevosFiltros = { desde: "", hasta: "" };
    setFiltros(nuevosFiltros);
    if (clienteId) cargar(nuevosFiltros);
  };

  const exportar = async () => {
    if (!clienteId) return;
    try {
      await exportarAnticiposPendientes({
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
        <span>Anticipos pendientes de imputación</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Anticipos pendientes de imputación</h1>
      <p className="lead">
        Anticipos con estado <b>Disponible</b> o <b>Parcial</b> (tienen saldo disponible para imputar).
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

          {/* Resumen */}
          <div className="panel" style={{ marginBottom: "1.5rem" }}>
            <h3>Resumen</h3>
            <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginBottom: "1rem" }}>
              <div><b>Total anticipos:</b> {data.resumen.cantidad}</div>
              <div><b>Total importe:</b> {pesos(data.resumen.total_importe)}</div>
              <div><b>Total imputado:</b> {pesos(data.resumen.total_imputado)}</div>
              <div><b style={{ color: "var(--accent-3)" }}>Total disponible:</b> {pesos(data.resumen.total_disponible)}</div>
            </div>
          </div>

          {/* Detalle */}
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Número</th>
                  <th>Cliente</th>
                  <th className="derecha">Importe</th>
                  <th className="derecha">Imputado</th>
                  <th className="derecha">Disponible</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {cargando ? (
                  <tr><td colSpan="7" className="vacio">Cargando…</td></tr>
                ) : data.items.length === 0 ? (
                  <tr><td colSpan="7" className="vacio">No hay anticipos pendientes en el período seleccionado.</td></tr>
                ) : (
                  data.items.map((a) => (
                    <tr key={a.fecha + a.numero + a.cliente}>
                      <td className="mono">{fecha(a.fecha)}</td>
                      <td className="mono">{a.numero}</td>
                      <td>{a.cliente}</td>
                      <td className="mono derecha">{pesos(a.importe)}</td>
                      <td className="mono derecha">{pesos(a.imputado)}</td>
                      <td className="mono derecha"><b>{pesos(a.disponible)}</b></td>
                      <td><span className={`chip ${a.estado.toLowerCase()}`}>{a.estado}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="3"><b>TOTALES</b></td>
                  <td className="mono derecha"><b>{pesos(data.resumen.total_importe)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.resumen.total_imputado)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.resumen.total_disponible)}</b></td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="nota">Total disponible para imputar: <b>{pesos(data.resumen.total_disponible)}</b></p>
        </>
      )}

      {!clienteId && (
        <div className="panel">
          <p className="lista-vacia">Seleccioná un cliente para ver sus anticipos pendientes.</p>
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