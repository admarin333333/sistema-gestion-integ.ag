import { useEffect, useState } from "react";
import { obtenerResultados, exportarResultados } from "../api/informes.js";
import Periodo from "../components/Periodo.jsx";
import Variantes from "../components/Variantes.jsx";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIO = { desde: "", hasta: "" };

/** Un bloque del estado de resultado: sus grupos, sus cuentas y el total. */
function Bloque({ titulo, grupos, total, cantidad, signo }) {
  return (
    <>
      <h2 className="centro-titulo" style={{ marginTop: "2.2rem" }}>
        {titulo}
        <b className="centro-total">
          {/* El "−" dice que este bloque se resta del neto. Con el bloque en
              cero no se pone: "−0,00" parece un número raro y no agrega nada. */}
          {signo === "-" && Math.abs(total) > 0.004 ? "− " : ""}
          {pesos(total)}
        </b>
      </h2>

      {cantidad === 0 && (
        <p className="nota">
          Sin movimientos en el período. Si cargaste documentos y esto está en
          cero, es que todavía no están en un asiento contabilizado: el informe
          muestra los libros.
        </p>
      )}

      {cantidad > 0 && (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Grupo</th>
                <th>Cuenta</th>
                <th className="derecha">Movimientos</th>
                <th className="derecha">Total</th>
              </tr>
            </thead>
            <tbody>
              {grupos.map((g) => (
                <FragmentoGrupo key={g.id} g={g} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/** Un grupo y sus cuentas. Las cuentas en cero no se muestran: si un grupo
 *  tiene 12 cuentas y solo dos con movimiento, listar las doce esconde lo que
 *  importa. */
function FragmentoGrupo({ g }) {
  const conMovimiento = g.cuentas.filter((k) => k.cantidad_movimientos > 0);
  if (conMovimiento.length === 0) {
    return (
      <tr>
        <td className="mono">{g.codigo}</td>
        <td>
          <b>{g.nombre}</b>
        </td>
        <td colSpan="2" className="vacio">
          Sin movimientos
        </td>
        <td className="mono derecha">
          <b>{pesos(0)}</b>
        </td>
      </tr>
    );
  }
  return (
    <>
      {conMovimiento.map((k, n) => (
        <tr key={k.id}>
          <td className="mono">{k.codigo}</td>
          <td>{n === 0 ? <b>{g.nombre}</b> : ""}</td>
          <td>{k.nombre}</td>
          <td className="mono derecha">{k.cantidad_movimientos}</td>
          <td className="mono derecha">
            {pesos(k.total)}
          </td>
        </tr>
      ))}
      <tr className="fila-subtotal">
        <td className="mono">{g.codigo}</td>
        <td colSpan="2">
          <b>Total {g.nombre}</b>
        </td>
        <td className="mono derecha">
          <b>{g.cantidad_movimientos}</b>
        </td>
        <td className="mono derecha">
          <b>{pesos(g.total)}</b>
        </td>
      </tr>
    </>
  );
}

export default function InformeResultados() {
  const [filtros, setFiltros] = useState(VACIO);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      setDatos(await obtenerResultados(f));
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

  const negativo = datos && datos.neto < 0;

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de resultados — {alcance}</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Informe de resultados</h1>
      <p className="lead">
        Los tres lados salen de los <b>asientos contabilizados</b>:{" "}
        <b>ingresos</b> (rama 4 del plan) − <b>costos</b> (rama 5) −{" "}
        <b>gastos</b> (rama 6) = <b>neto</b>. El gasto es el mismo número que
        muestra el informe por centro de costos.
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
          onClick={() => exportarResultados(filtros)}
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
        pantalla="informe-resultados"
        filtros={filtros}
        setFiltros={setFiltros}
        onCargar={cargar}
      />

      {error && <p className="error">{error}</p>}
      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && datos && (
        <>
          <Bloque
            titulo="Ingresos"
            grupos={datos.ingresos.grupos}
            total={datos.ingresos.total}
            cantidad={datos.ingresos.cantidad}
          />

          <Bloque
            titulo="Costos"
            grupos={datos.costos.grupos}
            total={datos.total_costos}
            cantidad={datos.costos.cantidad}
            signo="-"
          />

          <Bloque
            titulo="Gastos"
            grupos={datos.centros}
            total={datos.total_gastos}
            cantidad={datos.centros.reduce(
              (s, c) => s + c.cantidad_movimientos,
              0
            )}
            signo="-"
          />

          {/* NETO */}
          <div className="tabla-envoltura" style={{ marginTop: "2.5rem" }}>
            <table className="tabla">
              <tbody>
                <tr>
                  <td>
                    <h2 style={{ margin: 0 }}>NETO DEL PERÍODO</h2>
                    <small>
                      Ingresos {pesos(datos.ingresos.total)} − costos{" "}
                      {pesos(datos.total_costos)} − gastos{" "}
                      {pesos(datos.total_gastos)}
                    </small>
                  </td>
                  <td
                    className="mono derecha"
                    style={{
                      fontSize: "1.4rem",
                      color: negativo ? "var(--accent-3)" : undefined,
                    }}
                  >
                    <b>{pesos(datos.neto)}</b>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* BIENES */}
          <h2 style={{ marginTop: "2.5rem" }}>Bienes</h2>
          <p className="nota">
            Cuentas de balance — no afectan el neto del período.
          </p>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>N°</th>
                  <th>Bien</th>
                  <th className="derecha">Importe</th>
                  <th>Observación</th>
                </tr>
              </thead>
              <tbody>
                {datos.bienes.map((b) => (
                  <tr key={b.n}>
                    <td className="mono">{b.n}</td>
                    <td>
                      <b>{b.nombre}</b>
                    </td>
                    <td className="mono derecha">—</td>
                    <td>{b.nota}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="nota" style={{ marginTop: "1.5rem" }}>
            <b>{alcance}</b>
          </p>
        </>
      )}
    </section>
  );
}
