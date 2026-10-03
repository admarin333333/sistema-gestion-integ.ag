import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useNavigate, useLocation } from "react-router-dom";
import { descargar } from "../api/client.js";
import { listarClientes } from "../api/clientes.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import {
  ESTADOS,
  TIPOS,
  anularAsientoFactura,
  anularFactura,
  eliminarFactura,
  enviarFacturas,
  generarAsientoFactura,
  listarFacturas,
  query,
  reabrirFactura,
  totalFacturas,
} from "../api/facturas.js";
import { NOMBRE_ESTUDIO, fecha, pesos } from "../formato.js";

const VACIOS = { cliente_id: "", estado: "", desde: "", hasta: "" };

export default function Facturas() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const aviso = location.state?.aviso;
  const esAdmin = user.rol === "admin";

  const [filtros, setFiltros] = useState(VACIOS);
  const [lista, setLista] = useState([]);
  const [total, setTotal] = useState(0);
  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [tildadas, setTildadas] = useState([]);
  const [avisos, setAvisos] = useState([]);
  // La factura cuyo asiento se está generando: para dejar el botón en
  // "Generando…" y que no se pueda apretar dos veces.
  const [generando, setGenerando] = useState(null);

  const cargar = async (f) => {
    setCargando(true);
    setError("");
    try {
      const [items, suma] = await Promise.all([listarFacturas(f), totalFacturas(f)]);
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

  const cambiar = (k) => (e) => setFiltros({ ...filtros, [k]: e.target.value });

  // El cliente elegido en el buscador, para que el campo muestre su nombre.
  const clienteFiltro = clientes.find(
    (c) => String(c.id) === String(filtros.cliente_id)
  );

  const buscar = (e) => {
    e.preventDefault();
    setTildadas([]);
    cargar(filtros);
  };

  const limpiar = () => {
    setFiltros(VACIOS);
    setTildadas([]);
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

  // Cuántas del listado están sin asentar. Se cuentan acá y no en el backend
  // porque es un dato de la pantalla (solo de lo que se está viendo), no un
  // total del sistema: si filtrás por cliente, el aviso habla de las de ESE
  // cliente.
  //
  // Las anuladas se dejan fuera: una factura anulada no se asienta nunca.
  const sinAsentar = lista.filter(
    (f) => !f.id_asiento && f.estado !== "anulada"
  ).length;

  /* --- los botones del asiento ------------------------------------------
   *
   * Las facturas cargadas ANTES de que existiera el módulo contable no tienen
   * asiento: se emiten igual, pero no están en los libros. El botón "Generar"
   * les crea el que les corresponde, con la misma proyección que usa el alta
   * (Documentos a cobrar / ingresos / IVA, o el inverso si es una nota).
   *
   * Anular la factura NO anula el asiento: son cosas separadas. Por eso el
   * botón sale solo si NO tiene asiento; si lo tiene, se ve su número y se lo
   * puede anular desde la pantalla de asientos.
   */
  const generarAsiento = async (f) => {
    if (
      !window.confirm(
        `¿Generar el asiento de la factura ${f.numero}?\n\n` +
          "Se va a asentar como está ahora: Documentos a cobrar, ingresos e IVA."
      )
    ) {
      return;
    }
    setError("");
    setGenerando(f.id);
    try {
      await generarAsientoFactura(f.id);
      setAvisos((v) => [...v, `Asiento generado para la factura ${f.numero}.`]);
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerando(null);
    }
  };

  const anularAsiento = async (f) => {
    if (
      !window.confirm(
        `¿Anular el asiento ${f.numero_comprobante_asiento}?\n\n` +
          "La factura sigue como estaba. Anulado es terminal: ese asiento no " +
          "se vuelve a usar, y hay que generar otro si hace falta."
      )
    ) {
      return;
    }
    setError("");
    setGenerando(f.id);
    try {
      await anularAsientoFactura(f.id);
      setAvisos((v) => [...v, `Asiento ${f.numero_comprobante_asiento} anulado.`]);
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerando(null);
    }
  };

  // qué cubre este listado (se imprime arriba de todo)
  const alcance = [
    filtros.cliente_id && `Cliente: ${nombreCliente(filtros.cliente_id)}`,
    filtros.estado && ESTADOS[filtros.estado],
    filtros.desde && `Desde: ${fecha(filtros.desde)}`,
    filtros.hasta && `Hasta: ${fecha(filtros.hasta)}`,
  ]
    .filter(Boolean)
    .join(" · ");

  const borrar = (f) => {
    if (window.confirm(`¿Eliminar la factura ${f.numero}?`)) {
      hacer(() => eliminarFactura(f.id));
    }
  };

  // lo que hay que contarle al usuario (todo junto en un solo cartel)
  const mensajes = [aviso, ...avisos, error].filter(Boolean).join(" · ");

  // ------------------------------------------------------------- envío mail
  const tildar = (id) =>
    setTildadas((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const tildarTodas = (e) =>
    setTildadas(e.target.checked ? lista.map((f) => f.id) : []);

  /** Manda las que se le pasen. Lo que no sale queda en el cartel rojo. */
  const enviar = async (ids) => {
    if (!ids.length) {
      setError("Tildá al menos una factura para enviarla.");
      return;
    }
    setError("");
    setAvisos([]);
    try {
      const r = await enviarFacturas(ids);
      setAvisos(r.avisos);
      setTildadas([]);
      await cargar(filtros);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Informe de facturas{alcance ? ` — ${alcance}` : ""}</span>
      </div>

      <span className="kicker">Facturas</span>
      <h1>Comprobantes emitidos</h1>
      <p className="lead">
        Filtrá por <b>cliente</b>, <b>estado</b> o <b>período</b>. El total de
        abajo lo calcula la base de datos, no el navegador.
      </p>

      {/* El aviso que faltaba: si hay facturas sin asentar, no se nota en la
          columna sola. Sin él, el contador ve una lista de comprobantes
          normales y asume que están todos en los libros. */}
      {sinAsentar > 0 && (
        <p className="aviso-amarillo">
          Hay <b>{sinAsentar}</b> comprobante{sinAsentar === 1 ? "" : "s"} sin
          asiento en este listado. Son las facturas cargadas antes de que
          existiera el módulo contable: no están en los mayores ni en el balance.
          Apretá <b>Generar asiento</b> en cada una para traerlas al libro.
        </p>
      )}

      <form className="buscador" onSubmit={buscar}>
        {/* Buscador y no lista desplegada: se escribe y filtra al toque. */}
        <BuscadorCliente
          clientes={clientes}
          seleccion={clienteFiltro || null}
          onElegir={(c) =>
            setFiltros({ ...filtros, cliente_id: c ? String(c.id) : "" })
          }
          tipo_registro="cliente"
          etiqueta="Cliente"
          placeholder="Todos los clientes — escribí para filtrar"
        />

        <select aria-label="Estado" value={filtros.estado} onChange={cambiar("estado")}>
          <option value="">Cualquier estado</option>
          {Object.entries(ESTADOS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>

        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiar}>
          Limpiar
        </button>
      </form>

      <div className="buscador">
        <button className="btn btn-sm" onClick={() => navigate("/factura-alta")}>
          + Nueva factura
        </button>
        <button
          className="btn btn-sm"
          disabled={tildadas.length === 0}
          onClick={() => enviar(tildadas)}
        >
          Enviar por mail{tildadas.length ? ` (${tildadas.length})` : ""}
        </button>
        <button
          className="btn btn-sm fantasma"
          onClick={() => descargar(`/facturas/export.xlsx${query(filtros)}`)}
        >
          Descargar Excel
        </button>
        <button className="btn btn-sm fantasma" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>

      {mensajes && <p className="error">{mensajes}</p>}
      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th className="col-tilde">
                <input
                  type="checkbox"
                  aria-label="Tildar todas"
                  checked={
                    lista.length > 0 && lista.every((f) => tildadas.includes(f.id))
                  }
                  onChange={tildarTodas}
                />
              </th>
              <th>Fecha</th>
              <th>Comprobante</th>
              <th>Número</th>
              <th>Cliente</th>
              <th>Concepto</th>
              <th className="derecha">Importe</th>
              <th>Estado</th>
              <th>Asiento</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan="9" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="9" className="vacio">
                  No hay comprobantes con esos filtros.
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((f) => (
                <tr key={f.id}>
                  <td className="col-tilde">
                    <input
                      type="checkbox"
                      aria-label={`Tildar factura ${f.numero}`}
                      checked={tildadas.includes(f.id)}
                      onChange={() => tildar(f.id)}
                    />
                  </td>
                  <td className="mono">{fecha(f.fecha)}</td>
                  <td>
                    {TIPOS[f.tipo_comprobante]}
                    <small>PV {f.punto_venta}</small>
                  </td>
                  <td className="mono">{f.numero}</td>
                  <td>
                    <b>{f.cliente_nombre}</b>
                  </td>
                  <td>{f.concepto || "—"}</td>
                  <td className="mono derecha">{pesos(f.importe)}</td>
                  <td>
                    <span className={`chip ${f.estado}`}>{ESTADOS[f.estado]}</span>
                    {f.fecha_envio && <span className="chip enviada">Enviado</span>}
                  </td>
                  {/* La columna del asiento: muestra el número del comprobante
                      si lo tiene, y el botón "Generar" si no. Sin esto, las
                      facturas cargadas antes del módulo quedaban fuera de los
                      libros sin que se notara. */}
                  <td>
                    {f.numero_comprobante_asiento ? (
                      <span className="mono">{f.numero_comprobante_asiento}</span>
                    ) : f.estado === "anulada" ? (
                      <small className="nota">—</small>
                    ) : (
                      <small className="nota">sin asentar</small>
                    )}
                  </td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => navigate(`/factura-editar/${f.id}`)}
                    >
                      Editar
                    </button>
                    {/* El botón del asiento sale SOLO si la factura no lo tiene
                        y no está anulada. Con el asiento ya hecho, la acción es
                        "Modificar" o "Anular", que van desde la pantalla de
                        asientos: son tres botones separados porque anular la
                        factura NO anula el asiento. */}
                    {esAdmin && f.estado !== "anulada" && !f.id_asiento && (
                      <button
                        className="btn btn-sm"
                        onClick={() => generarAsiento(f)}
                        disabled={generando === f.id}
                        title="Genera el asiento que le faltaba a esta factura"
                      >
                        {generando === f.id ? "Generando…" : "Generar asiento"}
                      </button>
                    )}
                    {esAdmin && f.estado !== "anulada" && f.id_asiento && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => anularAsiento(f)}
                        disabled={generando === f.id}
                        title="Anula solo el asiento; la factura sigue como estaba"
                      >
                        Anular asiento
                      </button>
                    )}
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => descargar(`/facturas/${f.id}/pdf`)}
                    >
                      PDF
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => enviar([f.id])}
                    >
                      {f.fecha_envio ? "Reenviar" : "Enviar"}
                    </button>
                    {esAdmin && f.estado !== "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => anularFactura(f.id))}
                      >
                        Anular
                      </button>
                    )}
                    {esAdmin && f.estado === "anulada" && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => hacer(() => reabrirFactura(f.id))}
                      >
                        Reabrir
                      </button>
                    )}
                    {esAdmin && (
                      <button
                        className="btn btn-sm peligro"
                        onClick={() => borrar(f)}
                      >
                        Borrar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>

            <tfoot>
              {/* Los colSpan tienen que sumar las columnas del thead: tilde +
                  7 del cuerpo + Asiento + acciones. Con la columna nueva, si no
                  se ajustan, el TOTAL se corre de lugar. */}
              <tr>
                <td className="col-tilde"></td>
                <td colSpan="5">
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