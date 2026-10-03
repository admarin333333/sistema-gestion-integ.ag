import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useNavigate, useLocation } from "react-router-dom";
import { descargar } from "../api/client.js";
import { listarClientes } from "../api/clientes.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import {
  ESTADOS,
  listarAnticipos,
  exportarExcel,
  exportarPdf,
  eliminarAnticipo,
  query,
} from "../api/anticipos.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIOS = { cliente_id: "", desde: "", hasta: "" };

export default function Anticipos() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const aviso = location.state?.aviso;
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [lista, setLista] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarAnticipos(f));
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

  // El cliente elegido en el buscador, para que el campo muestre su nombre.
  const clienteFiltro = clientes.find(
    (c) => String(c.id) === String(filtros.cliente_id)
  );

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

  const bajar = async (fn) => {
    try {
      await fn();
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

  const borrar = (a) => {
    if (window.confirm(`¿Eliminar el anticipo ${a.numero}?`)) {
      hacer(() => eliminarAnticipo(a.id));
    }
  };

  const mensajes = [aviso, error].filter(Boolean).join(" · ");

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de anticipos{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Anticipos</span>
      <h1>Anticipos de clientes</h1>
      <p className="lead">
        Filtrá por <b>cliente</b> o <b>período</b>. El total de abajo lo calcula la base de datos.
      </p>

      <form className="buscador" onSubmit={buscar}>
        {/* Buscador y no lista desplegada: se escribe y filtra al toque. */}
        <BuscadorCliente
          clientes={clientes}
          seleccion={clienteFiltro || null}
          onElegir={(c) =>
            setFiltros({ ...filtros, cliente_id: c ? String(c.id) : "" })
          }
          tipo_registro="cliente"
          etiqueta="Cliente"
          placeholder="Todos los clientes — escribí para filtrar"
        />

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
        <button className="btn btn-sm" onClick={() => navigate("/anticipo-alta")}>
          + Nuevo anticipo
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => bajar(() => exportarExcel(filtros))}
        >
          Descargar Excel
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => bajar(() => exportarPdf(filtros))}
        >
          Descargar PDF
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
              <th className="derecha">Importe</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="6" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="6" className="vacio">
                  No hay anticipos con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{fecha(a.fecha)}</td>
                  <td className="mono">{a.numero}</td>
                  <td>
                    <b>{a.cliente_nombre}</b>
                  </td>
                  <td className="mono derecha">{pesos(a.importe)}</td>
                  <td>
                    <span className={`chip ${a.estado}`}>{ESTADOS[a.estado] || a.estado}</span>
                  </td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => navigate(`/anticipo-editar/${a.id}`)}
                    >
                      Editar
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => descargar(`/anticipos/${a.id}/pdf`)}
                    >
                      PDF
                    </button>
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(a)}
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
              <td colSpan="4"><b>TOTAL</b></td>
              <td className="mono derecha">
                <b>{pesos(lista.reduce((s, a) => s + a.importe, 0))}</b>
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} anticipo${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}