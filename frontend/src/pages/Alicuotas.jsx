import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  listarAlicuotas,
  crearAlicuota,
  eliminarAlicuota,
} from "../api/alicuotas.js";
import { NOMBRE_ESTUDIO } from "../formato.js";

export default function Alicuotas() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [nombre, setNombre] = useState("");
  const [porcentaje, setPorcentaje] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarAlicuotas());
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
    if (!nombre.trim() || !porcentaje) return;
    setEnviando(true);
    setError("");
    try {
      await crearAlicuota({ nombre: nombre.trim(), porcentaje: Number(porcentaje) });
      setNombre("");
      setPorcentaje("");
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const borrar = (a) => {
    if (window.confirm(`¿Eliminar la alícuota ${a.nombre}?`)) {
      eliminarAlicuota(a.id)
        .then(cargar)
        .catch((e) => setError(e.message));
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Alícuotas de IVA</span>
      </div>

      <span className="kicker">IVA</span>
      <h1>Alícuotas de IVA</h1>
      <p className="lead">
        Catálogo de alícuotas para responsables inscriptos. Se eligen en la
        ficha de cada cliente o proveedor.
      </p>

      <form className="buscador" onSubmit={alta}>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej: IVA 21%"
          aria-label="Nombre de la alícuota"
          maxLength={50}
          style={{ flex: "2 1 260px" }}
        />
        <label className="campo" style={{ flex: "0 0 120px" }}>
          <span>%</span>
          <input
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={porcentaje}
            onChange={(e) => setPorcentaje(e.target.value)}
            placeholder="21"
          />
        </label>
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
              <th className="derecha">Porcentaje</th>
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
                  Todavía no hay alícuotas cargadas.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((a) => (
                <tr key={a.id}>
                  <td>
                    <b>{a.nombre}</b>
                  </td>
                  <td className="mono derecha">{Number(a.porcentaje).toFixed(1)} %</td>
                  <td className="acciones">
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
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} alícuota${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}
