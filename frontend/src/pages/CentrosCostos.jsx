import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  listarCentros,
  crearCentro,
  eliminarCentro,
} from "../api/centros.js";
import { NOMBRE_ESTUDIO } from "../formato.js";

export default function CentrosCostos() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [nombre, setNombre] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarCentros());
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const alta = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    setEnviando(true);
    setError("");
    try {
      await crearCentro({ nombre: nombre.trim() });
      setNombre("");
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const borrar = (c) => {
    if (window.confirm(`¿Eliminar el centro ${c.nombre}?`)) {
      eliminarCentro(c.id)
        .then(cargar)
        .catch((e) => setError(e.message));
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Centros de costos</span>
      </div>

      <span className="kicker">Configuración</span>
      <h1>Centros de costos</h1>
      <p className="lead">
        Cada comprobante de compra se imputa a un centro. Sus tipos de gasto
        se eligen desde acá.
      </p>

      <form className="buscador" onSubmit={alta}>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej: Logística…"
          aria-label="Nombre del centro"
          maxLength={50}
          style={{ flex: "2 1 260px" }}
        />
        <button className="btn btn-sm" type="submit" disabled={enviando}>
          + Agregar
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={() => window.print()}>
          Imprimir
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>Nombre</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td colSpan="2" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="2" className="vacio">
                  Todavía no hay centros cargados.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((c) => (
                <tr key={c.id}>
                  <td>
                    <b>{c.nombre}</b>
                  </td>
                  <td className="acciones">
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(c)}
                      >
                        Borrar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} centro${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}
