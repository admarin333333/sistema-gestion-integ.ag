import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { fecha, pesos } from "../formato.js";
import { api } from "../api/client.js";
import {
  ESTADOS,
  FORMAS,
  anularAsientoRecibo,
  anularRecibo,
  aplicarRecibo,
  desaplicarRecibo,
  generarAsientoRecibo,
  listarAplicaciones,
  obtenerRecibo,
  reabrirRecibo,
} from "../api/recibos.js";

/** El backend devuelve los importes como número; acá se muestran con coma. */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Pantalla de UN recibo: acá se ve el recibo entero y, al lado, el asiento.
 *
 * Es la respuesta a "yo cobro hoy y asento la semana que viene": el recibo se
 * guarda apenas se confirma, y el asiento es un botón aparte. Por eso esta
 * pantalla tiene que mostrar las dos cosas juntas —si el contador tiene que ir
 * a dos lugares para entender qué pasó, no entiende nada.
 *
 * Las tres cosas que se pueden hacer, y cuándo:
 *   - sin asiento  → se puede **cambiar los pagos** y después generar
 *   - con asiento  → los pagos NO se tocan (el asiento es documento contable);
 *                    solo se puede anular el asiento y rehacerlo
 *   - recibo anulado → no se toca nada
 */
export default function Recibo() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [recibo, setRecibo] = useState(null);
  const [aplicaciones, setAplicaciones] = useState([]);
  const [asiento, setAsiento] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = async () => {
    setError("");
    try {
      const r = await obtenerRecibo(id);
      setRecibo(r);
      setAplicaciones(await listarAplicaciones(id));
      // El asiento se pide aparte porque es otra pantalla y tiene su propio
      // historial. Si el recibo no tiene, se deja en null y la pantalla avisa.
      setAsiento(r.id_asiento ? await api(`/asientos/${r.id_asiento}`) : null);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const hacer = async (fn) => {
    setOcupado(true);
    setError("");
    try {
      await fn();
      await cargar();
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  };

  const generarAsiento = () => {
    if (
      window.confirm(
        "¿Generar el asiento de cobranza? Queda contabilizado con el " +
          "comprobante interno que le toque y después ya no se pueden cambiar " +
          "las formas de pago."
      )
    ) {
      hacer(generarAsientoRecibo.bind(null, recibo.id));
    }
  };

  const anularAsiento = () => {
    if (
      window.confirm(
        "¿Anular el asiento? El recibo sigue como estaba; solo se da por " +
          "anulado en libros. Después podés generar uno nuevo."
      )
    ) {
      hacer(anularAsientoRecibo.bind(null, recibo.id));
    }
  };

  const quitarAplicacion = (app) => {
    if (
      window.confirm(
        `¿Quitar la aplicación a la factura ${app.factura.punto_venta}-` +
          `${app.factura.numero}?`
      )
    ) {
      hacer(desaplicarRecibo.bind(null, app.id));
    }
  };

  const devolverAplicacion = (app) => {
    const importe = window.prompt(
      "¿Cuánto se aplica a esta factura?",
      String(app.factura.importe)
    );
    if (importe === null) return;
    hacer(() =>
      aplicarRecibo(recibo.id, { factura_id: app.factura_id, importe: Number(importe) })
    );
  };

  if (cargando) return <p className="nota">Cargando…</p>;
  if (!recibo) return <p className="error">{error || "No existe ese recibo."}</p>;

  const esAnulado = recibo.estado === "anulado";
  const tieneAsiento = Boolean(recibo.id_asiento);
  const asientoAnulado = recibo.estado_asiento === "anulado";
  const totalAplicado = aplicaciones.reduce((s, a) => s + Number(a.importe || 0), 0);
  const libre = Number(recibo.importe) - totalAplicado;

  return (
    <section>
      <span className="kicker">Recibos</span>
      <h1>
        Recibo {recibo.numero}{" "}
        <span className={`chip ${recibo.estado}`}>
          {ESTADOS[recibo.estado] || recibo.estado}
        </span>
      </h1>

      {error && <p className="error">{error}</p>}

      <div className="buscador">
        <button className="btn btn-sm fantasma" onClick={() => navigate("/recibos")}>
          Volver al listado
        </button>
        {esAdmin && esAnulado && (
          <button
            className="btn btn-sm"
            disabled={ocupado}
            onClick={() => hacer(reabrirRecibo.bind(null, recibo.id))}
          >
            Reabrir recibo
          </button>
        )}
        {esAdmin && !esAnulado && (
          <button
            className="btn btn-sm peligro"
            disabled={ocupado}
            onClick={() => {
              if (
                window.confirm(
                  "¿Anular el recibo? Se desaplican sus aplicaciones. " +
                    "El asiento NO se anula: es otra cosa."
                )
              ) {
                hacer(anularRecibo.bind(null, recibo.id));
              }
            }}
          >
            Anular recibo
          </button>
        )}
      </div>

      {/* ------------------------------------------------ el recibo */}
      <fieldset className="fieldset">
        <legend>El recibo</legend>
        <div className="form-grid">
          <label className="campo">
            <span>Cliente</span>
            <input value={recibo.cliente_nombre} readOnly />
          </label>
          <label className="campo">
            <span>Fecha</span>
            <input value={fecha(recibo.fecha)} readOnly />
          </label>
          <label className="campo">
            <span>Importe</span>
            <input value={numero(recibo.importe)} readOnly />
          </label>
        </div>

        <h3 style={{ marginTop: "1rem" }}>Con qué se cobró</h3>
        {recibo.pagos.length === 0 ? (
          <p className="aviso-amarillo">
            Este recibo no tiene formas de pago cargadas (se cargó antes de que
            existieran). Para poder asentar hay que elegir con qué se cobró.
          </p>
        ) : (
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Forma de pago</th>
                  <th className="derecha">Importe</th>
                  <th>Cuenta donde entró</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {recibo.pagos.map((p) => (
                  <tr key={p.id_pago}>
                    <td>{FORMAS[p.forma_pago] || p.forma_pago}</td>
                    <td className="mono derecha">{numero(p.importe)}</td>
                    <td className="mono">
                      {p.cuenta_codigo ? `${p.cuenta_codigo} ${p.cuenta_nombre}` : "—"}
                    </td>
                    <td>{p.detalle || "—"}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th>Suma</th>
                  <th className="derecha">
                    {numero(
                      recibo.pagos.reduce((s, p) => s + Number(p.importe || 0), 0)
                    )}
                  </th>
                  <th colSpan="2"></th>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        {tieneAsiento && !asientoAnulado && (
          <p className="nota">
            Las formas de pago no se pueden cambiar: el asiento ya está
            contabilizado y sus líneas son la foto de estos pagos. Para
            cambiarlas, anulá el asiento.
          </p>
        )}
      </fieldset>

      {/* ------------------------------------- a qué facturas se aplicó */}
      <fieldset className="fieldset">
        <legend>A qué documentos se aplicó</legend>
        {aplicaciones.length === 0 ? (
          <p className="lista-vacia">
            Este recibo todavía no está aplicado a ninguna factura.
          </p>
        ) : (
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Factura</th>
                  <th>Concepto</th>
                  <th className="derecha">Importe de la factura</th>
                  <th className="derecha">Aplicado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {aplicaciones.map((a) => (
                  <tr key={a.id}>
                    <td className="mono">
                      {a.factura.punto_venta}-{a.factura.numero}
                    </td>
                    <td>{a.factura.concepto || "—"}</td>
                    <td className="mono derecha">{numero(a.factura.importe)}</td>
                    <td className="mono derecha">{numero(a.importe)}</td>
                    <td className="acciones">
                      {!esAnulado && (
                        <button
                          className="btn btn-sm peligro"
                          disabled={ocupado}
                          onClick={() => quitarAplicacion(a)}
                        >
                          Quitar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th colSpan={3}>Aplicado</th>
                  <th className="derecha">{numero(totalAplicado)}</th>
                  <th></th>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        {libre > 0.005 && (
          <p className="nota">
            Quedan {numero(libre)} del recibo sin aplicar a ninguna factura.
          </p>
        )}
        {esAnulado && (
          <p className="nota">
            <button className="link" onClick={devolverAplicacion}>
              Reaplicar un importe
            </button>{" "}
            no aplica a recibos anulados.
          </p>
        )}
      </fieldset>

      {/* -------------------------------------------------- el asiento */}
      <fieldset className="fieldset">
        <legend>
          El asiento{" "}
          {recibo.numero_comprobante_asiento && (
            <span className={`chip ${recibo.estado_asiento}`}>
              {recibo.numero_comprobante_asiento}
            </span>
          )}
        </legend>

        {!tieneAsiento && (
          <p className="aviso-amarillo">
            Este recibo todavía <b>no está en los libros</b>. Es normal: el
            recibo se guarda al cobrar y el asiento se genera cuando el
            contador decide. Cuando lo generes, sale con el número de
            comprobante que le toque (familia RC) y queda contabilizado.
          </p>
        )}

        {tieneAsiento && asiento && (
          <>
            <p className="nota">{asiento.concepto}</p>
            <table className="tabla as-tabla">
              <thead>
                <tr>
                  <th>Cuenta</th>
                  <th className="as-dinero">Debe</th>
                  <th className="as-dinero">Haber</th>
                </tr>
              </thead>
              <tbody>
                {asiento.detalle.map((d, i) => (
                  <tr key={i}>
                    <td>
                      <b>{d.codigo}</b> {d.nombre_cuenta}
                      {d.auxiliar_nombre && (
                        <small className="nota"> · {d.auxiliar_nombre}</small>
                      )}
                    </td>
                    <td className="as-dinero">{Number(d.debe) ? numero(d.debe) : ""}</td>
                    <td className="as-dinero">{Number(d.haber) ? numero(d.haber) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th>Totales</th>
                  <th className="as-dinero">{numero(asiento.total_debe)}</th>
                  <th className="as-dinero">{numero(asiento.total_haber)}</th>
                </tr>
              </tfoot>
            </table>
            <p className={asiento.estado === "anulado" ? "aviso-amarillo" : "ok"}>
              {asiento.estado === "anulado"
                ? "Asiento ANULADO: no suma en los libros, pero el recibo sigue válido."
                : Number(asiento.total_debe) === Number(asiento.total_haber)
                  ? `Cierra: el Debe y el Haber dan ${numero(asiento.total_debe)}.`
                  : "El asiento no cierra. Revisá la configuración de asientos."}
            </p>
          </>
        )}

        {/* Un solo botón a la vez: si no hay asiento se genera, si hay y está
            vivo se anula. Nunca los dos, que es lo que confundía. */}
        <div className="form-acciones">
          {esAdmin && !esAnulado && !tieneAsiento && (
            <button
              className="btn"
              disabled={ocupado}
              onClick={generarAsiento}
            >
              Generar el asiento
            </button>
          )}
          {esAdmin && !esAnulado && tieneAsiento && !asientoAnulado && (
            <button
              className="btn peligro"
              disabled={ocupado}
              onClick={anularAsiento}
            >
              Anular el asiento
            </button>
          )}
        </div>
      </fieldset>
    </section>
  );
}