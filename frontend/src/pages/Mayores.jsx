import { useEffect, useMemo, useState } from "react";
import { listarMayor, listarSaldos } from "../api/asientos.js";
import { listarPlanCuentas } from "../api/planCuentas.js";
import { listarEjercicios } from "../api/ejercicios.js";
import { useArbolCuentas } from "../components/useArbolCuentas.js";

const HOY = new Date().toISOString().slice(0, 10);

/**
 * Los importes van con coma decimal y SIN punto de miles, como en el resto de
 * la pantalla: 2268000,00 y no 2.268.000,00.
 *
 * OJO: `toFixed(2)` pone PUNTO decimal (2268000.00), que es lo contrario de lo
 * que hay que mostrar. Por eso se cambia el punto por coma a mano en vez de
 * usar `toLocaleString`, que además agregaría el separador de miles que acá no
 * se quiere. Es el mismo criterio que usa Asientos.jsx.
 */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return Number(valor).toFixed(2).replace(".", ",");
}

/** "2026-09-01" → "01/09/2026". Para las fechas del filtro. */
function fechaCorta(iso) {
  if (!iso) return "";
  const [a, m, d] = String(iso).split("-");
  return d ? `${d}/${m}/${a}` : iso;
}

/**
 * Los MAYORES GENERALES.
 *
 * Un mayor es el libro de UNA cuenta: todos sus movimientos, uno por línea, con
 * el saldo que va acumulando. Sirve para responder "¿de dónde salió esta plata
 * y a dónde fue?".
 *
 * **Dos solapas**, porque son dos preguntas distintas:
 *  - "Cuentas": ¿cuál me interesa mirar? Acá están todas con su saldo. El
 *    saldo lo calcula la base con SQL, no el navegador.
 *  - "Movimientos": todos los movimientos de la cuenta elegida, con desde/hasta.
 *
 * OJO con el signo del saldo: sale de la naturaleza de la cuenta. En una
 * **deudora** (Activo, Costos, Gastos) es Debe − Haber, así que un saldo
 * positivo es lo que la empresa tiene. En una **acreedora** (Pasivo, Patrimonio
 * Neto, Ingresos) es Haber − Debe, y también positivo significa "a favor".
 *
 * **Las cuentas con auxiliar** (Documentos a cobrar, Clientes, bancos) son un
 * caso aparte. El saldo acumulado de la cuenta COMPLETA mezcla clientes: si
 * le debés 100.000 a Ana y 70.000 a Bruno, el acumulado dice 170.000 y ese
 * número no es de nadie. Por eso el backend devuelve un subtotal por auxiliar,
 * que es lo que realmente se mira, y se puede abrir el mayor de UN cliente
 * solo, donde el acumulado sí es el saldo de ese cliente.
 */
export default function Mayores() {
  const [solapa, setSolapa] = useState("cuentas");

  const [mayor, setMayor] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const [texto, setTexto] = useState("");

  const [saldos, setSaldos] = useState([]);
  const [cargandoSaldos, setCargandoSaldos] = useState(false);

  // El árbol del plan de cuentas. Es el MISMO que usa PlanCuentas (hook
  // compartido): si cada pantalla armara el suyo, el contador vería dos
  // maneiras distintas de recorrer las cuentas y no sabría si "Fondo fijo" es la
  // misma en las dos.
  const [plan, setPlan] = useState([]);

  // Por defecto, el ejercicio de hoy: si no, el mayor arranca con todo el
  // histórico y no se entiende nada.
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [ejercicios, setEjercicios] = useState([]);

  // El auxiliar que se está mirando (cliente). "" = la cuenta entera.
  const [auxiliar, setAuxiliar] = useState("");

  useEffect(() => {
    listarPlanCuentas({ todas: true })
      .then(setPlan)
      .catch(() => setPlan([]));
    listarEjercicios()
      .then((r) => {
        const vigentes = r.resumen?.vigente ? [r.resumen.vigente] : r.ejercicios || [];
        setEjercicios(vigentes);
        const vigente = r.resumen?.vigente;
        if (vigente) {
          setDesde(vigente.fecha_inicio);
          setHasta(vigente.fecha_fin);
        } else {
          setDesde(HOY);
          setHasta(HOY);
        }
      })
      .catch(() => {
        setDesde(HOY);
        setHasta(HOY);
      });
  }, []);

  // --- solapa 1: las cuentas con su saldo -----------------------------------
  const cargarSaldos = () => {
    setCargandoSaldos(true);
    listarSaldos({ desde, hasta, con_movimientos: "true" })
      .then(setSaldos)
      .catch(() => setSaldos([]))
      .finally(() => setCargandoSaldos(false));
  };

  useEffect(() => {
    if (solapa === "cuentas") cargarSaldos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solapa, desde, hasta]);

  // El árbol de cuentas. Sale de `plan` y se filtra con `texto` en memoria: es
  // un filtro de_tree, no una consulta nueva. `soloImputables` es false porque
  // acá sí tienen que verse los agrupadores (son el camino para llegar a las
  // cuentas), pero solo se puede ABRIR un mayor de una imputable.
  const arbol = useArbolCuentas(plan, { buscar: texto });

  // El saldo de cada cuenta, por id. Viene de `/saldos` (SQL), no se calcula acá.
  const saldoDe = useMemo(() => {
    const m = new Map();
    saldos.forEach((s) => m.set(s.id_cuenta, s));
    return m;
  }, [saldos]);

  const abrir = async (idCuenta, idAuxiliar = "") => {
    setError("");
    setCargando(true);
    try {
      setMayor(await listarMayor(idCuenta, { desde, hasta, auxiliar_id: idAuxiliar }));
      setAuxiliar(idAuxiliar || "");
      setSolapa("movimientos");
    } catch (e) {
      setError(e.message);
      setMayor(null);
    } finally {
      setCargando(false);
    }
  };

  // Al cambiar el período hay que recargar: si no, la pantalla mentiría mostrando
  // el mayor viejo junto con las fechas nuevas.
  const recargar = () => {
    if (mayor) abrir(mayor.cuenta.id_cuenta, auxiliar);
  };

  // El camino de la cuenta: "1.1 ACTIVO / 1.1.01 Caja y bancos / Banco Nación".
  const nivel = mayor?.cuenta.nivel || 1;
  const sangria = useMemo(() => (nivel - 1) * 1.1, [nivel]);

  const tieneAuxiliar = mayor?.cuenta.tipo_auxiliar === "CLIENTE"
    || mayor?.cuenta.tipo_auxiliar === "PROVEEDOR"
    || mayor?.cuenta.tipo_auxiliar === "BANCO";

  /** Una fila del árbol, con las hijas debajo si está abierta. */
  const filaArbol = (c, nivelVisual) => {
    const abierta = arbol.abierta(c);
    const hijas = arbol.hijasDe.get(c.id_cuenta) || [];
    const tieneHijas = c.tiene_hijas || hijas.length > 0;
    // Solo las IMPUTABLES tienen movimientos propios. Las agrupadoras se
    // muestran para poder llegar a las de abajo, pero sin saldo ni botón.
    const s = c.imputable ? saldoDe.get(c.id_cuenta) : null;

    return (
      <div key={c.id_cuenta}>
        <div
          className={`pc-fila ${c.imputable ? "imputable" : "grupo"} ${
            !c.activa ? "apagada" : ""
          }`}
          style={{ paddingLeft: `${0.6 + nivelVisual * 1.1}rem` }}
        >
          <button
            type="button"
            className="pc-flecha"
            onClick={() => arbol.alternar(c.codigo)}
            disabled={!tieneHijas}
            aria-label={abierta ? "Cerrar" : "Abrir"}
          >
            {tieneHijas ? (abierta ? "▾" : "▸") : "·"}
          </button>

          <span className="pc-codigo mono">{c.codigo}</span>
          <span className="pc-nombre">{c.nombre}</span>

          {c.imputable ? (
            <span
              className={`pc-dh ${
                c.deudora_acreadora === "DEUDORA" ? "deudora" : "acreedora"
              }`}
              title={
                c.deudora_acreadora === "DEUDORA"
                  ? "Deudora: su saldo aumenta en el Debe"
                  : "Acreedora: su saldo aumenta en el Haber"
              }
            >
              {c.deudora_acreadora === "DEUDORA" ? "D" : "A"}
            </span>
          ) : (
            <span className="nota pc-dh">—</span>
          )}

          <span className="mayor-debe">{s ? numero(s.total_debe) : ""}</span>
          <span className="mayor-haber">{s ? numero(s.total_haber) : ""}</span>
          <span className="mayor-saldo">
            {s ? <b>{numero(s.saldo)}</b> : null}
          </span>

          <span className="mayor-accion">
            {c.imputable && (
              <button
                type="button"
                className="btn btn-sm fantasma"
                onClick={() => abrir(c.id_cuenta)}
                title={`Ver los movimientos de ${c.codigo} ${c.nombre}`}
              >
                Ver mayor
              </button>
            )}
          </span>
        </div>

        {abierta && hijas.map((h) => filaArbol(h, nivelVisual + 1))}
      </div>
    );
  };

  return (
    <section>
      <span className="kicker">Contabilidad</span>
      <h1>Mayores generales</h1>
      <p className="lead">
        Elegí una cuenta y mirá todos sus movimientos. El saldo sale con el signo
        de la cuenta: en una deudora es Debe − Haber, en una acreedora es
        Haber − Debe.
      </p>

      {error && <p className="error">{error}</p>}

      {/* ------------------------------------------------------------ solapas */}
      <div className="solapas" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={solapa === "cuentas"}
          className={solapa === "cuentas" ? "solapa activa" : "solapa"}
          onClick={() => setSolapa("cuentas")}
        >
          Cuentas
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={solapa === "movimientos"}
          className={solapa === "movimientos" ? "solapa activa" : "solapa"}
          onClick={() => setSolapa("movimientos")}
          disabled={!mayor}
        >
          Movimientos
          {mayor && (
            <small className="solapa-sub">
              {mayor.cuenta.codigo} {mayor.cuenta.nombre}
            </small>
          )}
        </button>
      </div>

      {/* ------------------------------------------------- filtro de período */}
      <div className="form-barra">
        <label className="campo">
          <span>Desde</span>
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>

        {ejercicios.length > 0 && (
          <label className="campo">
            <span>Ejercicio</span>
            <select
              value=""
              onChange={(e) => {
                const ej = ejercicios.find((x) => String(x.id_ejercicio) === e.target.value);
                if (ej) {
                  setDesde(ej.fecha_inicio);
                  setHasta(ej.fecha_fin);
                }
              }}
            >
              <option value="">Elegí un ejercicio…</option>
              {ejercicios.map((ej) => (
                <option key={ej.id_ejercicio} value={ej.id_ejercicio}>
                  {ej.nombre} ({ej.fecha_inicio} a {ej.fecha_fin})
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="campo">
          <span>&nbsp;</span>
          <button
            className="btn fantasma"
            onClick={solapa === "cuentas" ? cargarSaldos : recargar}
            disabled={solapa === "movimientos" && !mayor}
          >
            Actualizar
          </button>
        </label>
      </div>

      {/* ================================================== SOLAPA: CUENTAS */}
      {solapa === "cuentas" && (
        <>
          <div className="form-barra">
            <label className="campo" style={{ flex: "1 1 22rem" }}>
              <span>Buscar cuenta</span>
              <input
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                placeholder="Buscá por código o nombre (por ejemplo: fondo fijo)…"
              />
            </label>
            {arbol.estaFiltrando && (
              <p className="nota">
                {arbol.cuantas} cuenta{arbol.cuantas === 1 ? "" : "s"} coinciden.
                Se muestran también sus padres para que se vea de dónde sale.
              </p>
            )}
          </div>

          <div className="pc-arbol">
            <div className="pc-fila pc-encabezado">
              <span className="pc-flecha" />
              <span className="pc-codigo">Código</span>
              <span className="pc-nombre">Nombre</span>
              <span className="pc-dh">D/A</span>
              <span className="mayor-debe">Debe</span>
              <span className="mayor-haber">Haber</span>
              <span className="mayor-saldo">Saldo</span>
              <span className="mayor-accion">&nbsp;</span>
            </div>

            {cargandoSaldos && (
              <p className="nota" style={{ padding: "0.7rem" }}>
                Calculando saldos…
              </p>
            )}

            {arbol.raices.map((c) => filaArbol(c, 0))}
          </div>

          <p className="nota">
            Los saldos son del {fechaCorta(desde)} al {fechaCorta(hasta)}, y los
            calcula la base de datos. Las agrupadoras no tienen saldo propio: se
            los suman las cuentas de abajo.
          </p>
        </>
      )}

      {/* =============================================== SOLAPA: MOVIMIENTOS */}
      {solapa === "movimientos" && (
        <>
          {cargando && <p className="nota">Cargando…</p>}

          {!cargando && !mayor && (
            <p className="nota">Elegí una cuenta en la solapa Cuentas.</p>
          )}

          {!cargando && mayor && (
            <article className="as-card">
              <header>
                <span className="as-num" style={{ paddingLeft: `${sangria}rem` }}>
                  {mayor.cuenta.codigo}
                </span>
                <span className="as-concepto">{mayor.cuenta.nombre}</span>
                <span
                  className={`as-estado ${
                    mayor.cuenta.deudora_acreadora === "ACREEDORA" ? "anulado" : "contabilizado"
                  }`}
                >
                  {mayor.cuenta.deudora_acreadora === "ACREEDORA" ? "Acreedora" : "Deudora"}
                </span>
              </header>

              <p className="nota">
                Período {desde} a {hasta}.
                {mayor.auxiliar_nombre && (
                  <>
                    {" "}
                    Filtrado por <b>{mayor.auxiliar_nombre}</b>: el saldo de
                    abajo es solo de ese auxiliar.
                  </>
                )}
              </p>

              {mayor.movimientos === 0 ? (
                <p className="nota">
                  {mayor.auxiliar_nombre
                    ? `Ese auxiliar no tuvo movimientos entre ${desde} y ${hasta}.`
                    : `La cuenta no tiene movimientos entre ${desde} y ${hasta}.`}
                </p>
              ) : (
                <table className="tabla as-tabla">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Comprobante</th>
                      <th>Concepto</th>
                      {tieneAuxiliar && !mayor.auxiliar_id && <th>Auxiliar</th>}
                      <th className="as-dinero">Debe</th>
                      <th className="as-dinero">Haber</th>
                      <th className="as-dinero">Saldo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mayor.lineas.map((l) => (
                      <tr key={l.id_detalle}>
                        <td>{l.fecha}</td>
                        <td>
                          <b>{l.numero_comprobante || "—"}</b>
                        </td>
                        <td>{l.concepto}</td>
                        {tieneAuxiliar && !mayor.auxiliar_id && (
                          <td>{l.auxiliar_nombre || "—"}</td>
                        )}
                        <td className="as-dinero">{l.debe ? numero(l.debe) : ""}</td>
                        <td className="as-dinero">{l.haber ? numero(l.haber) : ""}</td>
                        <td className="as-dinero">
                          <b>{numero(l.saldo)}</b>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <th colSpan={tieneAuxiliar && !mayor.auxiliar_id ? 4 : 3}>
                        Totales
                      </th>
                      <th className="as-dinero">{numero(mayor.total_debe)}</th>
                      <th className="as-dinero">{numero(mayor.total_haber)}</th>
                      <th className="as-dinero">
                        <b>{numero(mayor.saldo_final)}</b>
                      </th>
                    </tr>
                  </tfoot>
                </table>
              )}

              {/* ----------------------------- subtotales por auxiliar ----------
                  El saldo de arriba mezcla clientes. Estos son los números que
                  importan: cuánto debe cada uno. */}
              {tieneAuxiliar && !mayor.auxiliar_id && mayor.auxiliares.length > 0 && (
                <>
                  <h3 className="as-subtitulo">Saldo por auxiliar</h3>
                  <p className="nota">
                    El saldo de la tabla de arriba mezcla a todos los auxiliares.
                    Estos son los que le debe el estudio a cada uno.
                  </p>
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Auxiliar</th>
                        <th className="as-dinero">Debe</th>
                        <th className="as-dinero">Haber</th>
                        <th className="as-dinero">Saldo</th>
                        <th>Movs.</th>
                        <th>&nbsp;</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mayor.auxiliares.map((a) => (
                        <tr key={a.id_auxiliar}>
                          <td>{a.nombre || `Auxiliar ${a.id_auxiliar}`}</td>
                          <td className="as-dinero">{numero(a.debe)}</td>
                          <td className="as-dinero">{numero(a.haber)}</td>
                          <td className="as-dinero">
                            <b>{numero(a.saldo)}</b>
                          </td>
                          <td>{a.movimientos}</td>
                          <td>
                            <button
                              type="button"
                              className="btn fantasma"
                              onClick={() => abrir(mayor.cuenta.id_cuenta, a.id_auxiliar)}
                            >
                              Ver su mayor
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <th>Total</th>
                        <th className="as-dinero">{numero(mayor.total_debe)}</th>
                        <th className="as-dinero">{numero(mayor.total_haber)}</th>
                        <th className="as-dinero">
                          <b>{numero(mayor.saldo_final)}</b>
                        </th>
                        <th colSpan={2}>&nbsp;</th>
                      </tr>
                    </tfoot>
                  </table>
                </>
              )}

              {tieneAuxiliar && !mayor.auxiliar_id && mayor.auxiliares.length > 1 && (
                <div className="form-acciones">
                  <button
                    className="btn fantasma"
                    onClick={() => abrir(mayor.cuenta.id_cuenta, "")}
                  >
                    Ver la cuenta entera (sin filtro de auxiliar)
                  </button>
                </div>
              )}

              {mayor.auxiliar_id && (
                <div className="form-acciones">
                  <button
                    className="btn fantasma"
                    onClick={() => abrir(mayor.cuenta.id_cuenta, "")}
                  >
                    ← Sacar el filtro de {mayor.auxiliar_nombre}
                  </button>
                </div>
              )}

              <p className="nota">
                {mayor.movimientos} movimiento{mayor.movimientos === 1 ? "" : "s"}.
                {!mayor.cierra && (
                  <span className="error">
                    {" "}
                    Ojo: el saldo acumulado no coincide con el total.
                  </span>
                )}
              </p>
            </article>
          )}
        </>
      )}
    </section>
  );
}