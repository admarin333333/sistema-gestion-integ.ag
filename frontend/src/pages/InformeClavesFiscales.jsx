import { useEffect, useState } from "react";
import { obtenerClavesFiscales, exportarClavesFiscales } from "../api/informes.js";
import { NOMBRE_ESTUDIO, fecha, fechaHora } from "../formato.js";

const VACIO = { desde: "", hasta: "", terminacion: "" };

/** Columnas por las que se puede ordenar la lista. */
const ORDENES = [
  { id: "nro_cuenta", etiqueta: "Cuenta" },
  { id: "nombre", etiqueta: "Apellido y nombre / Razón social" },
  { id: "cuit", etiqueta: "CUIT" },
  { id: "ultimo_digito", etiqueta: "Terminación del CUIT" },
  { id: "fecha_carga_clave_fiscal", etiqueta: "Fecha de carga de la clave" },
];

// La API devuelve `nombre` (apellido y nombre, o razón social).
const celda = (item) => item.nombre;

export default function InformeClavesFiscales() {
  const [filtros, setFiltros] = useState(VACIO);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [orden, setOrden] = useState("ultimo_digito");
  const [descendente, setDescendente] = useState(false);
  const [verBloques, setVerBloques] = useState(true);

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      setDatos(await obtenerClavesFiscales(f));
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

  const alternarOrden = (columna) => {
    if (orden === columna) {
      setDescendente(!descendente);
    } else {
      setOrden(columna);
      setDescendente(false);
    }
  };

  // El orden se resuelve acá solo para la lista; los totales no se calculan.
  const ordenar = (items) =>
    items.slice().sort((a, b) => {
      const va = orden === "nombre" ? celda(a) : a[orden];
      const vb = orden === "nombre" ? celda(b) : b[orden];
      const cmp = String(va ?? "").localeCompare(String(vb ?? ""), "es", {
        numeric: true,
      });
      return descendente ? -cmp : cmp;
    });

  const columnas = [
    { id: "nro_cuenta", etiqueta: "Cuenta" },
    { id: "nombre", etiqueta: "Apellido y nombre / Razón social" },
    { id: "cuit", etiqueta: "CUIT", mono: true },
    { id: "ultimo_digito", etiqueta: "Termina en", mono: true },
    { id: "clave_fiscal", etiqueta: "Clave fiscal", mono: true },
    { id: "fecha_carga_clave_fiscal", etiqueta: "Cargada el" },
    { id: "fecha_modif_clave_fiscal", etiqueta: "Última modificación" },
    { id: "email", etiqueta: "Email" },
  ];

  const encabezado = (columna) => (
    <th
      key={columna.id}
      className={columna.mono ? "mono" : ""}
      onClick={() => alternarOrden(columna.id)}
      style={{ cursor: "pointer" }}
      title="Ordenar por esta columna"
    >
      {columna.etiqueta}
      {orden === columna.id ? (descendente ? " ▼" : " ▲") : ""}
    </th>
  );

  const fila = (i) => (
    <tr key={i.id}>
      <td className="mono">{i.nro_cuenta}</td>
      <td>{celda(i)}</td>
      <td className="mono">{i.cuit || <span className="vacio">—</span>}</td>
      <td className="mono">
        {i.ultimo_digito || <span className="vacio">—</span>}
      </td>
      <td className="mono">
        {i.clave_fiscal || <span className="vacio">sin cargar</span>}
      </td>
      <td className="mono">
        {i.fecha_carga_clave_fiscal ? fecha(i.fecha_carga_clave_fiscal) : "—"}
      </td>
      <td className="mono">
        {i.fecha_modif_clave_fiscal ? fechaHora(i.fecha_modif_clave_fiscal) : "—"}
      </td>
      <td>{i.email || <span className="vacio">—</span>}</td>
    </tr>
  );

  const alcance =
    datos && (datos.desde || datos.hasta)
      ? `Clave cargada desde ${datos.desde ? fecha(datos.desde) : "inicio"} hasta ${
          datos.hasta ? fecha(datos.hasta) : "hoy"
        }`
      : "Cualquier fecha de carga";

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de CUIT y clave fiscal (ARCA)</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Informe de CUIT y clave fiscal</h1>
      <p className="lead">
        Todos los clientes con su CUIT y la clave fiscal de ARCA. Sirve para
        saber a quién ya se la cargaste y a quién le falta, y para cargar las
        que faltan en bloque por terminación del CUIT.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <label className="campo">
          <span>Clave cargada desde</span>
          <input
            type="date"
            value={filtros.desde}
            onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })}
          />
        </label>
        <label className="campo">
          <span>Hasta</span>
          <input
            type="date"
            value={filtros.hasta}
            onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })}
          />
        </label>
        <label className="campo">
          <span>CUIT termina en</span>
          <select
            value={filtros.terminacion}
            onChange={(e) => setFiltros({ ...filtros, terminacion: e.target.value })}
          >
            <option value="">Todos</option>
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
        <button className="btn btn-sm" type="submit">Buscar</button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiar}>
          Limpiar
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => exportarClavesFiscales(filtros)}
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

      {datos && !cargando && (
        <>
          <p className="nota">
            {alcance} — <b>{datos.cantidad}</b> cliente(s) con clave fiscal
            {datos.terminacion !== null && datos.terminacion !== undefined
              ? ` · filtrado por los que terminan en ${datos.terminacion}`
              : ""}
          </p>

          {datos.cantidad === 0 && (
            <p className="nota">
              Ningún cliente tiene clave fiscal cargada en este período.
            </p>
          )}

          {/* --- lista con orden a elegir --- */}
          {datos.cantidad > 0 && (
            <>
              <div className="buscador">
                <label className="campo">
                  <span>Ordenar por</span>
                  <select value={orden} onChange={(e) => setOrden(e.target.value)}>
                    {ORDENES.map((o) => (
                      <option key={o.id} value={o.id}>{o.etiqueta}</option>
                    ))}
                  </select>
                </label>
                <button
                  className="btn btn-sm fantasma"
                  type="button"
                  onClick={() => setDescendente(!descendente)}
                >
                  {descendente ? "Ascendente" : "Descendente"}
                </button>
                <button
                  className="btn btn-sm fantasma"
                  type="button"
                  onClick={() => setVerBloques(!verBloques)}
                >
                  {verBloques ? "Ver todo junto" : "Ver en bloques por dígito"}
                </button>
              </div>

              {verBloques ? (
                <>
                  {datos.bloques.map((b) => (
                    <div className="panel" key={b.ultimo_digito}>
                      <h3>
                        CUIT termina en {b.ultimo_digito}
                        <small className="eecc-nota"> · {b.cantidad} cliente(s)</small>
                      </h3>
                      <div className="tabla-envoltura">
                        <table className="tabla">
                          <thead>
                            <tr>{columnas.map(encabezado)}</tr>
                          </thead>
                          <tbody>
                            {ordenar(b.items).map(fila)}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                  {datos.bloques.length === 0 && (
                    <p className="nota">
                      Ningún cliente con clave fiscal tiene CUIT cargado, así que
                      no se puede agrupar por terminación.
                    </p>
                  )}
                </>
              ) : (
                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead>
                      <tr>{columnas.map(encabezado)}</tr>
                    </thead>
                    <tbody>{ordenar(datos.items).map(fila)}</tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* --- los que todavía no tienen clave --- */}
          <div className="panel">
            <h3>
              Sin clave fiscal cargada
              <small className="eecc-nota">
                {" "}
                · {datos.cantidad_sin_clave} cliente(s)
              </small>
            </h3>
            {datos.cantidad_sin_clave === 0 ? (
              <p className="lista-vacia">
                Todos los clientes tienen clave fiscal cargada.
              </p>
            ) : (
              <>
                <p className="nota">
                  A estos clientes todavía no se la cargaste. Cargales la clave
                  fiscal desde su ficha (pestaña Datos) y van a aparecer en la
                  lista de arriba.
                </p>
                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Cuenta</th>
                        <th>Apellido y nombre / Razón social</th>
                        <th className="mono">CUIT</th>
                        <th className="mono">Termina en</th>
                        <th>Email</th>
                        <th>Localidad</th>
                      </tr>
                    </thead>
                    <tbody>
                      {datos.sin_clave.map((i) => (
                        <tr key={i.id}>
                          <td className="mono">{i.nro_cuenta}</td>
                          <td>{celda(i)}</td>
                          <td className="mono">
                            {i.cuit || <span className="vacio">—</span>}
                          </td>
                          <td className="mono">
                            {i.ultimo_digito || <span className="vacio">—</span>}
                          </td>
                          <td>{i.email || <span className="vacio">—</span>}</td>
                          <td>{i.localidad || <span className="vacio">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}