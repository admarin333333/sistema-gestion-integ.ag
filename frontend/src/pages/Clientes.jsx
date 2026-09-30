import { useEffect, useState } from "react";
import { listarClientes } from "../api/clientes.js";

export default function Clientes({ ir }) {
  const [termino, setTermino] = useState("");
  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (q = "") => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarClientes(q));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const buscar = (e) => {
    e.preventDefault();
    cargar(termino);
  };

  return (
    <section>
      <span className="kicker">Clientes</span>
      <h1>Clientes del estudio</h1>
      <p className="lead">
        Buscá por <b>nombre</b>, <b>DNI</b> o <b>CUIT</b> — el sistema no
        distingue los guiones del CUIT.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <input
          value={termino}
          onChange={(e) => setTermino(e.target.value)}
          placeholder="Ej: Pérez, 26473674 o 20-26473674-2"
          aria-label="Buscar cliente"
        />
        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => {
            setTermino("");
            cargar();
          }}
        >
          Limpiar
        </button>
        <button
          className="btn btn-sm"
          type="button"
          onClick={() => ir("cliente-alta")}
        >
          + Nuevo cliente
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>Cuenta</th>
              <th>Cliente</th>
              <th>CUIT</th>
              <th>DNI</th>
              <th>Localidad</th>
              <th>Servicios</th>
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
                  {termino
                    ? `No hay nadie que coincida con «${termino}».`
                    : "Todavía no hay clientes cargados."}
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.id}</td>
                  <td>
                    <b>{c.nombre_completo}</b>
                    <small>
                      {c.tipo_persona === "juridica"
                        ? "Persona jurídica"
                        : "Persona física"}
                    </small>
                  </td>
                  <td className="mono">{c.cuit || "—"}</td>
                  <td className="mono">{c.dni || "—"}</td>
                  <td>{c.localidad || "—"}</td>
                  <td className="mono">{c.servicios.length}</td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm"
                      onClick={() => ir("cliente-ficha", c.id)}
                    >
                      Ficha
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => ir("cliente-editar", c.id)}
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <p className="nota">
        {cargando ? "" : `${lista.length} cliente${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}
