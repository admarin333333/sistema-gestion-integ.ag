import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { listarCentros } from "../api/centros.js";
import {
  listarTiposGasto,
  crearTipoGasto,
  eliminarTipoGasto,
} from "../api/tiposgasto.js";
import { NOMBRE_ESTUDIO } from "../formato.js";

export default function TiposGastos() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [lista, setLista] = useState([]);
  const [centros, setCentros] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [nombre, setNombre] = useState("");
  const [centroId, setCentroId] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      const [tipos, cs] = await Promise.all([listarTiposGasto(), listarCentros()]);
      setLista(tipos);
      setCentros(cs);
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
    if (!nombre.trim() || !centroId) return;
    setEnviando(true);
    setError("");
    try {
      await crearTipoGasto({ nombre: nombre.trim(), centro_costo_id: Number(centroId) });
      setNombre("");
      setCentroId("");
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const borrar = (t) => {
    if (window.confirm(`¿Eliminar el tipo de gasto ${t.nombre}?`)) {
      eliminarTipoGasto(t.id)
        .then(cargar)
        .catch((e) => setError(e.message));
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Tipos de gasto</span>
      </div>

      <span className="kicker">Configuración</span>
      <h1>Tipos de gasto</h1>
      <p className="lead">
        Cada tipo pertenece a <b>un</b> centro de costos. Al cargar una compra,
        elegido el centro solo se ofrecen sus tipos.
      </p>

      <form className="buscador" onSubmit={alta}>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej: Viáticos…"
          aria-label="Nombre del tipo de gasto"
          maxLength={50}
          style={{ flex: "2 1 260px" }}
        />
        <select
          value={centroId}
          onChange={(e) => setCentroId(e.target.value)}
          aria-label="Centro de costos"
        >
          <option value="">Centro…</option>
          {centros.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
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
              <th>Tipo de gasto</th>
              <th>Centro de costos</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td colSpan="3" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="3" className="vacio">
                  Todavía no hay tipos de gasto cargados.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((t) => (
                <tr key={t.id}>
                  <td>
                    <b>{t.nombre}</b>
                  </td>
                  <td>{t.centro?.nombre || "—"}</td>
                  <td className="acciones">
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(t)}
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
          : `${lista.length} tipo${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}
