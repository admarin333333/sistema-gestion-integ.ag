import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { listarClientes } from "../api/clientes.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import {
  obtenerEstadoDeuda,
  exportarEstadoDeuda,
} from "../api/informes.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

export default function EstadoDeuda() {
  const navigate = useNavigate();
  // El cliente puede venir en la dirección: el botón "Detalle" de la cuenta
  // corriente manda a `/estado-deuda?cliente=7`. Sin esto, el contador llegaba
  // desde la lista y tenía que volver a buscar el cliente a mano.
  const [params] = useSearchParams();
  const clienteDeUrl = params.get("cliente") || "";
  const [clientes, setClientes] = useState([]);
  const [clienteId, setClienteId] = useState(clienteDeUrl);
  const [filtros, setFiltros] = useState({
    desde: "",
    hasta: "",
    // "Solo vencidas" es el caso de uso del día: ir a buscar a los que atrasaron.
    // Con todo mezclado hay que leer la columna de vencimiento fila por fila.
    solo_vencidas: false,
  });
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  // `idQuePedir` existe porque al elegir en el buscador el `setClienteId` todavía
  // no se aplicó: si `cargar` leyera el `clienteId` del cierre, pediría el
  // cliente ANTERIOR y la pantalla mostraría la deuda de otro.
  const cargar = async (idQuePedir = clienteId) => {
    if (!idQuePedir) return;
    setCargando(true);
    setError("");
    try {
      const data = await obtenerEstadoDeuda({
        cliente_id: Number(idQuePedir),
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        solo_vencidas: filtros.solo_vencidas || undefined,
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
  }, [clienteId, filtros.desde, filtros.hasta, filtros.solo_vencidas]);

  const cambiarFiltro = (k) => (e) => setFiltros({ ...filtros, [k]: e.target.value });

  const limpiarFiltros = () =>
    setFiltros({ desde: "", hasta: "", solo_vencidas: false });

  const exportar = async () => {
    if (!clienteId) return;
    try {
      await exportarEstadoDeuda({
        cliente_id: Number(clienteId),
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        solo_vencidas: filtros.solo_vencidas || undefined,
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
        Facturas, notas de crédito y notas de débito pendientes de pago, con lo que ya
        está <b>vencido</b> a la vista. Una factura vence {data?.dias_plazo ?? 7} días
        después de su fecha: es el plazo que usa el sistema.
      </p>

      <form className="buscador" onSubmit={(e) => { e.preventDefault(); if (clienteId) cargar(); }}>
        {/* Buscador, no lista desplegada. Antes era un `<select>` con TODOS los
            clientes: con 40 ya hay que buscarlos scrolleando dentro de la lista,
            y con 400 es imposible. Acá se escribe el nombre (o el CUIT, o el DNI)
            y se filtra al toque. */}
        <BuscadorCliente
          clientes={clientes}
          seleccion={clienteSel || null}
          onElegir={(c) => {
            setClienteId(c ? String(c.id) : "");
            if (c) cargar(String(c.id));
          }}
          tipo_registro="cliente"
          etiqueta="Cliente"
        />

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiarFiltro("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiarFiltro("hasta")} />
        </label>

        <label className="campo">
          <span>Mostrar</span>
          <select
            value={filtros.solo_vencidas ? "vencidas" : "todas"}
            onChange={(e) =>
              setFiltros({ ...filtros, solo_vencidas: e.target.value === "vencidas" })
            }
          >
            <option value="todas">Todas las pendientes</option>
            <option value="vencidas">Solo las vencidas</option>
          </select>
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
          <button className="btn btn-sm fantasma" onClick={() => navigate(`/cliente-ficha/${clienteId}`)}>Ver ficha</button>
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
                  <th className="derecha">Días vencida</th>
                </tr>
              </thead>
              <tbody>
                {cargando ? (
                  <tr><td colSpan="11" className="vacio">Cargando…</td></tr>
                ) : data.items.length === 0 ? (
                  <tr>
                    <td colSpan="11" className="vacio">
                      {filtros.solo_vencidas
                        ? "No hay comprobantes vencidos: está todo al día."
                        : "No hay comprobantes pendientes en el período seleccionado."}
                    </td>
                  </tr>
                ) : (
                  data.items.map((m) => (
                    <tr
                      key={`${m.fecha}-${m.tipo}-${m.punto_venta}-${m.numero}`}
                      className={m.vencido ? "fila-vencida" : ""}
                    >
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
                      <td className="mono derecha">
                        {m.vencido ? (
                          <b className="vencida">{m.dias_vencida}</b>
                        ) : (
                          <span className="vacio">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="6"><b>TOTALES</b></td>
                  <td className="mono derecha"><b>{pesos(data.total_general)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.pendiente_general)}</b></td>
                  <td colSpan="3"></td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Las dos cifras del día, juntas: cuánto le deben en total, y
              cuánto de eso hay que ir a cobrar YA porque venció. */}
          <div className="panel resumen-deuda">
            <div>
              <span>Pendiente total</span>
              <b>{pesos(data.pendiente_general)}</b>
              <small>{data.cantidad_total} comprobante(s)</small>
            </div>
            <div className={data.cantidad_vencida ? "alerta" : ""}>
              <span>Vencido</span>
              <b>{pesos(data.total_vencido)}</b>
              <small>
                {data.cantidad_vencida} de {data.cantidad_total} comprobante(s)
              </small>
            </div>
          </div>
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