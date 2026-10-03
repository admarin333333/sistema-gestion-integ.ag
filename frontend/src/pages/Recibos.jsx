import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useNavigate, useLocation } from "react-router-dom";
import { descargar } from "../api/client.js";
import { listarClientes } from "../api/clientes.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import {
  FORMAS,
  ESTADOS,
  listarRecibos,
  totalRecibos,
  eliminarRecibo,
  anularRecibo,
  reabrirRecibo,
  query,
} from "../api/recibos.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIOS = { cliente_id: "", desde: "", hasta: "", sin_asiento: "" };

/** "true" → true, "" → false. El filtro viene como texto del `<select>`. */
const aBooleano = (v) => v === true || v === "true";

const HOY = new Date();
const iso = (d) => d.toISOString().slice(0, 10);
const inicioDeMes = new Date(HOY.getFullYear(), HOY.getMonth(), 1);

/**
 * Los períodos que el contador usa de verdad. Escribir dos fechas a mano cada
 * vez es lo que hace el filtro ilegible.
 *
 * El ejercicio (2026-09-01 a 2027-08-31) está hardcodeado porque es el del
 * estudio, que no cambia por corrida. Si algún día el estudio cambia de
 * ejercicio, se cambia acá.
 */
const PERIODOS = [
  { clave: "hoy", nombre: "Hoy", desde: iso(HOY), hasta: iso(HOY) },
  {
    clave: "mes",
    nombre: "Este mes",
    desde: iso(inicioDeMes),
    hasta: iso(HOY),
  },
  {
    clave: "ejercicio",
    nombre: "Ejercicio",
    desde: "2026-09-01",
    hasta: "2027-08-31",
  },
  { clave: "todo", nombre: "Todo", desde: "", hasta: "" },
];

export default function Recibos() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const aviso = location.state?.aviso;
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [periodo, setPeriodo] = useState("");
  const [lista, setLista] = useState([]);
  const [total, setTotal] = useState(0);
  const [clientes, setClientes] = useState([]);
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
        listarRecibos(params),
        totalRecibos(params),
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
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buscar = (e) => {
    e.preventDefault();
    cargar(filtros);
  };

  /** Un atajo de período: pone las fechas Y busca, en un solo paso. */
  const elegirPeriodo = (clave) => {
    const p = PERIODOS.find((x) => x.clave === clave);
    if (!p) return;
    setPeriodo(clave);
    const nuevos = { ...filtros, desde: p.desde, hasta: p.hasta };
    setFiltros(nuevos);
    cargar(nuevos);
  };

  // El cliente que está elegido en el buscador, para que el campo muestre su
  // nombre. Sin esto el campo quedaría con el texto escrito y al recargar la
  // pantalla (con `cliente_id` en el filtro) no se sabría a quién corresponde.
  const clienteFiltro = clientes.find((c) => String(c.id) === String(filtros.cliente_id));

  // Si la persona escribe una fecha a mano, el atajo deja de ser lo que está
  // marcado: si no, el botón quedaría prendido mintiendo.
  const cambiar = (k) => (e) => {
    const valores = { ...filtros, [k]: e.target.value };
    setFiltros(valores);
    if (k === "desde" || k === "hasta") {
      const p = PERIODOS.find((x) => x.desde === valores.desde && x.hasta === valores.hasta);
      setPeriodo(p ? p.clave : "");
    }
  };

  const limpiar = () => {
    setFiltros(VACIOS);
    setPeriodo("");
    cargar(VACIOS);
  };

  const hacer = async (fn) => {
    try {
      await fn();
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  const bajar = async (ruta) => {
    try {
      await descargar(ruta);
    } catch (e) {
      setError(e.message);
    }
  };

  const nombreCliente = (id) => {
    const c = clientes.find((x) => x.id === Number(id));
    return c ? c.nombre_completo : "";
  };

  const alcance = [
    filtros.cliente_id && `Cliente: ${nombreCliente(filtros.cliente_id)}`,
    filtros.desde && `Desde: ${fecha(filtros.desde)}`,
    filtros.hasta && `Hasta: ${fecha(filtros.hasta)}`,
    aBooleano(filtros.sin_asiento) && "Solo sin asentar",
  ]
    .filter(Boolean)
    .join(" · ");

  // Cuánto hay pendiente de asentar DENTRO de lo que se está viendo. Sale de
  // las filas ya cargadas, así que siempre cuadra con la lista.
  const sinAsentar = lista
    .filter((r) => r.estado === "emitido" && !r.id_asiento)
    .reduce((s, r) => s + Number(r.importe || 0), 0);
  const faltanAsentar = lista.filter(
    (r) => r.estado === "emitido" && !r.id_asiento
  ).length;

  const borrar = (r) => {
    if (window.confirm(`¿Eliminar el recibo ${r.numero}?`)) {
      hacer(() => eliminarRecibo(r.id));
    }
  };

  const anular = (r) => {
    if (window.confirm(`¿Anular el recibo ${r.numero}? Se desaplicarán sus aplicaciones.`)) {
      hacer(() => anularRecibo(r.id));
    }
  };

  const reabrir = (r) => {
    if (window.confirm(`¿Reabrir el recibo anulado ${r.numero}?`)) {
      hacer(() => reabrirRecibo(r.id));
    }
  };

  // El asiento del recibo se maneja desde la pantalla del recibo, no desde
  // acá. El listado muestra en qué estado está (columna Asiento) y el botón
  // "Ver" abre el recibo con su asiento al lado.

  const mensajes = [aviso, error].filter(Boolean).join(" · ");

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de recibos{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Recibos</span>
      <h1>Recibos emitidos</h1>
      <p className="lead">
        Filtrá por <b>cliente</b> o <b>período</b>. El total de abajo lo calcula la base de datos.
      </p>

      <form className="buscador" onSubmit={buscar}>
        {/* Buscador y no lista desplegada: se escribe el nombre, el CUIT o el
            DNI y filtra al toque. Con la lista había que buscarlos scrolleando
            adentro del desplegable, que con muchos clientes es imposible. */}
        <BuscadorCliente
          clientes={clientes}
          seleccion={clienteFiltro || null}
          onElegir={(c) => {
            setFiltros({ ...filtros, cliente_id: c ? String(c.id) : "" });
          }}
          tipo_registro="cliente"
          etiqueta="Cliente"
          placeholder="Todos los clientes — escribí para filtrar"
        />

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>

        {/* Los rangos que el contador realmente usa. Escribir dos fechas a mano
            cada vez es lo que hace el filtro ilegible: hoy, el mes, el
            ejercicio. */}
        <div className="campo">
          <span>Período</span>
          <div className="grupo-botones">
            {PERIODOS.map((p) => (
              <button
                key={p.clave}
                type="button"
                className={`btn btn-sm ${periodo === p.clave ? "" : "fantasma"}`}
                onClick={() => elegirPeriodo(p.clave)}
              >
                {p.nombre}
              </button>
            ))}
          </div>
        </div>

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

      <div className="buscador">
        <button className="btn btn-sm" onClick={() => navigate("/recibo-alta")}>
          + Nuevo recibo
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => descargar(`/recibos/export.xlsx${query(filtros)}`)}
        >
          Descargar Excel
        </button>
        <button className="btn btn-sm fantasma" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>

      {mensajes && <p className="error">{mensajes}</p>}

      {/* El aviso que faltaba: un recibo guardado NO mueve la cuenta. Si el
          contador ve recibos y una cuenta en cero, la respuesta está acá. */}
      {faltanAsentar > 0 && (
        <p className="aviso-amarillo">
          Hay <b>{faltanAsentar}</b> recibo{faltanAsentar === 1 ? "" : "s"} sin
          asentar: {pesos(sinAsentar)} no están todavía en los libros. Abrí cada
          uno con <b>Ver</b> y apretá <b>Generar el asiento</b>.
        </p>
      )}

      {/* La tabla scrollea dentro de su propia caja: con cientos de recibos, si
          crece para siempre hay que scrollear la página entera y uno se
          pierde. El encabezado queda fijo arriba y el total fijo abajo, así
          siempre se sabe qué se está mirando y cuánto da. */}
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Número</th>
              <th>Cliente</th>
              <th>Forma de pago</th>
              <th className="derecha">Importe</th>
              <th>Asiento</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="8" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="8" className="vacio">
                  No hay recibos con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{fecha(r.fecha)}</td>
                  <td className="mono">{r.numero}</td>
                  <td>
                    <b>{r.cliente_nombre}</b>
                  </td>
                  <td>{FORMAS[r.forma_pago] || r.forma_pago}</td>
                  <td className="mono derecha">{pesos(r.importe)}</td>
                  <td className="mono">
                    {r.numero_comprobante_asiento ? (
                      <>
                        {r.numero_comprobante_asiento}
                        <small className="nota">
                          {r.estado_asiento === "anulado"
                            ? "anulado"
                            : r.estado_asiento === "contabilizado"
                              ? "contabilizado"
                              : r.estado_asiento || ""}
                        </small>
                      </>
                    ) : (
                      <span className="nota">sin asentar</span>
                    )}
                  </td>
                  <td>
                    <span className={`chip ${r.estado}`}>{ESTADOS[r.estado] || r.estado}</span>
                  </td>
                  <td className="acciones">
                    {/* Un solo botón: "Ver". El asiento se genera o se anula
                        desde la pantalla del recibo, donde se ve el recibo y el
                        asiento juntos. Acá, dos botones que cambian según el
                        estado confundían más de lo que ayudaban. */}
                    <button
                      className="btn btn-sm"
                      onClick={() => navigate(`/recibo/${r.id}`)}
                    >
                      Ver
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => descargar(`/recibos/${r.id}/pdf`)}
                    >
                      PDF
                    </button>
                    {esAdmin && r.estado === "emitido" && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => anular(r)}
                      >
                        Anular
                      </button>
                    )}
                    {esAdmin && r.estado === "anulado" && (
                      <button
                        className="btn btn-sm"
                        onClick={() => reabrir(r)}
                      >
                        Reabrir
                      </button>
                    )}
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(r)}
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
                <td colSpan="5"><b>TOTAL</b></td>
                <td className="mono derecha"><b>{pesos(total)}</b></td>
                <td colSpan="3"></td>
              </tr>
            </tfoot>
          </table>
        </div>

        <p className="nota">
          {cargando
            ? ""
            : `${lista.length} recibo${lista.length === 1 ? "" : "s"} en el listado`}
        </p>
      </section>
    );
  }