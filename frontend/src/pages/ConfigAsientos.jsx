import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  buscarCuentas,
  guardarConfigAsiento,
  guardarConfigComprobante,
  listarConfigAsientos,
  listarConfigComprobantes,
} from "../api/asientos.js";

/**
 * CONFIGURACIÓN DE LOS ASIENTOS AUTOMÁTICOS.
 *
 * Qué cuenta va en cada lado de cada operación. Son DATOS, no código: por eso
 * están en tablas editables. Si el contador cambia "Documentos a cobrar" por
 * "Clientes", o manda las notas de crédito a otra cuenta de ingresos, se
 * corrige acá y no hay que tocar el programa.
 *
 * **Lo que se puede cambiar:** las CUENTAS (Debe, ingresos, IVA, cobranza).
 * **Lo que no:** los nombres de cada caso ni si están activos. Un caso mal
 * configurado se corrige, no se desactiva: desactivar el asiento de una venta
 * dejaría las facturas sin asentar, en silencio.
 *
 * Ojo con las notas: su asiento está **al revés** que el de la venta (ingresos
 * en el Debe, documentos en el Haber). Por eso son filas separadas y no una
 * bandera: si se invirtiera el signo en el momento de armar el asiento, un
 * error de tipeo en la cuenta mandaría todas las notas al lado incorrecto.
 */
export default function ConfigAsientos() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [asientos, setAsientos] = useState([]);
  const [comprobantes, setComprobantes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [editando, setEditando] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      const [a, c] = await Promise.all([
        listarConfigAsientos(),
        listarConfigComprobantes(),
      ]);
      setAsientos(a);
      setComprobantes(c);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const guardar = async (clave, cuentas) => {
    setGuardando(true);
    setError("");
    setMensaje("");
    try {
      await guardarConfigAsiento(clave, cuentas);
      setMensaje(`Guardado: ${clave}`);
      setEditando(null);
      await cargar();
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  const alternarComprobante = async (c) => {
    setError("");
    setMensaje("");
    try {
      await guardarConfigComprobante(c.codigo, {
        nombre: c.nombre,
        activa: !c.activa,
      });
      await cargar();
    } catch (e) {
      setError(e.message);
    }
  };

  // Las ventas y las notas van en tablas separadas: es lo que hace evidente
  // que la nota de crédito está al revés.
  const ventas = useMemo(
    () => asientos.filter((a) => a.clave.startsWith("VENTA_")),
    [asientos]
  );
  const notas = useMemo(
    () => asientos.filter((a) => a.clave.startsWith("CREDITO_") || a.clave.startsWith("DEBITO_")),
    [asientos]
  );
  const cobranza = useMemo(
    () => asientos.filter((a) => a.clave === "COBRANZA"),
    [asientos]
  );

  return (
    <section>
      <span className="kicker">Contabilidad</span>
      <h1>Asientos automáticos</h1>
      <p className="lead">
        Qué cuenta va en cada lado de cada operación. Se cambia acá y no hace
        falta tocar el programa. Solo el administrador puede guardar.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="ok">{mensaje}</p>}
      {cargando && <p className="nota">Cargando…</p>}

      {/* -------------------------------------------------- códigos internos */}
      {!cargando && (
        <>
          <h3 className="as-subtitulo">Códigos de comprobante</h3>
          <p className="nota">
            Cada código numera por su cuenta. La A, la B o la C de un tipo no
            cambian el asiento: por eso hay un solo código de nota, no tres.
          </p>
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th>Se usa para</th>
                <th className="derecha">Emitidos</th>
                <th>Estado</th>
                {esAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {comprobantes.map((c) => (
                <tr key={c.codigo} className={c.activa ? "" : "inactivo"}>
                  <td>
                    <b className="mono">{c.codigo}</b>
                  </td>
                  <td>{c.nombre}</td>
                  <td className="nota">{ORIGENES[c.origen] || "a mano"}</td>
                  <td className="mono derecha">{c.usados}</td>
                  <td>
                    <span className={`as-estado ${c.activa ? "contabilizado" : "anulado"}`}>
                      {c.activa ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  {esAdmin && (
                    <td className="acciones">
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => alternarComprobante(c)}
                        disabled={c.usados > 0 && c.activa}
                        title={
                          c.usados > 0 && c.activa
                            ? "No se puede desactivar: ya se emitieron comprobantes con este código"
                            : ""
                        }
                      >
                        {c.activa ? "Desactivar" : "Activar"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="nota">
            Un código con comprobantes emitidos no se puede desactivar: esos
            números ya existen y no pueden volver a usarse.
          </p>

          {/* ------------------------------------------------------ las ventas */}
          <h3 className="as-subtitulo">Ventas</h3>
          <p className="nota">
            Deben en Documentos a cobrar (la deuda del cliente) y haber en
            ingresos. La plata entra en el banco recién cuando se registra el
            cobro, en la cobranza de más abajo.
          </p>
          <TablaAsientos
            filas={ventas}
            editando={editando}
            setEditando={setEditando}
            guardar={guardar}
            guardando={guardando}
            esAdmin={esAdmin}
          />

          {/* ------------------------------------------------------- las notas */}
          <h3 className="as-subtitulo">Notas de crédito y de débito</h3>
          <p className="nota">
            Una nota de crédito <b>revierte</b> la venta: ingresos en el Debe y
            documentos en el Haber. Una nota de débito, en cambio, hace lo mismo
            que una factura (aumenta lo facturado), así que sus cuentas van
            derecho. Compará las dos filas: la de crédito está al revés, la de
            débito no.
          </p>
          <TablaAsientos
            filas={notas}
            editando={editando}
            setEditando={setEditando}
            guardar={guardar}
            guardando={guardando}
            esAdmin={esAdmin}
          />

          {/* ------------------------------------------------------ la cobranza */}
          {cobranza.length > 0 && (
            <>
              <h3 className="as-subtitulo">Cobranza</h3>
              <p className="nota">
                El Debe lo dice cada recibo (la cuenta donde entró la plata), así
                que acá solo va la cuenta del Haber: los documentos a cobrar que
                se cancelan.
              </p>
              <TablaAsientos
                filas={cobranza}
                editando={editando}
                setEditando={setEditando}
                guardar={guardar}
                guardando={guardando}
                esAdmin={esAdmin}
              />
            </>
          )}
        </>
      )}
    </section>
  );
}

const ORIGENES = {
  FACTURA: "facturas y notas",
  RECIBO: "recibos",
  MANUAL: "asientos manuales",
  null: "no se usa solo",
};

/* Cada familia de la tabla lleva su rótulo. La de DÉBITO NO va invertida
 * (lleva los ingresos en el Haber, como la venta), así que se decide por el
 * nombre de la clave y no por "es una nota". */
const VENTAS = (clave) => clave.startsWith("VENTA_");
const CREDITO = (clave) => clave.startsWith("CREDITO_");
const DEBITO = (clave) => clave.startsWith("DEBITO_");

function TablaAsientos({
  filas,
  editando,
  setEditando,
  guardar,
  guardando,
  esAdmin,
}) {
  return (
    <table className="tabla">
      <thead>
        <tr>
          <th>Operación</th>
          <th>Debe</th>
          <th>Haber (ingresos)</th>
          <th>IVA</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {filas.map((f) => (
          <FilaAsiento
            key={f.clave}
            fila={f}
            editando={editando === f.clave}
            setEditando={setEditando}
            guardar={guardar}
            guardando={guardando}
            esAdmin={esAdmin}
          />
        ))}
      </tbody>
    </table>
  );
}

function FilaAsiento({
  fila,
  editando,
  setEditando,
  guardar,
  guardando,
  esAdmin,
}) {
  if (editando) {
    return (
      <EditorFila
        fila={fila}
        guardarFn={guardar}
        cancel={() => setEditando(null)}
        guardando={guardando}
        invertido={CREDITO(fila.clave)}
      />
    );
  }
  return (
    <tr>
      <td>
        <b>{fila.nombre}</b>
        {CREDITO(fila.clave) && (
          <small className="nota"> · asiento invertido (revierte la venta)</small>
        )}
        {DEBITO(fila.clave) && (
          <small className="nota"> · igual que una factura</small>
        )}
      </td>
      <td>
        <Cuenta codigo={fila.debe_codigo} nombre={fila.debe_nombre} />
      </td>
      <td>
        <Cuenta codigo={fila.ing_codigo} nombre={fila.ing_nombre} />
      </td>
      <td>
        <Cuenta codigo={fila.iva_codigo} nombre={fila.iva_nombre} />
      </td>
      <td className="acciones">
        {esAdmin && (
          <button
            className="btn btn-sm fantasma"
            onClick={() => setEditando(fila.clave)}
          >
            Cambiar cuentas
          </button>
        )}
      </td>
    </tr>
  );
}

function Cuenta({ codigo, nombre }) {
  if (!codigo) return <span className="nota">— sin configurar —</span>;
  return (
    <span>
      <b className="mono">{codigo}</b>{" "}
      <span className="nota">{nombre}</span>
    </span>
  );
}

/** El renglón abierto para cambiar las cuentas. */
function EditorFila({ fila, guardarFn, cancel, guardando, invertido }) {
  const [debe, setDebe] = useState(fila.cuenta_debe || "");
  const [ingresos, setIngresos] = useState(fila.cuenta_haber_ingresos || "");
  const [iva, setIva] = useState(fila.cuenta_haber_iva || "");

  const cambiar = async () => {
    await guardarFn(fila.clave, {
      cuenta_debe: debe ? Number(debe) : null,
      cuenta_haber_ingresos: ingresos ? Number(ingresos) : null,
      cuenta_haber_iva: iva ? Number(iva) : null,
      cuenta_haber_cobranza: fila.cuenta_haber_cobranza || null,
    });
  };

  return (
    <tr>
      <td colSpan="5">
        <div className="form-barra" style={{ margin: 0 }}>
          <SelectorCuenta
            etiqueta={invertido ? "Debe (aquí va el ingreso)" : "Debe"}
            valor={debe}
            setValor={setDebe}
          />
          <SelectorCuenta
            etiqueta={
              invertido ? "Haber (aquí va documentos a cobrar)" : "Haber (ingresos)"
            }
            valor={ingresos}
            setValor={setIngresos}
          />
          <SelectorCuenta etiqueta="IVA" valor={iva} setValor={setIva} />
          <label className="campo">
            <span>&nbsp;</span>
            <div style={{ display: "flex", gap: "0.4rem" }}>
              <button className="btn btn-sm" onClick={cambiar} disabled={guardando}>
                Guardar
              </button>
              <button className="btn btn-sm fantasma" onClick={cancel}>
                Cancelar
              </button>
            </div>
          </label>
        </div>
        {invertido && (
          <p className="nota">
            Ojo: esta fila tiene el asiento al revés. Si las pondrás en el orden
            de una venta, la nota va a quedar mal.
          </p>
        )}
      </td>
    </tr>
  );
}

/** Un buscador de cuentas con el mismo comportamiento del resto del sistema. */
function SelectorCuenta({ etiqueta, valor, setValor }) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState([]);

  useEffect(() => {
    if (!texto.trim()) {
      setResultados([]);
      return undefined;
    }
    const t = setTimeout(async () => {
      try {
        setResultados(await buscarCuentas(texto));
      } catch {
        setResultados([]);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [texto]);

  return (
    <label className="campo" style={{ flex: "1 1 220px" }}>
      <span>{etiqueta}</span>
      {valor ? (
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <b className="mono">{valor}</b>
          <button
            type="button"
            className="btn btn-sm fantasma"
            onClick={() => setValor("")}
          >
            Cambiar
          </button>
        </div>
      ) : (
        <div className="as-buscador">
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Buscar cuenta…"
          />
          {resultados.length > 0 && (
            <ul className="as-resultados">
              {resultados.map((c) => (
                <li key={c.id_cuenta}>
                  <button
                    type="button"
                    onClick={() => {
                      setValor(c.id_cuenta);
                      setTexto("");
                      setResultados([]);
                    }}
                  >
                    <b>{c.codigo}</b> {c.nombre}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </label>
  );
}