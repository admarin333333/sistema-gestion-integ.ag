import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { usePeriodoEnFechas } from "../components/PeriodoActual.jsx";
import {
  anularAsiento,
  buscarCuentas,
  crearAsiento,
  guardarAsiento,
  listarAsientos,
  listarCodigos,
  obtenerAsiento,
} from "../api/asientos.js";

const HOY = new Date().toISOString().slice(0, 10);

const ETIQUETA_ESTADO = {
  BORRADOR: "Borrador",
  CONTABILIZADO: "Contabilizado",
  ANULADO: "Anulado",
};

/**
 * Los importes van con coma decimal y SIN punto de miles, como en el resto de
 * la pantalla.
 *
 * OJO: `toFixed(2)` pone PUNTO decimal (2268000.00), que es lo contrario de lo
 * que dice este comentario y lo que el contador no lee bien. Por eso se cambia
 * el punto por coma a mano en vez de usar `toLocaleString`, que además
 * agregaría el separador de miles que acá no se quiere.
 */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toFixed(2).replace(".", ",");
}

/* Una línea del asiento mientras se está editando. `cuenta` ya viene del
 * buscador con código y nombre, para no volver a consultarlo al pintar. */
const LINEA_VACIA = { id_cuenta: 0, codigo: "", nombre_cuenta: "", debe: "", haber: "" };

/**
 * Los MÓDULOS: de qué parte del sistema salió el asiento. Es lo que el contador
 * tiene en la cabeza ("mostrame los recibos"), más simple que el código.
 *
 * Cada módulo trae varios códigos: Facturas son FV (ventas) + NC (notas de
 * crédito) + ND (notas de débito), y todas salen de una factura. Recibos es
 * solo RC. Compras es solo FP. Manuales son los que se cargan a mano, sin
 * comprobante.
 *
 * Compras va aparte de Facturas a propósito: las dos tienen comprobantes de
 * tipo "factura" y nombres parecidos (FV la venta, FP la compra), y el contador
 * tiene que poder mirar una sin ver la otra. Si se mezclaran, el filtro
 * "Facturas" traería también los gastos.
 *
 * Sale de `asiento_origen.origen`, no del código: así el filtro no se rompe si
 * mañana el estudio le agrega un código nuevo a un módulo.
 */
const MODULOS = [
  { origen: "FACTURA", nombre: "Facturas (ventas, notas de crédito y débito)" },
  { origen: "RECIBO", nombre: "Recibos (cobranzas)" },
  { origen: "COMPRA", nombre: "Compras (facturas de proveedor)" },
  { origen: "MANUAL", nombre: "Asientos cargados a mano" },
];

/**
 * Los ASIENTOS ESPECIALES: los tres que el contador arma a mano una vez por
 * mes o una vez por cierre, y que siempre tienen la misma forma.
 *
 * No son automáticos como el de una factura: el sistema no sabe qué cuentas van
 * ni qué importe, así que no se puede armar solo. Lo que hace este selector es
 * **darle un nombre y una guía**, para que el contador no tenga que acordarse
 * de escribir el concepto y lo encuentre después buscando por nombre.
 *
 * El resto —elegir las cuentas, cargar los importes, que el Debe cierre con el
 * Haber— es exactamente el mismo editor de siempre. Por eso NO hay una pantalla
 * aparte: sería el mismo formulario tres veces.
 */
const ESPECIALES = [
  {
    id: "manual",
    etiqueta: "Asiento manual común",
    prefijo: "",
    ayuda: "El de siempre: lo armás a mano y le ponés el concepto que quieras.",
  },
  {
    id: "impuesto",
    etiqueta: "Impuesto nacional y provincial",
    prefijo: "Impuesto nacional y provincial",
    ayuda:
      "Retenciones y percepciones de impuestos. Cargá la cuenta del impuesto " +
      "en el Debe y la de quien lo paga en el Haber.",
  },
  {
    id: "ajuste_mensual",
    etiqueta: "Ajuste mensual",
    prefijo: "Ajuste mensual",
    ayuda:
      "Los ajustes de fin de mes: depreciaciones, consumos que se acumularon, " +
      "provisiones. Una vez por mes.",
  },
  {
    id: "ajuste_balance",
    etiqueta: "Ajuste de balance",
    prefijo: "Ajuste de balance",
    ayuda:
      "Los ajustes del cierre del ejercicio, los que después van al balance: " +
      "activos y pasivos a su valor real, resultados de ejercicios anteriores.",
  },
];

/**
 * Asientos contables.
 *
 * Tres cosas que hay que tener en cuenta al tocar esto:
 *
 * 1. **Acá no se cuenta nada.** El backend agrupa por día y trae los totales ya
 *    sumados (SQL). La pantalla solo los pinta: si el navegador sumara, dos
 *    pantallas darían dos números distintos y los libros no cerrarían con la
 *    pantalla.
 *
 * 2. **Guardar es un solo paso.** El PUT reemplaza las líneas y contabiliza en
 *    el mismo pedido. No hay un "Guardar" y después un "Contabilizar" que el
 *    contador se pueda olvidar: un asiento en borrador no aparece en los saldos.
 *
 * 3. **Anulado es terminal.** Un asiento anulado no se modifica ni se borra.
 */
export default function Asientos() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  // ---- filtros ----------------------------------------------------------
  // Nacen con el PERÍODO DE TRABAJO: el contador elige arriba en qué mes está y
  // la pantalla se abre en ese mes, no en el de hoy. Si arrancara en "hoy" y el
  // contador está retomando septiembre, vería una pantalla vacía sin saber por
  // qué.
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [codigo, setCodigo] = useState("");
  const [modulo, setModulo] = useState("");
  const [estado, setEstado] = useState("");
  const [codigos, setCodigos] = useState([]);

  // ---- datos ------------------------------------------------------------
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  // ---- edición ----------------------------------------------------------
  const [editando, setEditando] = useState(null); // el asiento abierto
  const [lineas, setLineas] = useState([]);
  const [nuevo, setNuevo] = useState(false);

  useEffect(() => {
    listarCodigos().then(setCodigos).catch(() => setCodigos([]));
  }, []);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setDatos(await listarAsientos({ codigo, origen: modulo, estado, desde, hasta }));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codigo, modulo, desde, hasta, estado]);

  // Las fechas van al período de trabajo que se eligió arriba en la barra, y se
  // vuelven a poner cada vez que el contador cambia de período. Los datos se
  // recargan solos por el `useEffect` de arriba, que ya depende de `desde` y
  // `hasta`.
  usePeriodoEnFechas(setDesde, setHasta);

  // ---- acciones sobre un asiento ---------------------------------------

  const abrir = async (id) => {
    setError("");
    setMensaje("");
    setNuevo(false);
    try {
      const a = await obtenerAsiento(id);
      setEditando(a);
      setLineas(
        a.detalle.map((d) => ({
          id_detalle: d.id_detalle,
          id_cuenta: d.id_cuenta,
          codigo: d.codigo,
          nombre_cuenta: d.nombre_cuenta,
          debe: numero(d.debe),
          haber: numero(d.haber),
        })),
      );
    } catch (e) {
      setError(e.message);
    }
  };

  const cerrar = () => {
    setEditando(null);
    setLineas([]);
    setMensaje("");
  };

  /** Suma de lo que está en pantalla. Solo para mirar; el backend es el que
   *  decide si el asiento puede contabilizarse. */
  const { sumaDebe, sumaHaber, diferencia } = useMemo(() => {
    const d = lineas.reduce((a, l) => a + (Number(l.debe) || 0), 0);
    const h = lineas.reduce((a, l) => a + (Number(l.haber) || 0), 0);
    return { sumaDebe: d, sumaHaber: h, diferencia: d - h };
  }, [lineas]);

  /**
   * ¿Se puede guardar? Solo si el Debe cierra con el Haber **y** hay algo
   * cargado.
   *
   * El "y hay algo" parece obvio pero no lo es: con las líneas vacías, 0 − 0 da
   * cero y la pantalla decía "Cierra: Debe = Haber", cuando en realidad lo que
   * se había escrito era nada. El backend lo rechaza igual ("El asiento no tiene
   * líneas"), pero mejor que la pantalla no diga que cierra algo que no cerró.
   */
  const conImportes = lineas.filter(
    (l) => (Number(l.debe) || 0) !== 0 || (Number(l.haber) || 0) !== 0
  );
  const conCuenta = conImportes.filter((l) => l.id_cuenta);
  const hayImportes = conCuenta.length > 0;
  const puedeGuardar = diferencia === 0 && hayImportes;

  const guardar = async () => {
    setError("");
    setMensaje("");
    try {
      const cuerpo = {
        detalle: lineas
          .filter((l) => l.id_cuenta)
          .map((l) => ({
            id_cuenta: Number(l.id_cuenta),
            debe: Number(l.debe) || 0,
            haber: Number(l.haber) || 0,
          })),
      };
      const a = await guardarAsiento(editando.id_asiento, cuerpo.detalle);
      setEditando(a);
      setMensaje(`Listo: ${a.numero_completo || "el asiento"} quedó contabilizado.`);
      await cargar();
    } catch (e) {
      // Si no cierra, el backend deja el asiento en borrador con las líneas
      // que se acababan de mandar: se corrige acá y se vuelve a guardar.
      setError(e.message);
      const a = await obtenerAsiento(editando.id_asiento).catch(() => null);
      if (a) setEditando(a);
    }
  };

  const anular = async (a) => {
    const ok = window.confirm(
      `¿Anular el asiento ${a.numero_completo || a.id_asiento}?\n\n` +
        "Anular es TERMINAL: no se puede modificar ni borrar después. " +
        "La factura o el recibo que lo originó no se tocan."
    );
    if (!ok) return;
    setError("");
    setMensaje("");
    try {
      await anularAsiento(a.id_asiento);
      if (editando?.id_asiento === a.id_asiento) cerrar();
      await cargar();
      setMensaje(`Listo: ${a.numero_completo || "el asiento"} quedó anulado.`);
    } catch (e) {
      setError(e.message);
    }
  };

  // ---- alta manual ------------------------------------------------------

  const [alta, setAlta] = useState({
    fecha: HOY,
    concepto: "",
    codigo_comprobante: "AB",
    tipo: "manual",
  });

  const especial = ESPECIALES.find((e) => e.id === alta.tipo) || ESPECIALES[0];

  // Al elegir un tipo especial se arma el concepto solo ("Ajuste mensual de ").
  // El contador puede cambiarlo: el prefijo es una ayuda, no una regla. Si ya
  // estaba escribiendo algo, no se lo pisa.
  const elegirTipo = (tipo) => {
    const nuevo = ESPECIALES.find((e) => e.id === tipo) || ESPECIALES[0];
    const concepto = alta.concepto.trim();
    setAlta({
      ...alta,
      tipo,
      concepto: nuevo.prefijo && !concepto ? `${nuevo.prefijo} de ` : concepto,
    });
  };

  const crearManual = async (e) => {
    e.preventDefault();
    setError("");
    setMensaje("");
    try {
      const a = await crearAsiento({
        fecha: alta.fecha,
        concepto: alta.concepto.trim(),
        codigo_comprobante: alta.codigo_comprobante,
      });
      setNuevo(false);
      setAlta({ fecha: HOY, concepto: "", codigo_comprobante: "AB", tipo: "manual" });
      setMensaje(
        `Se creó ${a.numero_completo}. Elegí las cuentas y cargá los importes: ` +
          "se guarda recién cuando el Debe cierre con el Haber."
      );
      await cargar();
      await abrir(a.id_asiento);
    } catch (err) {
      setError(err.message);
    }
  };

  // ---- líneas -----------------------------------------------------------

  const agregarLinea = () => setLineas((v) => [...v, { ...LINEA_VACIA }]);
  const sacarLinea = (i) => setLineas((v) => v.filter((_, n) => n !== i));
  const cambiarLinea = (i, campo, valor) =>
    setLineas((v) => v.map((l, n) => (n === i ? { ...l, [campo]: valor } : l)));

  // =================================================== una línea con buscador
  const FilaLinea = ({ linea, indice, puedeEditar }) => {
    const [texto, setTexto] = useState("");
    const [resultados, setResultados] = useState([]);
    const [buscando, setBuscando] = useState(false);

    useEffect(() => {
      if (!texto.trim()) {
        setResultados([]);
        return undefined;
      }
      // Se espera medio segundo para no pegarle una consulta por tecla.
      const t = setTimeout(async () => {
        setBuscando(true);
        try {
          setResultados(await buscarCuentas(texto));
        } catch {
          setResultados([]);
        } finally {
          setBuscando(false);
        }
      }, 350);
      return () => clearTimeout(t);
    }, [texto]);

    return (
      <tr>
        <td>
          {linea.id_cuenta ? (
            <span className="as-cuenta">
              <b>{linea.codigo}</b> {linea.nombre_cuenta}
            </span>
          ) : (
            <div className="as-buscador">
              <input
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                placeholder="Buscá por código o nombre…"
                disabled={!puedeEditar}
                autoFocus={indice === lineas.length - 1}
              />
              {buscando && <small className="nota">buscando…</small>}
              {resultados.length > 0 && (
                <ul className="as-resultados">
                  {resultados.map((c) => (
                    <li key={c.id_cuenta}>
                      <button
                        type="button"
                        onClick={() => {
                          cambiarLinea(indice, "id_cuenta", c.id_cuenta);
                          cambiarLinea(indice, "codigo", c.codigo);
                          cambiarLinea(indice, "nombre_cuenta", c.nombre);
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
        </td>
        <td className="as-dinero">
          <input
            type="number"
            step="0.01"
            min="0"
            value={puedeEditar ? linea.debe : linea.debe}
            onChange={(e) => cambiarLinea(indice, "debe", e.target.value)}
            disabled={!puedeEditar}
          />
        </td>
        <td className="as-dinero">
          <input
            type="number"
            step="0.01"
            min="0"
            value={linea.haber}
            onChange={(e) => cambiarLinea(indice, "haber", e.target.value)}
            disabled={!puedeEditar}
          />
        </td>
        <td>
          {puedeEditar && (
            <button
              className="btn btn-sm peligro"
              onClick={() => sacarLinea(indice)}
              title="Sacar la línea"
            >
              ×
            </button>
          )}
        </td>
      </tr>
    );
  };

  // =============================================================== pantalla
  return (
    <section>
      <span className="kicker">Contabilidad</span>
      <h1>Asientos contables</h1>
      <p className="lead">
        Elegí el código y la fecha para ver los asientos de ese día. Con el
        botón <b>Modificar</b> cambiás las cuentas y los importes; el Debe
        siempre tiene que cerrar con el Haber.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="ok">{mensaje}</p>}

      {/* --------------------------------------------------------- filtros */}
      <div className="form-barra">
        {/* El MÓDULO va primero porque es lo que el contador tiene en la cabeza:
            "mostrame los recibos". El código (RC, FV…) es el detalle de una
            familia de asientos; el módulo agrupa varias. */}
        <label className="campo">
          <span>Módulo</span>
          <select value={modulo} onChange={(e) => setModulo(e.target.value)}>
            <option value="">Todos</option>
            {MODULOS.map((m) => (
              <option key={m.origen} value={m.origen}>
                {m.nombre}
              </option>
            ))}
          </select>
        </label>

        <label className="campo">
          <span>Código</span>
          <select value={codigo} onChange={(e) => setCodigo(e.target.value)}>
            <option value="">Todos</option>
            {codigos.map((c) => (
              <option key={c.codigo} value={c.codigo}>
                {c.codigo} — {c.nombre}
              </option>
            ))}
          </select>
        </label>

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>

        <label className="campo">
          <span>Estado</span>
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">Contabilizados y anulados</option>
            <option value="CONTABILIZADO">Solo contabilizados</option>
            <option value="ANULADO">Solo anulados</option>
            <option value="BORRADOR">Solo borradores</option>
          </select>
        </label>

        <label className="campo">
          <span>&nbsp;</span>
          <button className="btn fantasma" onClick={cargar} disabled={cargando}>
            Actualizar
          </button>
        </label>
      </div>

      {/* ------------------------------------------------------- nuevo asiento */}
      {esAdmin && (
        <div className="form-acciones">
          <button className="btn" onClick={() => setNuevo((v) => !v)}>
            {nuevo ? "Cancelar" : "+ Nuevo asiento"}
          </button>
        </div>
      )}

      {nuevo && esAdmin && (
        <form className="form" onSubmit={crearManual}>
          <fieldset className="fieldset">
            <legend>Asiento manual</legend>

            {/* El tipo va PRIMERO porque es lo primero que decide el contador
                para un asiento especial: si es un ajuste mensual, el código y
                la fecha son lo de siempre. */}
            <label className="campo">
              <span>Tipo de asiento</span>
              <select value={alta.tipo} onChange={(e) => elegirTipo(e.target.value)}>
                {ESPECIALES.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.etiqueta}
                  </option>
                ))}
              </select>
            </label>

            {especial.ayuda && <p className="nota">{especial.ayuda}</p>}

            <div className="form-grid">
              <label className="campo">
                <span>Fecha *</span>
                <input
                  type="date"
                  value={alta.fecha}
                  onChange={(e) => setAlta({ ...alta, fecha: e.target.value })}
                  required
                />
              </label>
              <label className="campo">
                <span>Código *</span>
                <select
                  value={alta.codigo_comprobante}
                  onChange={(e) =>
                    setAlta({ ...alta, codigo_comprobante: e.target.value })
                  }
                >
                  {codigos.map((c) => (
                    <option key={c.codigo} value={c.codigo}>
                      {c.codigo} — {c.nombre}
                    </option>
                  ))}
                </select>
              </label>
              <label className="campo">
                <span>Concepto *</span>
                <input
                  value={alta.concepto}
                  onChange={(e) => setAlta({ ...alta, concepto: e.target.value })}
                  placeholder="Alquiler de agosto"
                  maxLength={200}
                  required
                />
              </label>
            </div>
            <p className="nota">
              Se crea con el número que le toca al código y queda en borrador.
              Después le cargás las líneas. <b>No se guarda hasta que el Debe
              cierre con el Haber</b>: el botón "Guardar" aparece apagado si no
              emparejan, y avisa cuánto falta.
            </p>
            <div className="form-acciones">
              <button className="btn" type="submit">Crear</button>
            </div>
          </fieldset>
        </form>
      )}

      {/* ----------------------------------------------------------- listado */}
      {cargando && <p className="nota">Cargando…</p>}

      {/* El aviso que faltaba: cuando no hay nada EN EL FILTRO pero sí hay
          cosas cargadas. Sin esto la pantalla dice "no hay asientos" y el
          contador piensa que no se asentó nada, cuando en realidad está
          mirando un día donde no se asentó nada. */}
      {!cargando && datos && datos.cantidad === 0 && datos.total_cargados > 0 && (
        <div className="aviso-faltan">
          <p>
            No hay asientos el <b>{desde === hasta ? desde : `${desde} y ${hasta}`}</b>
            {codigo ? ` con el código ${codigo}` : ""}, pero hay{" "}
            <b>{datos.total_cargados}</b> asiento
            {datos.total_cargados === 1 ? "" : "s"} cargado
            {datos.total_cargados === 1 ? "" : "s"} en {datos.dias_con_asientos}{" "}
            día{datos.dias_con_asientos === 1 ? "" : "s"}.
          </p>
          <p className="nota">
            Están entre el {datos.primera_fecha} y el {datos.ultima_fecha}.{" "}
            {datos.dias_con_asientos <= 10 && datos.dias_con_asientos > 0 && (
              <>
                Probá buscando por código, o mirá todos los días:{" "}
              </>
            )}
          </p>
          <div className="form-acciones">
            <button
              className="btn fantasma"
              onClick={() => {
                setDesde(datos.primera_fecha);
                setHasta(datos.ultima_fecha);
                setCodigo("");
                setEstado("");
              }}
            >
              Ver todo lo que hay cargado
            </button>
          </div>
        </div>
      )}

      {!cargando && datos && datos.cantidad === 0 && datos.total_cargados === 0 && (
        <p className="nota">
          {codigo
            ? `Todavía no hay asientos con el código ${codigo}.`
            : `Todavía no hay ningún asiento cargado. Cargá una factura y se arma solo.`}
        </p>
      )}

      {!cargando &&
        datos &&
        datos.dias.map((dia) => (
          <div key={dia.fecha} className="as-dia">
            <div className="as-dia-cab">
              <h2>
                {new Date(`${dia.fecha}T00:00:00`).toLocaleDateString("es-AR", {
                  weekday: "long",
                  day: "2-digit",
                  month: "long",
                  year: "numeric",
                })}
              </h2>
              <span className="nota">
                {dia.cantidad} asiento{dia.cantidad === 1 ? "" : "s"} · Debe{" "}
                {numero(dia.total_debe)} · Haber {numero(dia.total_haber)}
              </span>
            </div>

            {dia.asientos.map((a) => (
              <article key={a.id_asiento} className={`as-card ${a.estado.toLowerCase()}`}>
                <header>
                  <span className="as-num">{a.numero_completo || "Sin código"}</span>
                  <span className="as-concepto">{a.concepto}</span>
                  <span className={`as-estado ${a.estado.toLowerCase()}`}>
                    {ETIQUETA_ESTADO[a.estado] || a.estado}
                  </span>
                </header>

                <table className="tabla as-tabla">
                  <thead>
                    <tr>
                      <th>Cuenta</th>
                      <th className="as-dinero">Debe</th>
                      <th className="as-dinero">Haber</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {a.detalle.map((d) => (
                      <tr key={d.id_detalle}>
                        <td>
                          <b>{d.codigo}</b> {d.nombre_cuenta}
                          {d.tipo_auxiliar && (
                            <small className="nota"> · {d.tipo_auxiliar}</small>
                          )}
                        </td>
                        <td className="as-dinero">{numero(d.debe)}</td>
                        <td className="as-dinero">{numero(d.haber)}</td>
                        <td />
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <th>Totales</th>
                      <th className="as-dinero">{numero(a.total_debe)}</th>
                      <th className="as-dinero">{numero(a.total_haber)}</th>
                      <th />
                    </tr>
                  </tfoot>
                </table>

                <div className="form-acciones">
                  {editando?.id_asiento === a.id_asiento ? (
                    <button className="btn fantasma" onClick={cerrar}>
                      Cerrar
                    </button>
                  ) : (
                    esAdmin &&
                    a.estado !== "ANULADO" && (
                      <button className="btn fantasma" onClick={() => abrir(a.id_asiento)}>
                        Modificar
                      </button>
                    )
                  )}
                  {esAdmin && a.estado !== "ANULADO" && (
                    <button className="btn fantasma" onClick={() => anular(a)}>
                      Anular
                    </button>
                  )}
                  {a.estado === "ANULADO" && (
                    <small className="nota">Anulado: ya no se modifica.</small>
                  )}
                </div>
              </article>
            ))}
          </div>
        ))}

      {/* ------------------------------------------------------- editor */}
      {editando && (
        <div className="as-editor">
          <h2>
            Modificando {editando.numero_completo || `el asiento ${editando.id_asiento}`}
          </h2>
          <p className="nota">{editando.concepto}</p>

          <table className="tabla as-tabla">
            <thead>
              <tr>
                <th>Cuenta</th>
                <th className="as-dinero">Debe</th>
                <th className="as-dinero">Haber</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => (
                <FilaLinea
                  key={l.id_detalle ?? `nueva-${i}`}
                  linea={l}
                  indice={i}
                  puedeEditar
                />
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th>Totales</th>
                <th className="as-dinero">{numero(sumaDebe)}</th>
                <th className="as-dinero">{numero(sumaHaber)}</th>
                <th />
              </tr>
            </tfoot>
          </table>

          {conImportes.length && conCuenta.length !== conImportes.length ? (
            /* Escribir "6.1.10" en el buscador NO elige la cuenta: hay que
               apretar la sugerencia. Si no se avisa, el contador cree que ya la
               eligió y no entiende por qué no se guarda. */
            <p className="error">
              Te falta elegir la cuenta en{" "}
              {conImportes.length - conCuenta.length} línea
              {conImportes.length - conCuenta.length === 1 ? "" : "s"}: abajo del
              nombre de la línea tiene que quedar el código, no solo lo que
              escribiste.
            </p>
          ) : !hayImportes ? (
            <p className="nota">
              Todavía no cargaste importes. Elegí una cuenta en cada línea y
              poné el importe: <b>no se guarda un asiento vacío</b>.
            </p>
          ) : diferencia !== 0 ? (
            <p className="error">
              No cierra: el Debe y el Haber difieren en{" "}
              {numero(Math.abs(diferencia))}. El backend no lo va a contabilizar
              hasta que emparejen.
            </p>
          ) : (
            <p className="ok">Cierra: Debe = Haber.</p>
          )}

          <div className="form-acciones">
            <button className="btn fantasma" onClick={agregarLinea}>
              + Agregar línea
            </button>
            <button
              className="btn"
              onClick={guardar}
              disabled={!puedeGuardar}
              title={
                puedeGuardar
                  ? "Guarda el asiento y lo contabiliza"
                  : "No se puede guardar: el Debe tiene que cerrar con el Haber"
              }
            >
              Guardar
            </button>
            <button className="btn fantasma" onClick={cerrar}>Cancelar</button>
          </div>
        </div>
      )}
    </section>
  );
}