import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { listarClientes } from "../api/clientes.js";
import {
  FORMAS,
  aCobrar,
  aCobroPayload,
  crearRecibo,
  cuentasIngreso,
  formasPago,
  generarAsientoRecibo,
  previewCobro,
} from "../api/recibos.js";

const HOY = new Date().toISOString().slice(0, 10);

/** El backend devuelve los importes como número; acá se muestran con coma. */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** La suma de una lista de pagos. Solo para mostrarla mientras se carga:
 *  el backend la vuelve a hacer y es la que manda. */
const sumaPagos = (pagos) =>
  pagos.reduce((s, p) => s + (Number(p.importe) || 0), 0);

/**
 * Pantalla de recibo nuevo, en los pasos que hace el contador:
 *
 *   1. Buscar el cliente
 *   2. Tildar las facturas (y ver las notas de crédito que las compensan)
 *   3. Con qué se paga (una o varias formas de pago, con su cuenta)
 *   4. Ver cómo queda (recibo + asiento) antes de confirmar
 *   5. Confirmar
 *
 * El importe NO es un dato que se cargue suelto: sale de la suma de las facturas
 * tildadas (que ya viene con las notas de crédito restadas). Se puede tocar a
 * mano por si el cliente paga de más, y el backend avisa si no cierra.
 *
 * Todas las cuentas aritméticas están en el backend (`preview-cobro`); acá solo
 * se pinta lo que devuelve.
 */
export default function ReciboForm() {
  const { id: reciboId } = useParams();
  const navigate = useNavigate();
  const esEdicion = Boolean(reciboId);

  const [datos, setDatos] = useState({
    cliente_id: "",
    fecha: HOY,
    importe: "",
    forma_pago: "transferencia",
  });
  const [clientes, setClientes] = useState([]);
  const [cobro, setCobro] = useState(null);
  const [tildadas, setTildadas] = useState([]);   // ids de facturas tildadas
  const [notas, setNotas] = useState([]);          // ids de NC tildadas (a la vista)
  const [pagos, setPagos] = useState([]);          // [{forma_pago, importe, cuenta_id}]
  const [formas, setFormas] = useState([]);        // config_cuentas_forma_pago
  const [cuentas, setCuentas] = useState([]);      // cajas y bancos (para el selector)
  const [preview, setPreview] = useState(null);
  const [pidiendoPreview, setPidiendoPreview] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  // --- carga inicial ----------------------------------------------------
  useEffect(() => {
    listarClientes().then(setClientes).catch(() => setClientes([]));
    formasPago().then(setFormas).catch(() => setFormas([]));
    // Solo las cajas y bancos: no se puede depositar un cheque en un gasto.
    cuentasIngreso().then(setCuentas).catch(() => setCuentas([]));
  }, []);

  // --- qué tiene para cobrar este cliente --------------------------------
  const cargarCobro = async (clienteId) => {
    if (!clienteId) {
      setCobro(null);
      setTildadas([]);
      return;
    }
    try {
      setCobro(await aCobrar(clienteId));
    } catch {
      setCobro(null);
    }
  };

  const elegirCliente = (clienteId) => {
    setDatos((d) => ({ ...d, cliente_id: clienteId, importe: "" }));
    setTildadas([]);
    setNotas([]);
    setPreview(null);
    cargarCobro(clienteId);
  };

  // --- el importe y las tildas -------------------------------------------
  // Cuando cambia la lista de tildadas, el importe se recalcula con los SALDOS
  // que ya trajo el backend (netos de las notas de crédito). Es un Number() y
  // una suma de a lo sumo unas pocas filas: no es una cuenta contable, es solo
  // para ir viendo el número mientras se tilda.
  const editarImporte = (e) =>
    setDatos((d) => ({ ...d, importe: e.target.value }));

  const alternarFactura = (id) => {
    setTildadas((v) => {
      const siguiente = v.includes(id) ? v.filter((x) => x !== id) : [...v, id];
      recalcularImporte(siguiente);
      return siguiente;
    });
  };

  const alternarNota = (id) => {
    setNotas((v) => (v.includes(id) ? v.filter((x) => x !== id) : [...v, id]));
  };

  const recalcularImporte = (ids) => {
    if (!cobro) return;
    const total = cobro.facturas
      .filter((f) => ids.includes(f.id))
      .reduce((s, f) => s + Number(f.saldo || 0), 0);
    setDatos((d) => ({ ...d, importe: total ? total.toFixed(2) : "" }));
  };

  const tildarTodas = () => {
    const todas = cobro.facturas.map((f) => f.id);
    setTildadas(todas);
    recalcularImporte(todas);
  };

  const destildarTodas = () => {
    setTildadas([]);
    setDatos((d) => ({ ...d, importe: "" }));
  };

  // --- formas de pago ----------------------------------------------------
  /** Qué cuenta va por defecto según `config_cuentas_forma_pago`. */
  const cuentaDe = (formaPago) => {
    const f = formas.find((x) => x.forma_pago === formaPago);
    return f && f.cuenta_id ? f.cuenta_id : "";
  };
  const requiereBanco = (formaPago) => {
    const f = formas.find((x) => x.forma_pago === formaPago);
    return !f || f.requiere_banco;
  };

  const agregarPago = () => {
    const forma = "transferencia";
    setPagos((v) => [
      ...v,
      { forma_pago: forma, importe: "", cuenta_id: cuentaDe(forma), detalle: "" },
    ]);
  };

  const setPago = (i, campo) => (e) => {
    const valor = e.target.value;
    setPagos((v) =>
      v.map((p, k) => {
        if (k !== i) return p;
        // Si cambiás la forma de pago, la cuenta vuelve a la que esa forma tenga
        // por defecto (y a vacío si hay que elegir el banco a mano).
        if (campo === "forma_pago") {
          return { ...p, forma_pago: valor, cuenta_id: cuentaDe(valor) };
        }
        return { ...p, [campo]: valor };
      })
    );
  };

  const quitarPago = (i) => setPagos((v) => v.filter((_, k) => k !== i));

  /** Rellena el último pago con lo que falta para llegar al importe del recibo.
   *  Es una comodidad de la pantalla: el backend igual avisa si no cierra. */
  const usarTodoElImporte = () => {
    if (pagos.length === 0) return;
    const total = Number(datos.importe) || 0;
    const otros = pagos.reduce(
      (s, p, i) => (i === 0 ? s : s + (Number(p.importe) || 0)),
      0
    );
    setPagos((v) =>
      v.map((p, k) =>
        k === 0 ? { ...p, importe: (total - otros).toFixed(2) } : p
      )
    );
  };

  // --- la vista previa ----------------------------------------------------
  // Se pide al backend cada vez que cambia algo que cambia el asiento. Es la
  // misma función (`previsualizar_cobro`) que usa el alta, así que lo que se ve
  // acá es exactamente lo que se guarda.
  const pedirPreview = async () => {
    if (!datos.cliente_id || !(Number(datos.importe) > 0)) {
      setPreview(null);
      return;
    }
    setPidiendoPreview(true);
    try {
      setPreview(await previewCobro(aCobroPayload({ ...datos, facturas: tildadas, pagos })));
      setError("");
    } catch (e2) {
      setPreview(null);
      setError(e2.message);
    } finally {
      setPidiendoPreview(false);
    }
  };

  useEffect(() => {
    pedirPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos.cliente_id, datos.fecha, datos.importe, tildadas.join(","), pagos]);

  // --- confirmar ----------------------------------------------------------
  const cuerpo = () => aCobroPayload({ ...datos, facturas: tildadas, pagos });

  const confirmar = async (e) => {
    e.preventDefault();
    setError("");
    if (!datos.cliente_id) return setError("Elegí un cliente.");
    if (!datos.importe || Number(datos.importe) <= 0)
      return setError("Falta el importe del recibo.");
    if (tildadas.length === 0)
      return setError("Tildá al menos una factura para cobrar.");
    if (pagos.length === 0)
      return setError("Cargá con qué se cobró: agregá al menos una forma de pago.");
    const sinCuenta = pagos.filter((p) => !p.cuenta_id);
    if (sinCuenta.length > 0)
      return setError(
        `Elegí en qué cuenta entra el pago de ${FORMAS[sinCuenta[0].forma_pago]}.`
      );
    setEnviando(true);
    try {
      const recibo = await crearRecibo(cuerpo());
      navigate(`/recibo/${recibo.id}`);
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  const guardarYAsentar = async () => {
    const recibo = await crearRecibo(cuerpo());
    await generarAsientoRecibo(recibo.id);
    navigate("/recibos");
  };

  const totales = useMemo(
    () => ({ pagos: sumaPagos(pagos) }),
    [pagos]
  );

  if (esEdicion) {
    // Esta pantalla es SOLO para recibos nuevos. Ver o modificar uno que ya
    // existe es otra pantalla (`Recibo.jsx`), que muestra el recibo entero con
    // su asiento. Antes esta ruta no llevaba a ninguna parte y se veía una
    // pantalla en blanco.
    return (
      <section>
        <span className="kicker">Recibos</span>
        <h1>Modificar recibo</h1>
        <p className="lead">
          Para ver o cambiar un recibo que ya existe, entrá al recibo:{" "}
          <button
            className="link"
            onClick={() => navigate(`/recibo/${reciboId}`)}
          >
            recibo {reciboId}
          </button>
          .
        </p>
      </section>
    );
  }

  const listoParaConfirmar =
    datos.cliente_id && datos.importe > 0 && tildadas.length > 0 && pagos.length > 0;

  return (
    <section>
      <span className="kicker">Recibos</span>
      <h1>Cobrar a un cliente</h1>
      <p className="lead">
        Elegí el cliente, tildá lo que te paga, con qué lo paga, y revisá cómo
        queda antes de confirmar.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={confirmar}>
        {/* ---------------------------------------------------- 1. cliente */}
        <fieldset className="fieldset">
          <legend>1 · Cliente</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Cliente <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.cliente_id}
                onChange={(e) => elegirCliente(e.target.value)}
              >
                <option value="">Elegí un cliente…</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre_completo}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo">
              <span>
                Fecha <b className="obligatorio">*</b>
              </span>
              <input
                type="date"
                value={datos.fecha}
                onChange={(e) => setDatos((d) => ({ ...d, fecha: e.target.value }))}
              />
            </label>
          </div>
        </fieldset>

        {/* ------------------------------- 2. qué cobra (facturas y notas) */}
        {datos.cliente_id && (
          <fieldset className="fieldset">
            <legend>2 · Qué te paga</legend>
            {!cobro ? (
              <p className="nota">Buscando sus facturas…</p>
            ) : cobro.facturas.length === 0 ? (
              <p className="lista-vacia">
                Este cliente no tiene nada pendiente de pago.
              </p>
            ) : (
              <>
                <div className="form-acciones" style={{ gap: "0.5rem" }}>
                  <button type="button" className="btn btn-sm" onClick={tildarTodas}>
                    Tildar todas
                  </button>
                  <button type="button" className="btn btn-sm fantasma" onClick={destildarTodas}>
                    Destildar
                  </button>
                </div>

                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th></th>
                        <th>Documento</th>
                        <th>Concepto</th>
                        <th className="derecha">Importe</th>
                        <th className="derecha">Nota de crédito</th>
                        <th className="derecha">Cobrado</th>
                        <th className="derecha">Saldo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cobro.facturas.map((f) => (
                        <tr key={f.id}>
                          <td>
                            <input
                              type="checkbox"
                              checked={tildadas.includes(f.id)}
                              onChange={() => alternarFactura(f.id)}
                              aria-label={`Cobrar ${f.punto_venta}-${f.numero}`}
                            />
                          </td>
                          <td className="mono">
                            {f.punto_venta}-{f.numero}
                          </td>
                          <td>
                            {f.concepto || "—"}
                            <small className="nota">{f.etiqueta_tipo}</small>
                          </td>
                          <td className="mono derecha">{numero(f.importe)}</td>
                          <td className="mono derecha">
                            {f.creditos ? `- ${numero(f.creditos)}` : ""}
                          </td>
                          <td className="mono derecha">
                            {f.cobrado ? `- ${numero(f.cobrado)}` : ""}
                          </td>
                          <td className="mono derecha">
                            <b>{numero(f.saldo)}</b>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <th colSpan={6}>Total tildado</th>
                        <th className="derecha">
                          {numero(
                            cobro.facturas
                              .filter((f) => tildadas.includes(f.id))
                              .reduce((s, f) => s + Number(f.saldo || 0), 0)
                          )}
                        </th>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {cobro.notas_credito.length > 0 && (
                  <>
                    <p className="nota" style={{ marginTop: "1rem" }}>
                      Notas de crédito de este cliente. Una NC no se cobra: es
                      plata a favor del cliente. Si está vinculada a una factura,
                      esa factura ya sale con el saldo descontado (columna
                      "Nota de crédito").
                    </p>
                    <div className="tabla-envoltura">
                      <table className="tabla">
                        <thead>
                          <tr>
                            <th></th>
                            <th>Nota</th>
                            <th>Concepto</th>
                            <th className="derecha">Importe</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cobro.notas_credito.map((n) => (
                            <tr key={n.id}>
                              <td>
                                <input
                                  type="checkbox"
                                  checked={notas.includes(n.id)}
                                  onChange={() => alternarNota(n.id)}
                                  aria-label={`Ver nota ${n.punto_venta}-${n.numero}`}
                                />
                              </td>
                              <td className="mono">
                                {n.punto_venta}-{n.numero}
                              </td>
                              <td>{n.concepto || "—"}</td>
                              <td className="mono derecha">{numero(n.importe)}</td>
                              <td>
                                <span className={`chip ${n.estado}`}>
                                  {n.estado === "pagada" ? "Compensada" : "Disponible"}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                <div className="form-grid" style={{ marginTop: "1rem" }}>
                  <label className="campo">
                    <span>
                      Importe del recibo <b className="obligatorio">*</b>
                    </span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={datos.importe}
                      onChange={editarImporte}
                      placeholder="0,00"
                    />
                    <small className="nota">
                      Sale de las facturas tildadas. Se puede tocar a mano si el
                      cliente paga de más.
                    </small>
                  </label>
                </div>
              </>
            )}
          </fieldset>
        )}

        {/* --------------------------------------- 3. con qué se paga */}
        {datos.importe > 0 && (
          <fieldset className="fieldset">
            <legend>3 · Con qué lo paga</legend>
            <p className="nota">
              Un recibo se puede cobrar con una o varias formas de pago. Cada
              una va a su cuenta, y en el asiento sale un Debe por cada medio.
            </p>

            {pagos.length === 0 ? (
              <button type="button" className="btn btn-sm" onClick={agregarPago}>
                + Agregar forma de pago
              </button>
            ) : (
              <>
                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Forma de pago</th>
                        <th className="derecha">Importe</th>
                        <th>Cuenta donde entra</th>
                        <th>Detalle</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagos.map((p, i) => (
                        <tr key={i}>
                          <td>
                            <select
                              value={p.forma_pago}
                              onChange={setPago(i, "forma_pago")}
                              aria-label="Forma de pago"
                            >
                              {Object.entries(FORMAS).map(([k, v]) => (
                                <option key={k} value={k}>
                                  {v}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="derecha">
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={p.importe}
                              onChange={setPago(i, "importe")}
                              placeholder="0,00"
                              aria-label="Importe del pago"
                            />
                          </td>
                          <td>
                            <select
                              value={p.cuenta_id || ""}
                              onChange={setPago(i, "cuenta_id")}
                              aria-label="Cuenta"
                            >
                              <option value="">Elegí la cuenta…</option>
                              {cuentas.map((c) => (
                                <option key={c.id_cuenta} value={c.id_cuenta}>
                                  {c.codigo} {c.nombre}
                                </option>
                              ))}
                            </select>
                            {requiereBanco(p.forma_pago) && (
                              <small className="nota">
                                Esta forma no tiene cuenta fija: elegí el banco.
                              </small>
                            )}
                          </td>
                          <td>
                            <input
                              type="text"
                              value={p.detalle || ""}
                              onChange={setPago(i, "detalle")}
                              placeholder="Opcional"
                              aria-label="Detalle"
                            />
                          </td>
                          <td className="acciones">
                            <button
                              type="button"
                              className="btn btn-sm peligro"
                              onClick={() => quitarPago(i)}
                            >
                              Quitar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <th colSpan={1}>Suma de los pagos</th>
                        <th className="derecha">{numero(totales.pagos)}</th>
                        <th colSpan={3} className="nota">
                          El recibo es de {numero(datos.importe)}.
                        </th>
                      </tr>
                    </tfoot>
                  </table>
                </div>
                <div className="form-acciones" style={{ gap: "0.5rem" }}>
                  <button type="button" className="btn btn-sm" onClick={agregarPago}>
                    + Agregar otra
                  </button>
                  {pagos.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-sm fantasma"
                      onClick={usarTodoElImporte}
                    >
                      Completar el último
                    </button>
                  )}
                </div>
              </>
            )}
          </fieldset>
        )}

        {/* ------------------------------------------- 4. cómo queda */}
        {(preview || pidiendoPreview) && (
          <fieldset className="fieldset">
            <legend>4 · Cómo queda</legend>
            {pidiendoPreview && <p className="nota">Calculando…</p>}
            {preview && (
              <>
                {preview.avisos.map((a, i) => (
                  <p key={i} className="aviso-amarillo">
                    {a}
                  </p>
                ))}

                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Documento que se cobra</th>
                        <th>Concepto</th>
                        <th className="derecha">Saldo</th>
                        <th className="derecha">Se cobra</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.facturas.map((f) => (
                        <tr key={f.id}>
                          <td className="mono">
                            {f.punto_venta}-{f.numero}
                          </td>
                          <td>{f.concepto || "—"}</td>
                          <td className="mono derecha">{numero(f.saldo)}</td>
                          <td className="mono derecha">{numero(f.a_aplicar)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <th colSpan={3}>Total del recibo</th>
                        <th className="derecha">{numero(preview.importe)}</th>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {preview.asiento ? (
                  <>
                    <p className="nota" style={{ marginTop: "1rem" }}>
                      Asiento {preview.asiento.codigo_comprobante} —{" "}
                      {preview.asiento.concepto}
                    </p>
                    <table className="tabla as-tabla">
                      <thead>
                        <tr>
                          <th>Cuenta</th>
                          <th className="as-dinero">Debe</th>
                          <th className="as-dinero">Haber</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.asiento.lineas.map((l, i) => (
                          <tr key={i}>
                            <td>
                              <b>{l.codigo}</b> {l.nombre_cuenta}
                              {l.auxiliar && <small className="nota"> · {l.auxiliar}</small>}
                            </td>
                            <td className="as-dinero">{l.debe ? numero(l.debe) : ""}</td>
                            <td className="as-dinero">{l.haber ? numero(l.haber) : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <th>Totales</th>
                          <th className="as-dinero">
                            {numero(preview.asiento.total_debe)}
                          </th>
                          <th className="as-dinero">
                            {numero(preview.asiento.total_haber)}
                          </th>
                        </tr>
                      </tfoot>
                    </table>
                    <p className="ok">
                      Cierra: el Debe y el Haber dan {numero(preview.asiento.total_debe)}.
                    </p>
                  </>
                ) : (
                  <p className="error">
                    No se pudo armar el asiento. Corregí lo de arriba y vuelve a
                    mirar la vista previa.
                  </p>
                )}
              </>
            )}
          </fieldset>
        )}

        {/* ------------------------------------------ 5. confirmar */}
        <div className="form-acciones">
          <button
            className="btn"
            type="submit"
            disabled={enviando || !listoParaConfirmar}
          >
            {enviando ? "Guardando…" : "5 · Confirmar recibo"}
          </button>
          <button
            className="btn"
            type="button"
            disabled={enviando || !listoParaConfirmar}
            onClick={guardarYAsentar}
          >
            Confirmar y generar el asiento
          </button>
          <button
            className="btn fantasma"
            type="button"
            onClick={() => navigate("/recibos")}
          >
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}