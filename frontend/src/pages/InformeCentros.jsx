import { useEffect, useState } from "react";
import { obtenerCentros, exportarCentros } from "../api/informes.js";
import Periodo from "../components/Periodo.jsx";
import Variantes from "../components/Variantes.jsx";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIO = { desde: "", hasta: "" };

export default function InformeCentros() {
  const [filtros, setFiltros] = useState(VACIO);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      setDatos(await obtenerCentros(f));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar(VACIO);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buscar = (e) => {
    e.preventDefault();
    cargar(filtros);
  };

  const limpiar = () => {
    setFiltros(VACIO);
    cargar(VACIO);
  };

  const alcance =
    datos && (datos.desde || datos.hasta)
      ? `Desde: ${datos.desde ? fecha(datos.desde) : "inicio"} · Hasta: ${
          datos.hasta ? fecha(datos.hasta) : "hoy"
        }`
      : "Período completo";

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe por centro de costos — {alcance}</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Informe por centro de costos</h1>
      <p className="lead">
        Los centros son las cuentas de <b>{datos ? datos.raiz.nombre : "GASTOS"}</b>{" "}
        del plan de cuentas, y los importes se toman de los{" "}
        <b>asientos contabilizados</b>. Cada centro tiene su total.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <Periodo filtros={filtros} setFiltros={setFiltros} />
        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiar}>
          Limpiar
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => exportarCentros(filtros)}
        >
          Descargar Excel
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => window.print()}
        >
          Imprimir
        </button>
      </form>

      <Variantes
        pantalla="informe-centros"
        filtros={filtros}
        setFiltros={setFiltros}
        onCargar={cargar}
      />

      {error && <p className="error">{error}</p>}
      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && datos &&
        datos.centros.map((c) => (
          <div key={c.id} className="centro-costos">
            <h2 className="centro-titulo">
              <span className="mono">{c.codigo}</span> {c.nombre}
              <b className="centro-total">{pesos(c.total)}</b>
            </h2>

            {c.cantidad_movimientos === 0 ? (
              <p className="nota">
                Sin movimientos en el período. Si cargaste un gasto y no aparece,
                es que todavía no está en un asiento contabilizado: el informe
                muestra los libros, no lo que se está por cargar.
              </p>
            ) : (
              <div className="tabla-scroll">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Cuenta de gasto</th>
                      <th className="derecha">Movimientos</th>
                      <th className="derecha">Debe</th>
                      <th className="derecha">Haber</th>
                      <th className="derecha">Total</th>
                    </tr>
                  </thead>

                  <tbody>
                    {c.cuentas.map((k) => (
                      <tr key={k.id}>
                        <td className="mono">{k.codigo}</td>
                        <td>{k.nombre}</td>
                        <td className="mono derecha">
                          {k.cantidad_movimientos || "—"}
                        </td>
                        <td className="mono derecha">{pesos(k.total_debe)}</td>
                        <td className="mono derecha">{pesos(k.total_haber)}</td>
                        <td className="mono derecha">
                          <b>{pesos(k.total)}</b>
                        </td>
                      </tr>
                    ))}
                  </tbody>

                  <tfoot>
                    <tr>
                      <td colSpan="2">
                        <b>Total {c.nombre}</b>
                      </td>
                      <td className="mono derecha">
                        <b>{c.cantidad_movimientos}</b>
                      </td>
                      <td className="mono derecha">
                        <b>{pesos(c.total_debe)}</b>
                      </td>
                      <td className="mono derecha">
                        <b>{pesos(c.total_haber)}</b>
                      </td>
                      <td className="mono derecha">
                        <b>{pesos(c.total)}</b>
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        ))}

      {!cargando && datos && (
        <p className="nota centro-general">
          <b>Total general de gastos: {pesos(datos.total_general)}</b> —{" "}
          {alcance}
        </p>
      )}
    </section>
  );
}
