import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  listarIndices,
  guardarIndice,
  eliminarIndice,
} from "../api/indicesMoneda.js";
import { fecha, cuatro } from "../formato.js";

export default function IndiceMoneda() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mes, setMes] = useState("");
  const [indice, setIndice] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarIndices());
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
    if (!mes || !indice || Number(indice) <= 0) return;
    setEnviando(true);
    setError("");
    try {
      await guardarIndice({ fecha: `${mes}-01`, indice: Number(indice) });
      setMes("");
      setIndice("");
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const borrar = (i) => {
    if (window.confirm(`¿Eliminar el índice de ${fecha(i.fecha)}?`)) {
      eliminarIndice(i.id)
        .then(cargar)
        .catch((e) => setError(e.message));
    }
  };

  return (
    <section>
      <span className="kicker">Moneda homogénea</span>
      <h1>Índice de moneda homogénea (FACPCE)</h1>
      <p className="lead">
        IPC nacional empalme IPIM, uno por mes. Se carga a mano cuando sale el
        índice nuevo; con estos valores el Balance RT54 calcula el coeficiente
        de actualización.
      </p>

      <form className="buscador" onSubmit={alta}>
        <label className="campo" style={{ flex: "1 1 180px" }}>
          <span>Mes</span>
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            required
          />
        </label>
        <label className="campo" style={{ flex: "1 1 220px" }}>
          <span>Índice</span>
          <input
            type="number"
            min="0"
            step="any"
            value={indice}
            onChange={(e) => setIndice(e.target.value)}
            placeholder="Ej: 12276.766"
            required
          />
        </label>
        <button className="btn btn-sm" type="submit" disabled={enviando}>
          + Agregar
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => window.print()}
        >
          Imprimir
        </button>
      </form>

      <p className="nota">
        Si el mes ya tiene índice, la carga lo corrige. El índice va sin
        signo de pesos: solo el número.
      </p>

      {error && <p className="error">{error}</p>}

      <div className="tabla-envoltura" style={{ maxHeight: "26rem", overflowY: "auto" }}>
        <table className="tabla">
          <thead>
            <tr>
              <th>Mes</th>
              <th className="derecha">Índice</th>
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
                  Todavía no hay índices cargados.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((i) => (
                <tr key={i.id}>
                  <td>{fecha(i.fecha)}</td>
                  <td className="mono derecha">{cuatro(i.indice)}</td>
                  <td className="acciones">
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(i)}
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
          : `${lista.length} mes${lista.length === 1 ? "" : "es"} con índice cargado`}
      </p>
    </section>
  );
}
