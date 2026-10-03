import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  crearServicio,
  eliminarServicio,
  listarServicios,
} from "../api/servicios.js";

/**
 * El CATÁLOGO DE SERVICIOS del estudio.
 *
 * Son los servicios que el estudio ofrece (contabilidad, impositivo,
 * liquidaciones, balances...). Cada cliente elige de esta lista cuáles tiene,
 * así que es una tabla compartida por todos.
 *
 * Por eso el alta es **solo del administrador**: si un operador cargara uno,
 * podría cambiarle el catálogo a todos los clientes.
 *
 * Un servicio con clientes **no se borra**: si desapareciera del catálogo, las
 * fichas de esos clientes quedarían apuntando a algo que ya no existe. Si el
 * estudio deja de ofrecerlo, se deja cargado y no se elige en los clientes
 * nuevos: es la diferencia entre "ya no lo hacemos" y "ese servicio nunca
 * existió".
 */
export default function Servicios() {
  const { user } = useAuth();
  const esAdmin = user?.rol === "admin";

  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  const [nombre, setNombre] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarServicios());
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const alta = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    setEnviando(true);
    setError("");
    setMensaje("");
    try {
      await crearServicio(nombre);
      setNombre("");
      setMensaje(`Se agregó «${nombre.trim()}». Ya se puede elegir en los clientes.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const borrar = (s) => {
    if (
      !window.confirm(
        `¿Borrar el servicio «${s.nombre}»?\n\nSolo se puede si ningún cliente lo tiene asignado.`
      )
    ) {
      return;
    }
    setError("");
    setMensaje("");
    eliminarServicio(s.id)
      .then(async () => {
        setMensaje(`Se borró «${s.nombre}».`);
        await cargar();
      })
      .catch((e) => setError(e.message));
  };

  return (
    <section>
      <span className="kicker">Clientes</span>
      <h1>Servicios</h1>
      <p className="lead">
        Los servicios que ofrece el estudio. Cada cliente elige de esta lista
        cuáles tiene, en su ficha.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="ok">{mensaje}</p>}

      {esAdmin && (
        <form className="buscador" onSubmit={alta}>
          <label className="campo" style={{ flex: "1 1 260px" }}>
            <span>Nuevo servicio</span>
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej: Liquidaciones mensuales"
              maxLength={80}
              required
            />
          </label>
          <button className="btn btn-sm" type="submit" disabled={enviando || !nombre.trim()}>
            {enviando ? "Agregando…" : "+ Agregar"}
          </button>
        </form>
      )}

      {!esAdmin && (
        <p className="nota">
          Solo el administrador puede agregar o borrar servicios. Para cambiar
          los de un cliente, entrá a su ficha.
        </p>
      )}

      <div className="tabla-envoltura" style={{ maxHeight: "30rem", overflowY: "auto" }}>
        <table className="tabla">
          <thead>
            <tr>
              <th style={{ width: "4rem" }}>#</th>
              <th>Servicio</th>
              {esAdmin && <th />}
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td colSpan={esAdmin ? 3 : 2} className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan={esAdmin ? 3 : 2} className="vacio">
                  Todavía no hay servicios cargados.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((s) => (
                <tr key={s.id}>
                  <td className="mono">{s.orden}</td>
                  <td>{s.nombre}</td>
                  {esAdmin && (
                    <td className="acciones">
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(s)}
                      >
                        Borrar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <p className="nota">
        {cargando ? "" : `${lista.length} servicio${lista.length === 1 ? "" : "s"} en el catálogo`}
      </p>
    </section>
  );
}