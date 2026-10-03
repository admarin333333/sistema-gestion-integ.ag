import { useEffect, useMemo, useState } from "react";
import {
  activarConcepto,
  crearConcepto,
  desactivarConcepto,
  editarConcepto,
  listarConceptos,
  listarMeses,
  restaurarMes,
} from "../api/vencimientos.js";
import GrillaVencimientos from "./GrillaVencimientos.jsx";
import { MESES } from "./vencimientosComun.js";
import { fechaHora } from "../formato.js";

const hoy = new Date();

/** "última actualización: 02/10/2026 01:19" */
const cuando = (iso) => (iso ? fechaHora(iso) : "—");

/**
 * Vencimientos, dentro de Configuración.
 *
 * Es un árbol año -> mes -> grilla. Abajo queda el catálogo de conceptos,
 * que se edita acá mismo (agregar, renombrar, apagar).
 *
 * De dónde salen los datos:
 * - la lista de meses viene de `/meses`, que tiene un registro por mes
 *   guardado con la fecha del último guardado (aunque el mes esté vacío);
 * - la grilla de cada mes se pide recién cuando clickeás el mes.
 */
export default function VencimientosConfig() {
  const [meses, setMeses] = useState([]);
  const [conceptos, setConceptos] = useState([]);
  const [anioAbierto, setAnioAbierto] = useState(hoy.getFullYear());
  const [mesElegido, setMesElegido] = useState("");  // el mes del menú
  const [aniosExtra, setAniosExtra] = useState([]);
  const [anioNuevo, setAnioNuevo] = useState("");
  const [nuevo, setNuevo] = useState("");
  const [editando, setEditando] = useState(null);   // id del concepto en edición
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [guardandoCatalogo, setGuardandoCatalogo] = useState(false);

  // Las columnas de la grilla: los conceptos que están encendidos. Se recalcula
  // cuando el catálogo cambia, así agregar un concepto agrega la columna al
  // tiro (no hay que recargar la página).
  const conceptosActivos = conceptos.filter((c) => c.activo);

  const cargar = async () => {
    setError("");
    try {
      const [ms, cs] = await Promise.all([listarMeses(), listarConceptos()]);
      setMeses(ms);
      setConceptos(cs);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  // Si todavía no se eligió mes, se ofrece el primero del año abierto que tenga
  // vencimientos cargados. Así la pantalla no arranca siempre en blanco.
  useEffect(() => {
    if (mesElegido) return;
    const delAnio = meses.filter((m) => m.anio === anioAbierto);
    if (delAnio.length) setMesElegido(String(delAnio[0].mes));
  }, [meses, anioAbierto, mesElegido]);

  // Qué años se ven. Siempre aparecen el año en curso y el que viene, para
  // poder cargar los vencimientos del año próximo sin tener que esperar a
  // que January esté cerca. Los años que ya tienen algo cargado también.
  // Con `aniosExtra` el usuario puede agregar el que quiera (más atrás o más
  // adelante).
  const anios = useMemo(() => {
    const set = new Set([
      hoy.getFullYear(),
      hoy.getFullYear() + 1,
      ...meses.map((m) => m.anio),
      ...aniosExtra,
    ]);
    return [...set].sort((a, b) => b - a);
  }, [meses, aniosExtra]);

  // Los 12 meses de cada año, con lo que haya guardado en cada uno.
  // Los meses sin nada guardado también se listan: hay que verlos para poder
  // cargarlos.
  const porAnio = useMemo(() => {
    const mapa = new Map();   // anio -> { "1": mes, ..., "12": mes }
    for (const m of meses) {
      if (!mapa.has(m.anio)) {
        mapa.set(m.anio, Object.fromEntries(MESES.map((_, i) => [i + 1, null])));
      }
      mapa.get(m.anio)[m.mes] = m;
    }
    return anios.map((anio) => {
      const guardados = mapa.get(anio) || {};
      const lista = MESES.map((nombre, i) => ({
        anio,
        mes: i + 1,
        nombre,
        datos: guardados[i + 1] || null,
      }));
      const conDatos = lista.filter((x) => x.datos);
      const total = conDatos.reduce((s, x) => s + x.datos.cantidad, 0);
      const ultimo = conDatos.reduce(
        (s, x) => (x.datos.ultimo_cambio > s ? x.datos.ultimo_cambio : s),
        ""
      );
      return { anio, lista, total, ultimo, cargados: conDatos.length };
    });
  }, [anios, meses]);

  /* ------------------------------------------------------- catálogo */

  const agregar = async (e) => {
    e.preventDefault();
    const nombre = nuevo.trim();
    if (!nombre) return;
    setGuardandoCatalogo(true);
    setError("");
    setMensaje("");
    try {
      await crearConcepto(nombre);
      setNuevo("");
      await cargar();
      setMensaje(`Listo: se agregó el concepto "${nombre}". Ya aparece en la grilla.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardandoCatalogo(false);
    }
  };

  const renombrar = async (id, nombre) => {
    const limpio = nombre.trim();
    if (!limpio) {
      setEditando(null);
      return;
    }
    setError("");
    setMensaje("");
    try {
      await editarConcepto(id, limpio);
      setEditando(null);
      await cargar();
      setMensaje(`Listo: el concepto ahora se llama "${limpio}".`);
    } catch (e) {
      setError(e.message);
    }
  };

  const apagar = async (c) => {
    const confirmacion = window.confirm(
      `¿Apagar el concepto "${c.nombre}"?\n\n` +
        "Va a desaparecer de las grillas para cargar los meses nuevos.\n" +
        "Los vencimientos que ya están guardados NO se borran: siguen ahí y " +
        "muestran el nombre viejo.\n\n" +
        "Para volver a usarlo, activalo de nuevo."
    );
    if (!confirmacion) return;
    setError("");
    setMensaje("");
    try {
      await desactivarConcepto(c.id);
      await cargar();
      setMensaje(`Listo: "${c.nombre}" quedó apagado.`);
    } catch (e) {
      setError(e.message);
    }
  };

  const encender = async (c) => {
    setError("");
    setMensaje("");
    try {
      await activarConcepto(c.id);
      await cargar();
      setMensaje(`Listo: "${c.nombre}" volvió a estar disponible para cargar.`);
    } catch (e) {
      setError(e.message);
    }
  };

  const restaurar = async (m) => {
    setError("");
    setMensaje("");
    try {
      const r = await restaurarMes(m.anio, m.mes);
      await cargar();
      setMensaje(
        `Listo: se recuperaron ${r.restaurados} vencimientos de ` +
          `${MESES[m.mes - 1]} ${m.anio}.`
      );
    } catch (e) {
      setError(e.message);
    }
  };

  /* --------------------------------------------------------- árbol */

  return (
    <div className="panel">
      <h3>Vencimientos impositivos</h3>
      <p className="nota">
        Elegí el año, después el mes. En la grilla cargás la fecha de
        vencimiento de cada concepto para cada último dígito del CUIT: los
        clientes que terminan en el mismo dígito vencen el mismo día.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && (
        <p className="aviso-guardado" role="status">
          {mensaje}
        </p>
      )}

      {/* --- cascada: elegís el año, después el mes de un menú --- */}
      <div className="arbol-vencimientos">
        {porAnio.map(({ anio, lista, total, ultimo, cargados }) => {
          const abiertoAqui = anio === anioAbierto;
          // El menú va siempre en orden de calendario (enero a diciembre),
          // con la cantidad al lado de los meses que ya tienen algo. Si se
          // ordenaran por "cargados primero", cuando están todos cargados el
          // menú queda en un solo bloque y se pierde el orden del año.
          const conDatos = lista.filter((x) => x.datos);
          const elegido = abiertoAqui && mesElegido
            ? lista.find((x) => x.mes === Number(mesElegido))
            : null;

          return (
            <div key={anio} className="arbol-anio">
              <button
                type="button"
                className={`arbol-fila ${abiertoAqui ? "abierta" : ""}`}
                onClick={() => {
                  setAnioAbierto(abiertoAqui ? null : anio);
                  if (!abiertoAqui) {
                    // Al abrir un año se ofrece el último mes que tenga datos,
                    // así no arranca siempre en blanco.
                    setMesElegido(conDatos.length ? String(conDatos[0].mes) : "");
                  }
                }}
              >
                <span className="arbol-flecha">{abiertoAqui ? "▾" : "▸"}</span>
                <b>{anio}</b>
                <span className="nota">
                  {cargados === 0
                    ? "sin meses cargados"
                    : `${cargados} de 12 meses · ${total} vencimiento${
                        total === 1 ? "" : "s"
                      }`}
                </span>
                {ultimo && (
                  <span className="nota fecha-actualizacion">
                    última actualización: {cuando(ultimo)}
                  </span>
                )}
              </button>

              {abiertoAqui && (
                <div className="arbol-mes">
                  <label className="campo">
                    <span>Mes de {anio}</span>
                    <select
                      value={mesElegido}
                      onChange={(e) => setMesElegido(e.target.value)}
                    >
                      <option value="">Elegí el mes…</option>
                      {lista.map(({ mes: m, nombre, datos }) => (
                        <option key={m} value={m}>
                          {nombre}
                          {datos && datos.cantidad > 0
                            ? ` — ${datos.cantidad} ${
                                datos.cantidad === 1
                                  ? "vencimiento"
                                  : "vencimientos"
                              }`
                            : datos
                            ? " — vacío"
                            : ""}
                        </option>
                      ))}
                    </select>
                  </label>

                  {elegido && (
                    <p className="nota fecha-actualizacion" style={{ marginLeft: 0 }}>
                      {elegido.datos
                        ? `Última actualización: ${cuando(
                            elegido.datos.ultimo_cambio
                          )}${
                            elegido.datos.usuario
                              ? ` por ${elegido.datos.usuario}`
                              : ""
                          }`
                        : `${elegido.nombre} ${anio} todavía no tiene vencimientos cargados.`}
                    </p>
                  )}
                </div>
              )}

              {abiertoAqui && elegido && (
                <div className="arbol-grilla">
                  <GrillaVencimientos
                    anio={anio}
                    mes={elegido.mes}
                    conceptos={conceptosActivos}
                    compacto={Boolean(elegido.datos)}
                    alGuardar={cargar}
                  />
                  {elegido.datos?.tiene_respaldo && (
                    <p className="nota">
                      <button
                        type="button"
                        className="btn btn-sm fantasma"
                        onClick={() => restaurar(elegido.datos)}
                      >
                        Recuperar el último guardado
                      </button>{" "}
                      Vuelve a poner cómo estaba este mes la última vez que se
                      guardó.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* --- agregar otro año (más atrás o más adelante) --- */}
      <form
        className="arbol-nuevo-mes"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(anioNuevo);
          if (!n || n < 2000 || n > 2100) return;
          setAniosExtra((v) => (v.includes(n) ? v : [...v, n]));
          setAnioAbierto(n);
          setAnioNuevo("");
        }}
      >
        <label className="campo">
          <span>Ver otro año</span>
          <input
            type="number"
            min="2000"
            max="2100"
            placeholder="Ej: 2028"
            value={anioNuevo}
            onChange={(e) => setAnioNuevo(e.target.value)}
          />
        </label>
        <button className="btn btn-sm" type="submit" disabled={!anioNuevo}>
          Agregar año
        </button>
      </form>

      {/* --- catálogo de conceptos --- */}
      <CatalogoConceptos
        conceptos={conceptos}
        editando={editando}
        setEditando={setEditando}
        onRenombrar={renombrar}
        onApagar={apagar}
        onEncender={encender}
        onAgregar={agregar}
        nuevo={nuevo}
        setNuevo={setNuevo}
        guardando={guardandoCatalogo}
      />
    </div>
  );
}

/** La lista de conceptos: agregar, renombrar y apagar. */
function CatalogoConceptos({
  conceptos,
  editando,
  setEditando,
  onRenombrar,
  onApagar,
  onEncender,
  onAgregar,
  nuevo,
  setNuevo,
  guardando,
}) {
  const activos = conceptos.filter((c) => c.activo);
  const apagados = conceptos.filter((c) => !c.activo);

  return (
    <div className="catalogo-concepts">
      <h4>Catálogo de conceptos</h4>
      <p className="nota">
        Son las columnas de la grilla. Si apagás uno, no aparece para cargar
        meses nuevos, pero los vencimientos que ya guardaste no se tocan.
      </p>

      <form onSubmit={onAgregar} className="form-acciones">
        <label className="campo">
          <span>Nuevo concepto</span>
          <input
            type="text"
            value={nuevo}
            placeholder="Ej: DDJJ F.931"
            onChange={(e) => setNuevo(e.target.value)}
          />
        </label>
        <button className="btn btn-sm" type="submit" disabled={guardando || !nuevo.trim()}>
          {guardando ? "Agregando…" : "Agregar concepto"}
        </button>
      </form>

      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>Concepto</th>
              <th>Clave interna</th>
              <th>Orden</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {[...activos, ...apagados].map((c) => (
              <tr key={c.id} className={c.activo ? "" : "apagado"}>
                <td>
                  {editando === c.id ? (
                    <input
                      type="text"
                      autoFocus
                      defaultValue={c.nombre}
                      onBlur={(e) => onRenombrar(c.id, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") onRenombrar(c.id, e.currentTarget.value);
                        if (e.key === "Escape") setEditando(null);
                      }}
                    />
                  ) : (
                    <>
                      <b>{c.nombre}</b>
                      {!c.activo && (
                        <span className="nota"> · apagado</span>
                      )}
                    </>
                  )}
                </td>
                <td className="mono nota">{c.clave}</td>
                <td className="mono">{c.orden}</td>
                <td className="derecha">
                  {editando !== c.id && (
                    <button
                      type="button"
                      className="btn btn-sm fantasma"
                      onClick={() => setEditando(c.id)}
                    >
                      Renombrar
                    </button>
                  )}{" "}
                  {c.activo ? (
                    <button
                      type="button"
                      className="btn btn-sm fantasma"
                      onClick={() => onApagar(c)}
                    >
                      Apagar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-sm fantasma"
                      onClick={() => onEncender(c)}
                    >
                      Encender
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}