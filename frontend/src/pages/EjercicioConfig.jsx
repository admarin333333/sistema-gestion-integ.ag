import { useEffect, useState } from "react";
import {
  abrirEjercicio,
  cerrarEjercicio,
  crearEjercicio,
  editarEjercicio,
  listarEjercicios,
} from "../api/ejercicios.js";

const HOY = new Date().toISOString().slice(0, 10);

const VACIO = { nombre: "", fecha_inicio: HOY, fecha_fin: HOY, cerrado: false };

/** "2026-09-01" → "01/09/2026" */
function fecha(iso) {
  if (!iso) return "";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

/**
 * El ejercicio contable del ESTUDIO.
 *
 * Qué es y qué NO es:
 *
 * - Esto es el ejercicio del estudio (la empresa que usa el software). Marca
 *   desde qué fecha se puede asentar y cuándo se reinicia la numeración de los
 *   documentos internos (FV, RC, AB…).
 * - El ejercicio de cada **cliente** es otra cosa, en otra pantalla: cada uno
 *   tiene su fecha de cierre y no tiene por qué coincidir con ésta (el estudio
 *   puede cerrar en agosto y un cliente en diciembre).
 *
 * El botón Cerrar no exige que esté todo conciliado: es una trava para que
 * nadie meta un movimiento abajo de una fecha ya cerrada sin darse cuenta.
 */
export default function EjercicioConfig() {
  const [lista, setLista] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  const [editando, setEditando] = useState(null); // el ejercicio abierto
  const [nuevo, setNuevo] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      const r = await listarEjercicios();
      setLista(r.ejercicios);
      setResumen(r.resumen);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const limpiarAvisos = () => {
    setError("");
    setMensaje("");
  };

  const crear = async (e) => {
    e.preventDefault();
    limpiarAvisos();
    const f = e.target;
    try {
      const r = await crearEjercicio({
        nombre: f.elements.nombre.value.trim(),
        fecha_inicio: f.elements.fecha_inicio.value,
        fecha_fin: f.elements.fecha_fin.value,
        cerrado: false,
      });
      setNuevo(false);
      setMensaje(
        `Listo: quedó el ejercicio «${r.nombre}» (${fecha(r.fecha_inicio)} a ` +
          `${fecha(r.fecha_fin)}), abierto y recibiendo asientos.`
      );
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    limpiarAvisos();
    const f = e.target;
    try {
      const r = await editarEjercicio(editando.id_ejercicio, {
        nombre: f.elements.nombre.value.trim(),
        fecha_inicio: f.elements.fecha_inicio.value,
        fecha_fin: f.elements.fecha_fin.value,
      });
      setEditando(null);
      setMensaje(`Listo: «${r.nombre}» quedó actualizado.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const cambiarEstado = async (ej) => {
    limpiarAvisos();
    const queresCerrar = !ej.cerrado;
    const ok = window.confirm(
      queresCerrar
        ? `¿Cerrar el ejercicio «${ej.nombre}»?\n\n` +
            "Deja de recibir asientos: si cargás una factura con fecha dentro " +
            "de este ejercicio, el sistema va a avisar y no la va a asentar. " +
            "Los asientos que ya están no se tocan."
        : `¿Reabrir el ejercicio «${ej.nombre}»?\n\n` +
            "Vuelve a recibir asientos. Si se pisa con otro ejercicio abierto, " +
            "el sistema lo va a rechazar."
    );
    if (!ok) return;
    try {
      await (queresCerrar
        ? cerrarEjercicio(ej.id_ejercicio)
        : abrirEjercicio(ej.id_ejercicio));
      await cargar();
      setMensaje(
        `Listo: «${ej.nombre}» quedó ${queresCerrar ? "cerrado" : "abierto"}.`
      );
    } catch (e) {
      setError(e.message);
    }
  };

  // --------------------------------------------------------------- pantalla
  return (
    <section>
      <h2>Ejercicio contable del estudio</h2>
      <p className="nota">
        Es el ejercicio de <b>esta empresa</b>, no el de cada cliente. Marca
        desde qué fecha se puede asentar y cuándo se reinicia la numeración de
        los documentos internos.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="ok">{mensaje}</p>}

      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && resumen && (
        <p className="nota">
          {resumen.cantidad === 0
            ? "No hay ningún ejercicio cargado: no se puede asentar nada hasta cargar uno."
            : `${resumen.abiertos} abierto(s), ${resumen.cerrados} cerrado(s).` +
              (resumen.vigente
                ? `  Hoy cae en «${resumen.vigente.nombre}».`
                : "  Hoy no cae en ningún ejercicio abierto.")}
        </p>
      )}

      {/* ------------------------------------------------------------ tabla */}
      {!cargando && lista.length > 0 && (
        <table className="tabla">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Desde</th>
              <th>Hasta</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {lista.map((e) => (
              <tr key={e.id_ejercicio}>
                <td>
                  <b>{e.nombre}</b>
                  {e.es_el_de_hoy && (
                    <small className="nota"> · es el de hoy</small>
                  )}
                </td>
                <td>{fecha(e.fecha_inicio)}</td>
                <td>{fecha(e.fecha_fin)}</td>
                <td>
                  <span className={`as-estado ${e.cerrado ? "anulado" : "contabilizado"}`}>
                    {e.cerrado ? "Cerrado" : "Abierto"}
                  </span>
                </td>
                <td className="acciones">
                  <button
                    className="btn btn-sm fantasma"
                    onClick={() => {
                      limpiarAvisos();
                      setNuevo(false);
                      setEditando(e);
                    }}
                  >
                    Editar
                  </button>
                  <button
                    className={`btn btn-sm ${e.cerrado ? "fantasma" : "peligro"}`}
                    onClick={() => cambiarEstado(e)}
                  >
                    {e.cerrado ? "Reabrir" : "Cerrar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ------------------------------------------------------------- alta */}
      <div className="form-acciones">
        <button
          className="btn"
          onClick={() => {
            limpiarAvisos();
            setEditando(null);
            setNuevo((v) => !v);
          }}
        >
          {nuevo ? "Cancelar" : "+ Nuevo ejercicio"}
        </button>
      </div>

      {nuevo && (
        <form className="form" onSubmit={crear}>
          <fieldset className="fieldset">
            <legend>Nuevo ejercicio</legend>
            <div className="form-grid">
              <label className="campo">
                <span>
                  Nombre <b className="obligatorio">*</b>
                </span>
                <input
                  name="nombre"
                  placeholder="2027/2028"
                  maxLength={40}
                  required
                />
              </label>
              <label className="campo">
                <span>
                  Desde <b className="obligatorio">*</b>
                </span>
                <input type="date" name="fecha_inicio" required />
              </label>
              <label className="campo">
                <span>
                  Hasta <b className="obligatorio">*</b>
                </span>
                <input type="date" name="fecha_fin" required />
              </label>
            </div>
            <p className="nota">
              Se abre listo para recibir asientos. No se puede superponer con
              otro ejercicio abierto: si se pisan, el sistema avisa.
            </p>
            <div className="form-acciones">
              <button className="btn" type="submit">Crear</button>
            </div>
          </fieldset>
        </form>
      )}

      {/* ---------------------------------------------------------- edición */}
      {editando && (
        <form className="form" onSubmit={guardar}>
          <fieldset className="fieldset">
            <legend>Modificar «{editando.nombre}»</legend>
            <div className="form-grid">
              <label className="campo">
                <span>
                  Nombre <b className="obligatorio">*</b>
                </span>
                <input name="nombre" defaultValue={editando.nombre} required />
              </label>
              <label className="campo">
                <span>
                  Desde <b className="obligatorio">*</b>
                </span>
                <input
                  type="date"
                  name="fecha_inicio"
                  defaultValue={editando.fecha_inicio}
                  required
                />
              </label>
              <label className="campo">
                <span>
                  Hasta <b className="obligatorio">*</b>
                </span>
                <input
                  type="date"
                  name="fecha_fin"
                  defaultValue={editando.fecha_fin}
                  required
                />
              </label>
            </div>
            <p className="nota">
              Esto NO cambia el estado (abierto/cerrado): para eso está el botón
              de la tabla.
            </p>
            <div className="form-acciones">
              <button className="btn" type="submit">Guardar</button>
              <button
                className="btn fantasma"
                type="button"
                onClick={() => setEditando(null)}
              >
                Cancelar
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}