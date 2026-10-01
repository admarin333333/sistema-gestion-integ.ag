import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { descargar } from "../api/client.js";
import { listarClientes } from "../api/clientes.js";
import {
  FORMAS,
  ESTADOS,
  listarRecibos,
  totalRecibos,
  eliminarRecibo,
  anularRecibo,
  reabrirRecibo,
  query,
} from "../api/recibos.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIOS = { cliente_id: "", desde: "", hasta: "" };

export default function Recibos({ ir, aviso }) {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [lista, setLista] = useState([]);
  const [total, setTotal] = useState(0);
  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      const [items, suma] = await Promise.all([listarRecibos(f), totalRecibos(f)]);
      setLista(items);
      setTotal(suma.total);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar(VACIOS);
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cambiar = (k) => (e) => setFiltros({ ...filtros, [k]: e.target.value });

  const buscar = (e) => {
    e.preventDefault();
    cargar(filtros);
  };

  const limpiar = () => {
    setFiltros(VACIOS);
    cargar(VACIOS);
  };

  const hacer = async (fn) => {
    try {
      await fn();
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  const bajar = async (ruta) => {
    try {
      await descargar(ruta);
    } catch (e) {
      setError(e.message);
    }
  };

  const nombreCliente = (id) => {
    const c = clientes.find((x) => x.id === Number(id));
    return c ? c.nombre_completo : "";
  };

  const alcance = [
    filtros.cliente_id && `Cliente: ${nombreCliente(filtros.cliente_id)}`,
    filtros.desde && `Desde: ${fecha(filtros.desde)}`,
    filtros.hasta && `Hasta: ${fecha(filtros.hasta)}`,
  ]
    .filter(Boolean)
    .join(" · ");

  const borrar = (r) => {
    if (window.confirm(`¿Eliminar el recibo ${r.numero}?`)) {
      hacer(() => eliminarRecibo(r.id));
    }
  };

  const anular = (r) => {
    if (window.confirm(`¿Anular el recibo ${r.numero}? Se desaplicarán sus aplicaciones.`)) {
      hacer(() => anularRecibo(r.id));
    }
  };

  const reabrir = (r) => {
    if (window.confirm(`¿Reabrir el recibo anulado ${r.numero}?`)) {
      hacer(() => reabrirRecibo(r.id));
    }
  };

  const mensajes = [aviso, error].filter(Boolean).join(" · ");

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de recibos{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Recibos</span>
      <h1>Recibos emitidos</h1>
      <p className="lead">
        Filtrá por <b>cliente</b> o <b>período</b>. El total de abajo lo calcula la base de datos.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <select
          aria-label="Cliente"
          value={filtros.cliente_id}
          onChange={cambiar("cliente_id")}
        >
          <option value="">Todos los clientes</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre_completo}
            </option>
          ))}
        </select>

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>

        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiar}>
          Limpiar
        </button>
      </form>

      <div className="buscador">
        <button className="btn btn-sm" onClick={() => ir("recibo-alta")}>
          + Nuevo recibo
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => bajar(`/recibos/export.xlsx${query(filtros)}`)}
        >
          Descargar Excel
        </button>
        <button className="btn btn-sm fantasma" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>

      {mensajes && <p className="error">{mensajes}</p>}
      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Número</th>
              <th>Cliente</th>
              <th>Forma de pago</th>
              <th className="derecha">Importe</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="7" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="7" className="vacio">
                  No hay recibos con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{fecha(r.fecha)}</td>
                  <td className="mono">{r.numero}</td>
                  <td>
                    <b>{r.cliente_nombre}</b>
                  </td>
                  <td>{FORMAS[r.forma_pago] || r.forma_pago}</td>
                  <td className="mono derecha">{pesos(r.importe)}</td>
                  <td>
                    <span className={`chip ${r.estado}`}>{ESTADOS[r.estado] || r.estado}</span>
                  </td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => ir("recibo-editar", r.id)}
                    >
                      Editar
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => bajar(`/recibos/${r.id}/pdf`)}
                    >
                      PDF
                    </button>
                    {esAdmin && r.estado === "emitido" && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => anular(r)}
                      >
                        Anular
                      </button>
                    )}
                    {esAdmin && r.estado === "anulado" && (
                      <button
                        className="btn btn-sm"
                        onClick={() => reabrir(r)}
                      >
                        Reabrir
                      </button>
                    )}
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(r)}
                      >
                        Borrar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>

          <tfoot>
            <tr>
              <td colSpan="5"><b>TOTAL</b></td>
              <td className="mono derecha"><b>{pesos(total)}</b></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} recibo${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}