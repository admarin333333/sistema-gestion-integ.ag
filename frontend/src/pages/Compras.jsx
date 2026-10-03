import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useNavigate } from "react-router-dom";
import { descargar } from "../api/client.js";
import { listarProveedores } from "../api/clientes.js";
import {
  ESTADOS,
  TIPOS,
  anularCompra,
  anularAsientoCompra,
  eliminarCompra,
  generarAsientoCompra,
  listarCompras,
  reabrirCompra,
  totalCompras,
  query,
} from "../api/compras.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";
import Periodo from "../components/Periodo.jsx";
import Variantes from "../components/Variantes.jsx";

const VACIOS = {
  proveedor_id: "",
  desde: "",
  hasta: "",
  sin_asiento: "",
};

/** "true" → true, "" → false. El filtro viene como texto del `<select>`. */
const aBooleano = (v) => v === true || v === "true";

export default function Compras() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [lista, setLista] = useState([]);
  const [total, setTotal] = useState(0);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      // El backend espera un booleano de verdad: si le mandamos el texto
      // "true", FastAPI lo toma como string y el filtro no se aplica (y el
      // total de abajo no cuadra con las filas).
      const params = { ...f, sin_asiento: aBooleano(f.sin_asiento) };
      const [items, suma] = await Promise.all([
        listarCompras(params),
        totalCompras(params),
      ]);
      setLista(items);
      setTotal(suma.total);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar(VACIOS);
    listarProveedores()
      .then(setProveedores)
      .catch(() => setProveedores([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cambiar = (k) => (e) => setFiltros({ ...filtros, [k]: e.target.value });

  const buscar = (e) => {
    e.preventDefault();
    cargar(filtros);
  };

  const limpiar = () => {
    setFiltros(VACIOS);
    cargar(VACIOS);
  };

  const hacer = async (fn) => {
    setError("");
    try {
      await fn();
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  const nombreProveedor = (id) => {
    const p = proveedores.find((x) => x.id === Number(id));
    return p ? p.nombre_completo : "";
  };

  const alcance = [
    filtros.proveedor_id && `Proveedor: ${nombreProveedor(filtros.proveedor_id)}`,
    filtros.desde && `Desde: ${fecha(filtros.desde)}`,
    filtros.hasta && `Hasta: ${fecha(filtros.hasta)}`,
    aBooleano(filtros.sin_asiento) && "Solo sin asentar",
  ]
    .filter(Boolean)
    .join(" · ");

  const borrar = (c) => {
    if (window.confirm(`¿Eliminar el comprobante ${c.numero}?`)) {
      hacer(() => eliminarCompra(c.id));
    }
  };

  const asentar = (c) => {
    if (
      window.confirm(
        "¿Generar el asiento de la compra?\n\n" +
          `Va a debitar ${cuentaGasto(c)} por ${pesos(c.neto)}.\n` +
          "Queda contabilizado con el comprobante FP."
      )
    ) {
      hacer(() => generarAsientoCompra(c.id));
    }
  };

  const anularAsiento = (c) => {
    if (
      window.confirm(
        "¿Anular el asiento?\n\n" +
          "La compra sigue como estaba; solo se da por reverso el asiento."
      )
    ) {
      hacer(() => anularAsientoCompra(c.id));
    }
  };

  /** Cuánto hay SIN asentar dentro de lo que se está viendo. Sale de las filas
   *  ya cargadas, así que siempre cuadra con la lista de arriba. */
  const sinAsentar = lista
    .filter((c) => c.estado !== "anulada" && !c.id_asiento)
    .reduce((s, c) => s + Number(c.total || 0), 0);
  const faltanAsentar = lista.filter(
    (c) => c.estado !== "anulada" && !c.id_asiento
  ).length;

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de compras{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Compras</span>
      <h1>Facturas de proveedores</h1>
      <p className="lead">
        Cada compra elige la <b>cuenta de gasto del plan</b> donde se asienta
        (6.1.03 luz-agua, 6.2.01 publicidad). El centro de costos sale de esa
        cuenta, no se elige aparte.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <select
          aria-label="Proveedor"
          value={filtros.proveedor_id}
          onChange={cambiar("proveedor_id")}
        >
          <option value="">Todos los proveedores</option>
          {proveedores.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre_completo}
            </option>
          ))}
        </select>

        <Periodo filtros={filtros} setFiltros={setFiltros} />

        <label className="campo">
          <span>Asiento</span>
          <select value={filtros.sin_asiento} onChange={cambiar("sin_asiento")}>
            <option value="">Todos</option>
            <option value="true">Solo los que faltan asentar</option>
          </select>
        </label>

        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiar}>
          Limpiar
        </button>
      </form>

      <Variantes
        pantalla="compras"
        filtros={filtros}
        setFiltros={setFiltros}
        onCargar={cargar}
      />

      <div className="buscador">
        <button className="btn btn-sm" onClick={() => navigate("/compra-alta")}>
          + Nueva compra
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => descargar(`/compras/export.xlsx${query(filtros)}`)}
        >
          Descargar Excel
        </button>
        <button className="btn btn-sm fantasma" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {/* El aviso que faltaba: una compra guardada NO mueve la cuenta. Si el
          contador ve compras y el informe por centro en cero, la respuesta
          está acá. */}
      {faltanAsentar > 0 && (
        <p className="aviso-amarillo">
          Hay <b>{faltanAsentar}</b> compra{faltanAsentar === 1 ? "" : "s"} sin
          asentar: {pesos(sinAsentar)} no están todavía en los libros, así que
          tampoco aparecen en el informe por centro de costos. Apretá{" "}
          <b>Asentar</b>.
        </p>
      )}

      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Comprobante</th>
              <th>Número</th>
              <th>Proveedor</th>
              <th>Cuenta de gasto</th>
              <th className="derecha">Neto</th>
              <th className="derecha">IVA</th>
              <th className="derecha">Total</th>
              <th>Asiento</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="11" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="11" className="vacio">
                  No hay comprobantes con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{fecha(c.fecha)}</td>
                  <td>
                    {TIPOS[c.tipo_comprobante]}
                    <small>PV {c.punto_venta}</small>
                  </td>
                  <td className="mono">{c.numero}</td>
                  <td>
                    <b>{c.proveedor_nombre}</b>
                  </td>
                  <td>
                    <span className="mono">
                      {c.cuenta_gasto?.codigo || "—"}
                    </span>{" "}
                    {c.cuenta_gasto?.nombre || "sin cuenta"}
                    <small>{c.centro_nombre}</small>
                  </td>
                  <td className="mono derecha">{pesos(c.neto)}</td>
                  <td className="mono derecha">{pesos(c.iva)}</td>
                  <td className="mono derecha">{pesos(c.total)}</td>
                  <td className="mono">
                    {c.numero_comprobante_asiento ? (
                      <>
                        {c.numero_comprobante_asiento}
                        <small className="nota">
                          {c.estado_asiento === "anulado" ? "anulado" : "contabilizado"}
                        </small>
                      </>
                    ) : (
                      <span className="nota">sin asentar</span>
                    )}
                  </td>
                  <td>
                    <span className={`chip ${c.estado}`}>{ESTADOS[c.estado]}</span>
                  </td>
                  <td className="acciones">
                    {/* Un solo botón para el asiento, según el estado: si no hay
                        se genera; si hay y está vivo se anula. Dos botones que
                        cambian según el estado confundían más de lo que
                        ayudaban (como pasó con los recibos). */}
                    {esAdmin && c.estado !== "anulada" && !c.id_asiento && (
                      <button className="btn btn-sm" onClick={() => asentar(c)}>
                        Asentar
                      </button>
                    )}
                    {esAdmin &&
                      c.id_asiento &&
                      c.estado_asiento !== "anulado" && (
                        <button
                          className="btn btn-sm fantasma"
                          onClick={() => anularAsiento(c)}
                        >
                          Anular asiento
                        </button>
                      )}
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => navigate(`/compra-editar/${c.id}`)}
                    >
                      Editar
                    </button>
                    {esAdmin && c.estado !== "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => anularCompra(c.id))}
                      >
                        Anular
                      </button>
                    )}
                    {esAdmin && c.estado === "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => reabrirCompra(c.id))}
                      >
                        Reabrir
                      </button>
                    )}
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

          <tfoot>
            <tr>
              <td colSpan="8">
                <b>TOTAL</b>
              </td>
              <td className="mono derecha">
                <b>{pesos(total)}</b>
              </td>
              <td colSpan="3"></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} comprobante${lista.length === 1 ? "" : "s"} en el listado`}
      </p>
    </section>
  );
}

/** "6.1.03 luz-agua" — para el texto del confirmador. */
function cuentaGasto(c) {
  if (!c.cuenta_gasto) return "la cuenta de gasto";
  return `${c.cuenta_gasto.codigo} ${c.cuenta_gasto.nombre}`;
}
