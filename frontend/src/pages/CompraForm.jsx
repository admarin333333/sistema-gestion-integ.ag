import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { listarProveedores } from "../api/clientes.js";
import { listarAlicuotas } from "../api/alicuotas.js";
import {
  TIPOS,
  aPayload,
  actualizarCompra,
  crearCompra,
  listarCentrosCuentas,
  obtenerCompra,
  previewAsientoCompra,
} from "../api/compras.js";
import { pesos } from "../formato.js";

const HOY = new Date().toISOString().slice(0, 10);

const VACIO = {
  proveedor_id: "",
  fecha: HOY,
  tipo_comprobante: "factura_a",
  punto_venta: "0001",
  numero: "",
  concepto: "",
  neto: "",
  alicuota_iva_id: "",
  percepcion_iva: "",
  cuenta_gasto_id: "",
  fecha_vencimiento: "",
};

export default function CompraForm() {
  const { id: compraId } = useParams();
  const navigate = useNavigate();
  const esEdicion = Boolean(compraId);
  const [datos, setDatos] = useState(VACIO);
  const [proveedores, setProveedores] = useState([]);
  const [arbol, setArbol] = useState({ centros: [] });
  const [alicuotas, setAlicuotas] = useState([]);
  const [preview, setPreview] = useState(null);
  const [cargando, setCargando] = useState(esEdicion);
  const [previsualizando, setPrevisualizando] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    listarProveedores()
      .then(setProveedores)
      .catch(() => setProveedores([]));
    listarAlicuotas()
      .then(setAlicuotas)
      .catch(() => setAlicuotas([]));
    // El árbol de centros y cuentas sale del PLAN DE CUENTAS: es la misma
    // estructura que muestra el informe por centro de costos, así que la
    // compra no puede elegir un gasto que el informe no vaya a mostrar.
    listarCentrosCuentas()
      .then(setArbol)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!esEdicion) return;
    obtenerCompra(compraId)
      .then((c) => {
        setDatos({
          proveedor_id: String(c.proveedor_id),
          fecha: c.fecha,
          tipo_comprobante: c.tipo_comprobante,
          punto_venta: c.punto_venta,
          numero: c.numero,
          concepto: c.concepto || "",
          neto: c.neto,
          alicuota_iva_id: String(c.alicuota_iva_id),
          percepcion_iva: c.percepcion_iva || "",
          cuenta_gasto_id: c.cuenta_gasto_id ? String(c.cuenta_gasto_id) : "",
          fecha_vencimiento: c.fecha_vencimiento || "",
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [compraId, esEdicion]);

  const set = (campo) => (e) => {
    const valor = e.target.value;
    setDatos((d) => ({ ...d, [campo]: valor }));
    setPreview(null);
  };

  // Vista previa: mismo cálculo que hace el backend (neto × alícuota + percepción).
  const alicuotaSel = alicuotas.find(
    (a) => String(a.id) === String(datos.alicuota_iva_id)
  );
  const netoNum = Number(datos.neto || 0);
  const ivaPrev = alicuotaSel
    ? Math.round(netoNum * Number(alicuotaSel.porcentaje)) / 100
    : 0;
  const percepcionNum = Number(datos.percepcion_iva || 0);
  const totalPrev =
    Math.round((netoNum + ivaPrev + percepcionNum) * 100) / 100;

  const faltaAlgo =
    !datos.proveedor_id ||
    !datos.cuenta_gasto_id ||
    !datos.alicuota_iva_id ||
    !datos.numero ||
    !(netoNum > 0);

  /** El asiento que va a quedar, sin guardarlo. Se recalcula solo cuando
   *  cambian los importes o la cuenta. */
  const verAsiento = async () => {
    setPrevisualizando(true);
    setError("");
    setPreview(null);
    try {
      setPreview(
        await previewAsientoCompra({
          proveedor_id: Number(datos.proveedor_id),
          fecha: datos.fecha,
          tipo_comprobante: datos.tipo_comprobante,
          punto_venta: datos.punto_venta,
          numero: datos.numero,
          concepto: datos.concepto,
          neto: netoNum,
          iva: ivaPrev,
          percepcion_iva: percepcionNum,
          total: totalPrev,
          cuenta_gasto_id: Number(datos.cuenta_gasto_id),
        })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPrevisualizando(false);
    }
  };

  // Se previsualiza solo cuando ya se puede armar (todos los datos puestos) y
  // algo del asiento cambió. Es la misma función que usa el botón de asentar,
  // así que lo que se ve acá es exactamente lo que se guarda.
  useEffect(() => {
    if (faltaAlgo) {
      setPreview(null);
      return;
    }
    let cancelado = false;
    const t = setTimeout(async () => {
      try {
        const p = await previewAsientoCompra({
          proveedor_id: Number(datos.proveedor_id),
          fecha: datos.fecha,
          tipo_comprobante: datos.tipo_comprobante,
          punto_venta: datos.punto_venta,
          numero: datos.numero,
          concepto: datos.concepto,
          neto: netoNum,
          iva: ivaPrev,
          percepcion_iva: percepcionNum,
          total: totalPrev,
          cuenta_gasto_id: Number(datos.cuenta_gasto_id),
        });
        if (!cancelado) setPreview(p);
      } catch {
        // Si el preview falla no se interrumpe la carga: el backend valida
        // igual al guardar y ahí se ve el error con el mensaje del contador.
        if (!cancelado) setPreview(null);
      }
    }, 350);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    datos.proveedor_id,
    datos.fecha,
    datos.tipo_comprobante,
    datos.punto_venta,
    datos.numero,
    datos.concepto,
    datos.cuenta_gasto_id,
    netoNum,
    ivaPrev,
    percepcionNum,
    totalPrev,
  ]);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      const cuerpo = aPayload(datos);
      if (esEdicion) {
        await actualizarCompra(compraId, cuerpo);
      } else {
        await crearCompra(cuerpo);
      }
      navigate("/compras");
    } catch (e2) {
      setError(e2.message);
    } finally {
      setEnviando(false);
    }
  };

  const proveedor = proveedores.find(
    (p) => String(p.id) === String(datos.proveedor_id)
  );

  if (cargando) return <p className="nota">Cargando…</p>;

  return (
    <section>
      <span className="kicker">Compras</span>
      <h1>{esEdicion ? "Modificar compra" : "Nueva compra"}</h1>
      <p className="lead">
        Los campos con <span style={{ color: "var(--accent-3)" }}>*</span> son
        obligatorios. El IVA y el total los calcula el sistema.
      </p>

      {error && <p className="error">{error}</p>}

      <form className="form" onSubmit={enviar}>
        <fieldset className="fieldset">
          <legend>Comprobante del proveedor</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Proveedor <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.proveedor_id}
                onChange={set("proveedor_id")}
                disabled={esEdicion}
              >
                <option value="">Elegí un proveedor…</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre_completo} (cta. {p.nro_cuenta})
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>
                Tipo <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.tipo_comprobante}
                onChange={set("tipo_comprobante")}
              >
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
            </label>

            <label className="campo">
              <span>Concepto</span>
              <input
                value={datos.concepto}
                onChange={set("concepto")}
                placeholder="Compra de insumos…"
              />
            </label>
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <legend>Importes e imputación</legend>
          <div className="form-grid">
            <label className="campo">
              <span>
                Importe neto <b className="obligatorio">*</b>
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={datos.neto}
                onChange={set("neto")}
                placeholder="0,00"
              />
            </label>

            <label className="campo">
              <span>
                Alícuota IVA <b className="obligatorio">*</b>
              </span>
              <select
                value={datos.alicuota_iva_id}
                onChange={set("alicuota_iva_id")}
              >
                <option value="">Elegí una…</option>
                {alicuotas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo">
              <span>Percepción IVA</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={datos.percepcion_iva}
                onChange={set("percepcion_iva")}
                placeholder="0,00"
              />
            </label>

            {/* Una sola elección: la cuenta de gasto del plan. El centro de
                costos NO se elige aparte, sale de la cuenta (6.1.03 → 6.1
                Administración). Antes había dos campos (centro + tipo de gasto)
                y podían contradecir al plan. */}
            <label className="campo campo-ancho">
              <span>
                Cuenta de gasto del plan <b className="obligatorio">*</b>
              </span>
              <select value={datos.cuenta_gasto_id} onChange={set("cuenta_gasto_id")}>
                <option value="">Elegí la cuenta donde va el gasto…</option>
                {arbol.centros.map((c) => (
                  <optgroup key={c.id} label={`${c.codigo} ${c.nombre}`}>
                    {c.cuentas.map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.codigo} · {k.nombre}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
          </div>

          <p className="nota">
            IVA: <b>{pesos(ivaPrev)}</b> · Total:{" "}
            <b style={{ color: "var(--accent-3)" }}>{pesos(totalPrev)}</b>
            {datos.cuenta_gasto_id && centroDe(arbol, datos.cuenta_gasto_id) && (
              <>
                {" "}
                · Centro: <b>{centroDe(arbol, datos.cuenta_gasto_id)}</b>
              </>
            )}
          </p>
        </fieldset>

        {/* El preview del asiento. Sale de la MISMA función del backend que
            genera el asiento real, así que lo que se ve acá es exactamente lo
            que se guarda: no hay preview que difiera del asiento. */}
        <fieldset className="fieldset">
          <legend>Cómo queda el asiento</legend>

          {!faltaAlgo && (
            <p className="nota">
              Esto todavía <b>no</b> está en los libros. Guardar la compra no
              mueve ninguna cuenta: el asiento se genera aparte, desde el
              listado de compras.
            </p>
          )}

          {faltaAlgo && (
            <p className="nota">
              Completá proveedor, número, importe, alícuota y cuenta de gasto
              para ver el asiento.
            </p>
          )}

          {previsualizando && <p className="nota">Calculando…</p>}

          {preview && (
            <div className="tabla-envoltura">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Cuenta</th>
                    <th>Nombre</th>
                    <th className="derecha">Debe</th>
                    <th className="derecha">Haber</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.lineas.map((l, i) => (
                    <tr key={`${l.id_cuenta}-${i}`}>
                      <td className="mono">{l.codigo}</td>
                      <td>
                        {l.nombre_cuenta}
                        {l.tipo_auxiliar && proveedor && (
                          <small>{proveedor.nombre_completo}</small>
                        )}
                      </td>
                      <td className="mono derecha">
                        {Number(l.debe) ? pesos(l.debe) : ""}
                      </td>
                      <td className="mono derecha">
                        {Number(l.haber) ? pesos(l.haber) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan="2">
                      <b>Total</b>
                    </td>
                    <td className="mono derecha">
                      <b>{pesos(preview.total_debe)}</b>
                    </td>
                    <td className="mono derecha">
                      <b>{pesos(preview.total_haber)}</b>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          {preview && (
            <p className={preview.balanceado ? "ok" : "error"}>
              {preview.balanceado
                ? `Cierra: el Debe y el Haber dan ${pesos(preview.total_debe)}.`
                : "El asiento no cierra."}
              {preview.aviso ? ` ${preview.aviso}` : ""}
            </p>
          )}

          <button
            type="button"
            className="btn btn-sm fantasma"
            onClick={verAsiento}
            disabled={faltaAlgo || previsualizando}
          >
            Ver el asiento de nuevo
          </button>
        </fieldset>

        <div className="form-acciones">
          <button className="btn" type="submit" disabled={enviando}>
            {enviando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Dar de alta"}
          </button>
          <button
            className="btn fantasma"
            type="button"
            onClick={() => navigate("/compras")}
          >
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}

/** El nombre del centro al que pertenece una cuenta de gasto ("6.1 → Gastos
 *  de administración"). Es el mismo criterio que usa el backend, para que el
 *  texto de la pantalla no diga una cosa y el informe otra. */
function centroDe(arbol, cuentaId) {
  for (const c of arbol.centros || []) {
    if (c.cuentas.some((k) => String(k.id) === String(cuentaId))) return c.nombre;
  }
  return "";
}
