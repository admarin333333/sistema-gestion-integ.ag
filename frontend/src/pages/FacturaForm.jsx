import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { listarClientes } from "../api/clientes.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import {
  CONDICIONES,
  OPERACIONES,
  TIPOS,
  aPayload,
  actualizarFactura,
  crearFactura,
  enviarFacturas,
  listarAlicuotas,
  listarFacturas,
  obtenerFactura,
  previewAsiento,
} from "../api/facturas.js";

const HOY = new Date().toISOString().slice(0, 10);

/** Los días de plazo que maneja el contador para la deuda vencida. */
export const DIAS_PLAZO = 7;

/**
 * La fecha de vencimiento que sale sola: 7 días después de la de la factura.
 *
 * Se cuenta en días del calendario (no hábiles): es el plazo que pidió el
 * contador el 02/10/2026, y para un software contable lo que importa es que
 * todos los meses den el mismo número, no que un fin de semana corra el plazo.
 */
export function venceEn(fecha, dias = DIAS_PLAZO) {
  if (!fecha) return "";
  const f = new Date(`${fecha}T00:00:00`);
  if (Number.isNaN(f.getTime())) return "";
  f.setDate(f.getDate() + dias);
  return f.toISOString().slice(0, 10);
}

const VACIO = {
  cliente_id: "",
  fecha: HOY,
  tipo_comprobante: "factura_b",
  punto_venta: "0001",
  numero: "",
  concepto: "",
  importe: "",
  fecha_vencimiento: "",
  condicion_venta: "contado",
  cae: "",
  cae_vencimiento: "",
  // Para el asiento:
  tipo_operacion: "SERVICIOS",
  alicuota_iva_id: "",
  // Solo para las notas: la factura a la que corrigen.
  factura_relacionada_id: "",
};

/** El backend devuelve los importes como número; acá se muestran con coma. */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Alta y modificación de facturas.
 *
 * La diferencia con antes: **antes de guardar nada se ve el asiento**. El
 * botón dice "OK, facturar" y no se toca hasta que el contador miró lo que
 * va a quedar asentado. Recién ahí se guarda, con el asiento ya
 * contabilizado.
 *
 * El preview lo arma el backend (POST /facturas/preview-asiento) y usa la
 * misma función que después genera el asiento real, así que lo que se ve
 * acá es exactamente lo que se guarda: no puede haber diferencia.
 */
export default function FacturaForm() {
  const { id: facturaId } = useParams();
  const navigate = useNavigate();
  const esEdicion = Boolean(facturaId);

  const [datos, setDatos] = useState(VACIO);
  const [clientes, setClientes] = useState([]);
  const [alicuotas, setAlicuotas] = useState([]);
  const [cargando, setCargando] = useState(esEdicion);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  // El cliente elegido, para que el buscador muestre su nombre completo en vez
  // del número guardado en `datos.cliente_id`.
  //
  // Va DESPUÉS de `clientes`: si se usara antes, el componente tiraría
  // "Cannot access 'clientes' before initialization" y la pantalla quedaría en
  // blanco. Pasa porque los `useState` y los cálculos derived se mezclan.
  const clienteElegido = clientes.find(
    (c) => String(c.id) === String(datos.cliente_id)
  );

  // Las facturas del cliente, para que una nota de crédito pueda elegir a cuál
  // corrige. Solo se piden cuando el tipo es una nota: cargar la lista para
  // todas las facturas sería una consulta de más siempre.
  const [facturasCliente, setFacturasCliente] = useState([]);

  // El preview del asiento
  const [preview, setPreview] = useState(null);
  const [pidiendoPreview, setPidiendoPreview] = useState(false);

  // ¿El tipo elegido es una nota? Lo decide el NOMBRE del tipo ("nota_..."),
  // no una lista aparte: si mañana se agrega un tipo nuevo con prefijo "nota",
  // esto ya funciona sin tocarlo.
  const esNota = String(datos.tipo_comprobante || "").startsWith("nota_");

  // Cuando es una nota, se piden las facturas del cliente para elegir cuál
  // corrige. `facturasCliente` se borra al cambiar de cliente o de tipo, así
  // no queda la lista del cliente anterior.
  useEffect(() => {
    if (!esNota || !datos.cliente_id) {
      setFacturasCliente([]);
      return;
    }
    let vigente = true;
    listarFacturas({ cliente_id: datos.cliente_id })
      .then((fs) => {
        if (vigente) setFacturasCliente(fs || []);
      })
      .catch(() => {
        if (vigente) setFacturasCliente([]);
      });
    return () => {
      vigente = false;
    };
  }, [esNota, datos.cliente_id]);

  // Al cambiar de tipo, la factura relacionada se limpia: una factura no
  // "hereda" la que se eligió cuando era de otro tipo.
  useEffect(() => {
    setDatos((d) => ({ ...d, factura_relacionada_id: "" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos.tipo_comprobante]);

  /**
   * El VENCIMIENTO sale solo, 7 días después de la fecha de la factura.
   *
   * El 7 es el plazo que maneja el contador; lo pidió el 02/10/2026. Se calcula
   * en el navegador y no en el backend a propósito: es una ayuda de la pantalla,
   * y el backend no debe inventar una fecha que el contador puede cambiar. Si lo
   * imposed el backend, corregirlo después sería una modificación más.
   *
   * Solo se completa si el campo está vacío: así, si el contador puso un
   * vencimiento a mano, cambiar la fecha de la factura no le pisa lo que ya
   * eligió.
   */
  useEffect(() => {
    if (esEdicion) return; // al editar, la fecha ya está: no se toca
    if (!datos.fecha) return;
    if (datos.fecha_vencimiento) return;
    setDatos((d) => ({ ...d, fecha_vencimiento: venceEn(datos.fecha) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos.fecha, esEdicion]);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
    // Las alícuotas vienen del catálogo: si el contador agrega una 5% más
    // adelante, aparece sola acá sin tocar el formulario.
    listarAlicuotas()
      .then(setAlicuotas)
      .catch(() => setAlicuotas([]));
  }, []);

  useEffect(() => {
    if (!esEdicion) return;
    obtenerFactura(facturaId)
      .then((f) => {
        setDatos({
          cliente_id: String(f.cliente_id),
          fecha: f.fecha,
          tipo_comprobante: f.tipo_comprobante,
          punto_venta: f.punto_venta,
          numero: f.numero,
          concepto: f.concepto || "",
          importe: f.importe,
          fecha_vencimiento: f.fecha_vencimiento || "",
          condicion_venta: f.condicion_venta,
          cae: f.cae || "",
          cae_vencimiento: f.cae_vencimiento || "",
          tipo_operacion: f.tipo_operacion || "SERVICIOS",
          alicuota_iva_id: f.alicuota_iva_id ? String(f.alicuota_iva_id) : "",
          factura_relacionada_id: f.factura_relacionada_id
            ? String(f.factura_relacionada_id)
            : "",
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [facturaId, esEdicion]);

  const set = (campo) => (e) =>
    setDatos((d) => ({ ...d, [campo]: e.target.value }));

  // ------------------------------------------------------------------ preview
  /** Pide al backend cómo quedaría el asiento. No guarda nada. */
  const pedirPreview = async () => {
    const cuerpo = aPayload(datos);
    // Con estos dos vacíos no hay nada que mostrar: no se llama al backend
    // para que no devuelva un error que el contador no puede corregir.
    if (!cuerpo.cliente_id || !cuerpo.importe || cuerpo.importe <= 0) {
      setPreview(null);
      return;
    }
    setPidiendoPreview(true);
    try {
      const r = await previewAsiento(cuerpo);
      setPreview(r);
      setError("");
    } catch (e) {
      setPreview(null);
      setError(e.message);
    } finally {
      setPidiendoPreview(false);
    }
  };

  // Se vuelve a pedir cada vez que cambia algo que va al asiento. Con medio
  // segundo de espera para no pegarle una consulta por tecla.
  useEffect(() => {
    const t = setTimeout(pedirPreview, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    datos.cliente_id,
    datos.importe,
    datos.alicuota_iva_id,
    datos.tipo_operacion,
    datos.condicion_venta,
    // El TIPO importa: si es una nota de crédito, el preview muestra el asiento
    // al revés y el código `NC`. Sin esto, cambiar de Factura a Nota dejaría en
    // pantalla el asiento de la venta, que es justo el error que había.
    datos.tipo_comprobante,
    datos.factura_relacionada_id,
  ]);

  // ------------------------------------------------------------------- guardar
  const guardar = async () => {
    const cuerpo = aPayload(datos);
    return esEdicion
      ? await actualizarFactura(facturaId, cuerpo)
      : await crearFactura(cuerpo);
  };

  const facturar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      await guardar();
      navigate("/facturas");
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  /** Guarda y manda el comprobante por mail. */
  const guardarYEnviar = async () => {
    setEnviando(true);
    setError("");
    try {
      const r = await guardar();
      const res = await enviarFacturas([r.id]);
      navigate("/facturas", { state: { aviso: res.avisos.join(" · ") || null } });
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  // El botón "OK, facturar" se deshabilita si el preview todavía no llegó:
  // facturar a ciegas es justo lo que se quiere evitar.
  //
  // Y si es una NOTA, además tiene que estar elegida la factura que corrige:
  // el backend la exige, así que avisarlo acá es más amable que devolver un
  // error después de apretar.
  const listoParaFacturar =
    Boolean(preview) &&
    !pidiendoPreview &&
    !enviando &&
    (!esNota || Boolean(datos.factura_relacionada_id));

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">Facturas</span>
      <h1>{esEdicion ? "Modificar factura" : "Nueva factura"}</h1>
      <p className="lead">
        Cargá la factura y mirá cómo queda el asiento. Recién cuando esté
        bien, apretá <b>OK, facturar</b>.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={facturar}>
        <fieldset className="fieldset">
          <legend>Comprobante</legend>
          <div className="form-grid">
            {/* Buscador y no lista desplegada: se escribe el nombre, el CUIT o el DNI.
                Con la lista había que buscar scrolleando dentro del
                desplegable, y al cargar una factura uno ya tiene el cliente en
                la cabeza: lo escribe y aparece. */}
            <BuscadorCliente
              clientes={clientes}
              seleccion={clienteElegido}
              onElegir={(c) => setDatos((d) => ({ ...d, cliente_id: c ? String(c.id) : "" }))}
              tipo_registro="cliente"
              etiqueta="Cliente *"
              placeholder="Escribí el nombre, el CUIT o el DNI…"
            />

            <label className="campo">
              <span>
                Tipo <b className="obligatorio">*</b>
              </span>
              <select value={datos.tipo_comprobante} onChange={set("tipo_comprobante")}>
                {Object.entries(TIPOS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Punto de venta <b className="obligatorio">*</b>
              </span>
              <input value={datos.punto_venta} onChange={set("punto_venta")} />
            </label>

            <label className="campo">
              <span>
                Número <b className="obligatorio">*</b>
              </span>
              <input
                value={datos.numero}
                onChange={set("numero")}
                placeholder="00000001"
              />
            </label>

            <label className="campo">
              <span>
                Fecha <b className="obligatorio">*</b>
              </span>
              <input type="date" value={datos.fecha} onChange={set("fecha")} />
            </label>

            <label className="campo">
              <span>Vencimiento</span>
              <input
                type="date"
                value={datos.fecha_vencimiento}
                onChange={set("fecha_vencimiento")}
              />
              {!esEdicion && datos.fecha_vencimiento && (
                <small className="nota">
                  Sale solo a los {DIAS_PLAZO} días. Cambialo si este cliente
                  tiene otro plazo.
                </small>
              )}
            </label>

            <label className="campo">
              <span>
                Importe (total) <b className="obligatorio">*</b>
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={datos.importe}
                onChange={set("importe")}
                placeholder="0,00"
              />
            </label>

            <label className="campo">
              <span>
                Condición de venta <b className="obligatorio">*</b>
              </span>
              <select value={datos.condicion_venta} onChange={set("condicion_venta")}>
                {Object.entries(CONDICIONES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>

            {/* Solo en las notas. Una nota sin saber a qué factura corrige es
                un papel suelto: el contador no puede saber si el cliente ya
                pagó lo que se le está descontando. */}
            {esNota && (
              <label className="campo" style={{ flex: "1 1 100%" }}>
                <span>
                  Corrige a la factura{" "}
                  <b className="obligatorio">*</b>
                </span>
                <select
                  value={datos.factura_relacionada_id}
                  onChange={set("factura_relacionada_id")}
                >
                  <option value="">Elegí la factura que corrige…</option>
                  {facturasCliente.map((f) => (
                    <option key={f.id} value={f.id}>
                      Factura {f.punto_venta}-{f.numero} del {f.fecha} —{" "}
                      {numero(f.importe)} — {f.estado}
                    </option>
                  ))}
                </select>
                <small className="nota">
                  {facturasCliente.length === 0
                    ? "Este cliente no tiene facturas para corregir."
                    : "La nota se descuenta de esta factura."}
                </small>
              </label>
            )}
          </div>
        </fieldset>

        {/* ---------------------------------------------------- el IVA y la cuenta */}
        <fieldset className="fieldset">
          <legend>Para el asiento contable</legend>
          <p className="nota">
            Estos dos campos no cambian la factura: definen a qué cuenta va el
            Haber y cómo se desglosa el IVA.
          </p>
          <div className="form-grid">
            <label className="campo">
              <span>¿Qué se está facturando?</span>
              <select value={datos.tipo_operacion} onChange={set("tipo_operacion")}>
                {Object.entries(OPERACIONES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>Alícuota de IVA</span>
              <select value={datos.alicuota_iva_id} onChange={set("alicuota_iva_id")}>
                <option value="">Sin IVA</option>
                {alicuotas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <legend>Datos interno</legend>
          <div className="form-grid">
            <label className="campo">
              <span>Concepto</span>
              <input
                value={datos.concepto}
                onChange={set("concepto")}
                placeholder="Honorarios de mes…"
              />
            </label>

            <label className="campo">
              <span>CAE — opcional</span>
              <input value={datos.cae} onChange={set("cae")} />
            </label>

            <label className="campo">
              <span>Vto. CAE — opcional</span>
              <input
                type="date"
                value={datos.cae_vencimiento}
                onChange={set("cae_vencimiento")}
              />
            </label>
          </div>
        </fieldset>

        {/* -------------------------------------------------- el preview del asiento */}
        {preview && (
          <div className="as-preview">
            <h2>
              Así va a quedar el asiento{" "}
              <small className="nota">({preview.numero_completo_tentativo})</small>
            </h2>

            {preview.aviso && <p className="aviso-amarillo">{preview.aviso}</p>}

            {/* La nota de crédito al revés lo dice el backend (`familia`), no el
                navegador. Si no lo dijera, el contador vería el mismo asiento
                que en la venta y no se llevaría cuenta del cambio. */}
            {preview.familia === "CREDITO" && (
              <p className="nota">
                Esto es una nota de crédito: el asiento va <b>al revés</b> que
                en una factura, porque revierte la venta.
              </p>
            )}
            {preview.familia === "DEBITO" && (
              <p className="nota">
                Esto es una nota de débito: el asiento va igual que en una
                factura, porque aumenta lo facturado.
              </p>
            )}

            {/* Si el preview no cierra, el backend lo avisa. Con el código de
                esto hardcodeado pasaba que una nota mostraba 121.000 contra
                100.000 y la pantalla decía que cerraba. */}
            {preview.cierra === false && (
              <p className="error">
                El asiento no cierra: el Debe y el Haber dan distinto. No lo
                guardes; avisá porque hay un problema de configuración.
              </p>
            )}

            <table className="tabla as-tabla">
              <thead>
                <tr>
                  <th>Cuenta</th>
                  <th className="as-dinero">Debe</th>
                  <th className="as-dinero">Haber</th>
                </tr>
              </thead>
              <tbody>
                {preview.lineas.map((l, i) => (
                  <tr key={i}>
                    <td>
                      <b>{l.codigo}</b> {l.nombre_cuenta}
                      {l.tipo_auxiliar && (
                        <small className="nota"> · {l.tipo_auxiliar}</small>
                      )}
                    </td>
                    <td className="as-dinero">{l.debe ? numero(l.debe) : ""}</td>
                    <td className="as-dinero">{l.haber ? numero(l.haber) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th>Totales</th>
                  <th className="as-dinero">{numero(preview.total_debe)}</th>
                  <th className="as-dinero">{numero(preview.total_haber)}</th>
                </tr>
              </tfoot>
            </table>

            <p className="ok">
              Cierra: el Debe y el Haber dan lo mismo. Al apretar "OK, facturar"
              se guarda la factura y el asiento queda contabilizado.
            </p>
          </div>
        )}

        {pidiendoPreview && (
          <p className="nota">Calculando el asiento…</p>
        )}

        {/* Aviso de que falta lo único que no se puede adivinar: a qué factura
            corrige la nota. */}
        {esNota && !datos.factura_relacionada_id && preview && (
          <p className="aviso-amarillo">
            Elegí la factura que corrige. Una nota sin esa referencia no se
            puede guardar: sin saber a qué factura se descuenta, el saldo del
            cliente queda sin explicar.
          </p>
        )}

        {/* ------------------------------------------------------------ botones */}
        <div className="form-acciones">
          <button
            className="btn"
            type="submit"
            disabled={!listoParaFacturar}
            title={
              preview
                ? "Guarda la factura y su asiento"
                : "Cargá cliente e importe para ver el asiento"
            }
          >
            {enviando
              ? "Guardando…"
              : esEdicion
              ? "OK, guardar cambios"
              : "OK, facturar"}
          </button>
          <button
            className="btn fantasma"
            type="button"
            disabled={enviando}
            onClick={guardarYEnviar}
          >
            Facturar y enviar por mail
          </button>
          <button className="btn fantasma" type="button" onClick={() => navigate("/facturas")}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}