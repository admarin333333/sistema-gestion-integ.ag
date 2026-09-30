import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { descargar } from "../api/client.js";
import { listarClientes } from "../api/clientes.js";
import {
  ESTADOS,
  TIPOS,
  anularFactura,
  eliminarFactura,
  enviarFacturas,
  listarFacturas,
  query,
  reabrirFactura,
  totalFacturas,
} from "../api/facturas.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIOS = { cliente_id: "", estado: "", desde: "", hasta: "" };

export default function Facturas({ ir, aviso }) {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [lista, setLista] = useState([]);
  const [total, setTotal] = useState(0);
  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [tildadas, setTildadas] = useState([]);
  const [avisos, setAvisos] = useState([]);

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      const [items, suma] = await Promise.all([listarFacturas(f), totalFacturas(f)]);
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
    setTildadas([]);
    cargar(filtros);
  };

  const limpiar = () => {
    setFiltros(VACIOS);
    setTildadas([]);
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

  // qué cubre este listado (se imprime arriba de todo)
  const alcance = [
    filtros.cliente_id && `Cliente: ${nombreCliente(filtros.cliente_id)}`,
    filtros.estado && ESTADOS[filtros.estado],
    filtros.desde && `Desde: ${fecha(filtros.desde)}`,
    filtros.hasta && `Hasta: ${fecha(filtros.hasta)}`,
  ]
    .filter(Boolean)
    .join(" · ");

  const borrar = (f) => {
    if (window.confirm(`¿Eliminar la factura ${f.numero}?`)) {
      hacer(() => eliminarFactura(f.id));
    }
  };

  // lo que hay que contarle al usuario (todo junto en un solo cartel)
  const mensajes = [aviso, ...avisos, error].filter(Boolean).join(" · ");

  // ------------------------------------------------------------- envío mail
  const tildar = (id) =>
    setTildadas((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const tildarTodas = (e) =>
    setTildadas(e.target.checked ? lista.map((f) => f.id) : []);

  /** Manda las que se le pasen. Lo que no sale queda en el cartel rojo. */
  const enviar = async (ids) => {
    if (!ids.length) {
      setError("Tildá al menos una factura para enviarla.");
      return;
    }
    setError("");
    setAvisos([]);
    try {
      const r = await enviarFacturas(ids);
      setAvisos(r.avisos);
      setTildadas([]);
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de facturas{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Facturas</span>
      <h1>Comprobantes emitidos</h1>
      <p className="lead">
        Filtrá por <b>cliente</b>, <b>estado</b> o <b>período</b>. El total de
        abajo lo calcula la base de datos, no el navegador.
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

        <select aria-label="Estado" value={filtros.estado} onChange={cambiar("estado")}>
          <option value="">Cualquier estado</option>
          {Object.entries(ESTADOS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
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
        <button className="btn btn-sm" onClick={() => ir("factura-alta")}>
          + Nueva factura
        </button>
        <button
          className="btn btn-sm"
          disabled={tildadas.length === 0}
          onClick={() => enviar(tildadas)}
        >
          Enviar por mail{tildadas.length ? ` (${tildadas.length})` : ""}
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => bajar(`/facturas/export.xlsx${query(filtros)}`)}
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
              <th className="col-tilde">
                <input
                  type="checkbox"
                  aria-label="Tildar todas"
                  checked={
                    lista.length > 0 && lista.every((f) => tildadas.includes(f.id))
                  }
                  onChange={tildarTodas}
                />
              </th>
              <th>Fecha</th>
              <th>Comprobante</th>
              <th>Número</th>
              <th>Cliente</th>
              <th>Concepto</th>
              <th className="derecha">Importe</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="9" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="9" className="vacio">
                  No hay comprobantes con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((f) => (
                <tr key={f.id}>
                  <td className="col-tilde">
                    <input
                      type="checkbox"
                      aria-label={`Tildar factura ${f.numero}`}
                      checked={tildadas.includes(f.id)}
                      onChange={() => tildar(f.id)}
                    />
                  </td>
                  <td className="mono">{fecha(f.fecha)}</td>
                  <td>
                    {TIPOS[f.tipo_comprobante]}
                    <small>PV {f.punto_venta}</small>
                  </td>
                  <td className="mono">{f.numero}</td>
                  <td>
                    <b>{f.cliente_nombre}</b>
                  </td>
                  <td>{f.concepto || "—"}</td>
                  <td className="mono derecha">{pesos(f.importe)}</td>
                  <td>
                    <span className={`chip ${f.estado}`}>{ESTADOS[f.estado]}</span>
                    {f.fecha_envio && <span className="chip enviada">Enviado</span>}
                  </td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => ir("factura-editar", f.id)}
                    >
                      Editar
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => bajar(`/facturas/${f.id}/pdf`)}
                    >
                      PDF
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => enviar([f.id])}
                    >
                      {f.fecha_envio ? "Reenviar" : "Enviar"}
                    </button>
                    {esAdmin && f.estado !== "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => anularFactura(f.id))}
                      >
                        Anular
                      </button>
                    )}
                    {esAdmin && f.estado === "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => reabrirFactura(f.id))}
                      >
                        Reabrir
                      </button>
                    )}
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(f)}
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
              <td className="col-tilde"></td>
              <td colSpan="5">
                <b>TOTAL</b>
              </td>
              <td className="mono derecha">
                <b>{pesos(total)}</b>
              </td>
              <td colSpan="2"></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} comprobante${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}
