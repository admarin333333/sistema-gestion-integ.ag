import { useEffect, useState } from "react";
import {
  obtenerLibroIVA,
  exportarLibroIVA,
} from "../api/informes.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

/**
 * LIBRO DE IVA VENTAS.
 *
 * Qué es: **una línea por comprobante emitido**, en orden correlativo y por día,
 * con el total de cada columna al pie.
 *
 * Sale de las facturas y no de los asientos, al revés que los demás informes. Es
 * a propósito: el libro de IVA registra los **documentos emitidos**, no los
 * movimientos contables. Una factura guardada pero todavía sin contabilizar igual
 * emitió comprobante, y ese IVA hay que pagarlo. Si el libro saliera del libro
 * contable, escondería justamente las facturas que faltan pagar.
 *
 * **Las notas de crédito van en negativo.** El signo lo da el tipo de
 * comprobante, no el importe: las tres familias se guardan con importes
 * positivos. Una nota de crédito suma hacia abajo, una de débito suma hacia
 * arriba (aumenta la deuda del cliente).
 *
 * **La correlativa se reinicia cada día**, que es como la pide el libro: el
 * número de renglón es consecutively dentro de la fecha, no del período. Por eso
 * la columna Nº vuelve a 1 cada día que cambia.
 *
 * Todos los totales y los índices salen del backend. Si el navegador los
 * sumara, el número del pie de la pantalla y el del Excel no coincidirían.
 */
export default function LibroIVA() {
  const [filtros, setFiltros] = useState({
    desde: "",
    hasta: "",
    incluir_anuladas: false,
  });
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f = filtros) => {
    setCargando(true);
    setError("");
    try {
      setData(
        await obtenerLibroIVA({
          desde: f.desde || undefined,
          hasta: f.hasta || undefined,
          incluir_anuladas: f.incluir_anuladas || undefined,
        })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtros.desde, filtros.hasta, filtros.incluir_anuladas]);

  const cambiar = (campo) => (e) =>
    setFiltros({ ...filtros, [campo]: e.target.value });

  const exportar = async () => {
    try {
      await exportarLibroIVA({
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        incluir_anuladas: filtros.incluir_anuladas || undefined,
      });
    } catch (e) {
      setError(e.message);
    }
  };

  const t = data?.totales;

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Libro de IVA Ventas</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Libro de IVA Ventas</h1>
      <p className="lead">
        Una línea por <b>comprobante emitido</b>, en orden correlativo y por día.
        Incluye facturas y notas de crédito y débito. Las notas de crédito van
        en <b>negativo</b>, porque devuelven IVA.
      </p>

      <form className="buscador" onSubmit={(e) => e.preventDefault()}>
        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>

        <label className="campo">
          <span>Anuladas</span>
          <select
            value={filtros.incluir_anuladas ? "ver" : "no"}
            onChange={(e) =>
              setFiltros({
                ...filtros,
                incluir_anuladas: e.target.value === "ver",
              })
            }
          >
            <option value="no">No mostrarlas</option>
            <option value="ver">Mostrar también las anuladas</option>
          </select>
        </label>

        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={exportar}
          disabled={cargando || !data?.cantidad}
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

      {error && <p className="error">{error}</p>}
      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && data && data.cantidad === 0 && (
        <p className="nota">
          No hay comprobantes emitidos en este rango.
        </p>
      )}

      {!cargando && data && data.cantidad > 0 && (
        <>
          {/* Las cuatro cifras del período. El IVA es la que se paga: por eso
              va arriba y no al final. */}
          <div className="panel resumen-deuda">
            <div>
              <span>IVA del período</span>
              <b>{pesos(t.iva)}</b>
              <small>{data.cantidad} comprobante(s)</small>
            </div>
            <div>
              <span>Neto gravado</span>
              <b>{pesos(t.neto)}</b>
              <small>base imponible</small>
            </div>
            <div>
              <span>Percepciones</span>
              <b>{pesos(t.percepcion)}</b>
              <small>IVA que te retuvieron</small>
            </div>
            <div>
              <span>No gravado</span>
              <b>{pesos(t.no_gravado)}</b>
              <small>ingreso sin IVA</small>
            </div>
          </div>

          <div className="tabla-scroll">
            <table className="tabla">
              <thead>
                <tr>
                  <th className="derecha" title="Correlativo del día">Nº</th>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>P. Venta</th>
                  <th>Número</th>
                  <th>Cliente</th>
                  <th className="derecha">Neto</th>
                  <th className="derecha">Alíc. %</th>
                  <th className="derecha">IVA</th>
                  <th className="derecha">Percepción</th>
                  <th className="derecha">No gravado</th>
                  <th className="derecha">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => {
                  const esCredito = i.total < 0;
                  return (
                    <tr key={i.correlativo + "-" + i.numero_completo + "-" + i.fecha}
                        className={esCredito ? "fila-vencida" : ""}>
                      <td className="mono derecha">{i.correlativo}</td>
                      <td className="mono">{fecha(i.fecha)}</td>
                      <td>
                        {i.etiqueta_tipo}
                        {i.estado === "anulada" && (
                          <b className="vencida"> (anulada)</b>
                        )}
                      </td>
                      <td className="mono">{i.punto_venta}</td>
                      <td className="mono">{i.numero}</td>
                      <td>{i.cliente}</td>
                      <td className="mono derecha">{pesos(i.neto)}</td>
                      <td className="mono derecha">
                        {i.alicuota != null ? i.alicuota : "—"}
                      </td>
                      <td className="mono derecha">{pesos(i.iva)}</td>
                      <td className="mono derecha">
                        {i.percepcion ? pesos(i.percepcion) : <span className="vacio">—</span>}
                      </td>
                      <td className="mono derecha">
                        {i.no_gravado ? pesos(i.no_gravado) : <span className="vacio">—</span>}
                      </td>
                      <td className="mono derecha">
                        <b>{pesos(i.total)}</b>
                      </td>
                    </tr>
                  );
                })}
                {/* El total va dentro del tbody, como en el listado de clientes:
                    si queda debajo de la tabla, con muchas líneas se va al
                    final de la página y deja de verse. */}
                <tr className="fila-total">
                  <td colSpan="6">
                    <b>TOTALES</b>
                  </td>
                  <td className="mono derecha"><b>{pesos(t.neto)}</b></td>
                  <td></td>
                  <td className="mono derecha"><b>{pesos(t.iva)}</b></td>
                  <td className="mono derecha"><b>{pesos(t.percepcion)}</b></td>
                  <td className="mono derecha"><b>{pesos(t.no_gravado)}</b></td>
                  <td className="mono derecha"><b>{pesos(t.total)}</b></td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="nota">
            {data.desde ? `Desde ${fecha(data.desde)}` : "Desde el inicio"} ·{" "}
            {data.hasta ? `hasta ${fecha(data.hasta)}` : "hasta hoy"}. La
            columna Nº se reinicia cada día.
          </p>
        </>
      )}
    </section>
  );
}