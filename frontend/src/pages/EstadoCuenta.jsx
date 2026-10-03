import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listarClientes } from "../api/clientes.js";
import {
  obtenerCuentaCorriente,
  exportarCuentaCorriente,
} from "../api/cuentaCorriente.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

export default function EstadoCuenta() {
  const navigate = useNavigate();
  const [clientes, setClientes] = useState([]);
  const [clienteId, setClienteId] = useState("");
  const [filtros, setFiltros] = useState({ desde: "", hasta: "" });
  const [cc, setCc] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  const cargar = async (filtrosActuales = filtros) => {
    if (!clienteId) return;
    setCargando(true);
    setError("");
    try {
      const data = await obtenerCuentaCorriente(Number(clienteId), filtrosActuales);
      console.log('Datos recibidos:', data);
      setCc(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (clienteId) {
      console.log('Cargando cuenta corriente para cliente:', clienteId, 'filtros:', filtros);
      cargar();
    } else {
      setCc(null);
    }
  }, [clienteId, filtros]);

  const cambiarFiltro = (k) => (e) => {
    // Validar que la fecha tenga formato YYYY-MM-DD
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
      await exportarCuentaCorriente(Number(clienteId), filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  const clienteSel = clientes.find((c) => c.id === Number(clienteId));

  const tel = clienteSel
    ? [clienteSel.cod_area, clienteSel.telefono].filter(Boolean).join(" ")
    : "";

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Estado de cuenta</span>
      </div>

      <span className="kicker">Cuenta corriente</span>
      <h1>Estado de cuenta</h1>
      <p className="lead">
        Elegí un cliente y un rango de fechas. El saldo se calcula en la base de datos.
      </p>

      <form className="buscador" onSubmit={(e) => { e.preventDefault(); if (clienteId) cargar(filtros); }}>
        <BuscadorCliente
          clientes={clientes}
          seleccion={clienteSel}
          onElegir={(c) => setClienteId(c ? String(c.id) : "")}
        />

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
          <button className="btn btn-sm" onClick={exportar} disabled={cargando || !cc}>
            Descargar Excel
          </button>
          <button className="btn btn-sm fantasma" onClick={() => window.print()}>Imprimir</button>
          <button className="btn btn-sm fantasma" onClick={() => navigate(`/cliente-ficha/${clienteId}`)}>Ver ficha</button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {clienteSel && cc && (
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
              <div><b>Teléfono:</b> {tel || "—"}</div>
            </div>
          </div>

          {/* Tabla movimientos */}
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Concepto</th>
                  <th className="derecha">DEBE</th>
                  <th className="derecha">HABER</th>
                  <th className="derecha">SALDO</th>
                </tr>
              </thead>
              <tbody>
                {cargando ? (
                  <tr><td colSpan="5" className="vacio">Cargando…</td></tr>
                ) : cc.movimientos.length === 0 ? (
                  <tr><td colSpan="5" className="vacio">No hay movimientos en el período seleccionado.</td></tr>
                ) : (
                  cc.movimientos.map((m) => (
                    <tr key={`${m.fecha}-${m.concepto}`}>
                      <td className="mono">{fecha(m.fecha)}</td>
                      <td>{m.concepto}</td>
                      <td className="mono derecha">{m.debe ? pesos(m.debe) : "—"}</td>
                      <td className="mono derecha">{m.haber ? pesos(m.haber) : "—"}</td>
                      <td className="mono derecha"><b>{pesos(m.saldo)}</b></td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="2"><b>TOTALES</b></td>
                  <td className="mono derecha"><b>{pesos(cc.total_debe)}</b></td>
                  <td className="mono derecha"><b>{pesos(cc.total_haber)}</b></td>
                  <td className="mono derecha"><b>{pesos(cc.saldo)}</b></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="nota">Saldo final a la fecha: <b>{pesos(cc.saldo)}</b></p>
        </>
      )}
      {clienteSel && !cc && !cargando && (
        <div className="panel">
          <p className="error">Error al cargar el estado de cuenta. Intentá de nuevo.</p>
        </div>
      )}

      {!clienteId && (
        <div className="panel">
          <p className="lista-vacia">Seleccioná un cliente para ver su estado de cuenta.</p>
        </div>
      )}
    </section>
  );
}