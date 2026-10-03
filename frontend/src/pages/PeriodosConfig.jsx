import { useEffect, useState } from "react";
import {
  cambiarPeriodo,
  ejercicioVigente,
  listarPeriodos,
} from "../api/ejercicios.js";
import { leerPeriodoGuardado } from "../components/PeriodoActual.jsx";

/** "2026-09-01" → "01/09/2026" */
function fecha(iso) {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

/**
 * Los PERÍODOS: los 12 meses de un ejercicio, que se abren y se cierran uno por
 * uno.
 *
 * Para qué están, y por qué no alcanza con el ejercicio:
 *
 * - El **ejercicio** dice "nadie escribe en este año". Con eso alcanza para el
 *   ejercicio cerrado.
 * - El **período** dice "nadie escribe en este mes". Es lo que faltaba: hoy,
 *   con el ejercicio abierto, se puede anular tranquilamente un recibo de
 *   septiembre y nadie se entera.
 *
 * Ojo con el nombre: el período 1 es el mes en que **arranca el ejercicio**, no
 * enero. Con el ejercicio del 01/09/2026 al 31/08/2027, el 1 es septiembre de
 * 2026 y el 12 es agosto de 2027. Por eso van numerados del 1 al 12 y no con el
 * número de mes del calendario.
 *
 * **Cerrar no bloquea leer.** El Mayor, los informes y los listados se siguen
 * consultando: cerrado es "no escribas acá", no "no mires acá".
 *
 * **Cerrar un mes con documentos se puede**, pero la pantalla avisa cuántos hay
 * y pide confirmar. El cierre es una trava para no meter cosas sin querer, no
 * una validación contable.
 */
export default function PeriodosConfig() {
  const [periodos, setPeriodos] = useState([]);
  const [ejercicio, setEjercicio] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      const vigente = await ejercicioVigente();
      if (!vigente.ejercicio) {
        setPeriodos([]);
        setEjercicio(null);
        return;
      }
      setEjercicio(vigente.ejercicio);
      const r = await listarPeriodos(vigente.ejercicio.id_ejercicio);
      setPeriodos(r.periodos);
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

  const alternar = async (p) => {
    setError("");
    setMensaje("");
    const queresCerrar = !p.cerrado;

    // Primera vez: se avisa y se pide confirmar, sin llamar al backend. Si ya
    // se confirmó, se manda `forzar`.
    if (queresCerrar && p.tiene_movimientos && !p.confirmado) {
      const partes = [];
      if (p.documentos) {
        partes.push(
          `${p.documentos} documento${p.documentos === 1 ? "" : "s"}`
        );
      }
      if (p.asientos) {
        partes.push(`${p.asientos} asiento${p.asientos === 1 ? "" : "s"}`);
      }
      const ok = window.confirm(
        `El período ${p.numero} · ${p.nombre} tiene ${partes.join(" y ")} ` +
          "cargados.\n\n" +
          "Si lo cerrás igual no vas a poder anularlos ni modificarlos. " +
          "Vas a tener que reabrir el período para tocar eso.\n\n" +
          "¿Cerrar igual?"
      );
      if (!ok) return;
      // Se marca para que el próximo clic vaya directo al backend.
      setPeriodos((v) =>
        v.map((x) => (x.id_periodo === p.id_periodo ? { ...x, confirmado: true } : x))
      );
      return;
    }

    try {
      const r = await cambiarPeriodo(p.id_periodo, queresCerrar, !!p.confirmado);
      const actualizado = { ...p, ...r, confirmado: false };
      setPeriodos((v) =>
        v.map((x) => (x.id_periodo === p.id_periodo ? actualizado : x))
      );
      setMensaje(
        `Listo: el período ${r.numero} · ${r.nombre} quedó ${r.cerrado ? "cerrado" : "abierto"}.`
      );

      // Si el contador tenía ESTE período elegido en la barra de arriba, hay que
      // avisarle: si no, la barra seguiría diciendo "abierto" y el contador
      // trabajaría en un mes cerrado sin enterarse. Solo se avisa cuando cambió
      // el que está elegido; cerrar otro período no cambia lo que está haciendo
      // ahora mismo.
      const elegido = leerPeriodoGuardado();
      if (elegido && elegido.id_periodo === p.id_periodo) {
        window.dispatchEvent(
          new CustomEvent("gc:periodo-cambiado", { detail: actualizado })
        );
      }
    } catch (e) {
      setError(e.message);
    }
  };

  if (cargando) return <p className="nota">Cargando los períodos…</p>;

  if (!ejercicio) {
    return (
      <section>
        <h2>Períodos</h2>
        <p className="nota">
          No hay ningún ejercicio abierto: los períodos son los meses de un
          ejercicio, así que primero hay que cargar uno.
        </p>
      </section>
    );
  }

  const abiertos = periodos.filter((p) => !p.cerrado).length;

  return (
    <section>
      <h2>Períodos de «{ejercicio.nombre}»</h2>
      <p className="nota">
        Los 12 meses del ejercicio, del 1 (que es el mes en que arranca) al 12.
        Con un período <b>cerrado</b> no se puede cargar, anular ni modificar nada
        con fecha en ese mes. <b>Mirar</b> los documentos sí se puede: cerrar es
        para no escribir, no para no mirar.
      </p>

      {error && <p className="error">{error}</p>}
      {mensaje && <p className="ok">{mensaje}</p>}
      {ejercicio.cerrado && (
        <p className="error">
          El ejercicio está cerrado. Sus períodos no se pueden abrir hasta
          reabrir el ejercicio (el botón está arriba, en la tabla de
          ejercicios).
        </p>
      )}

      {periodos.length === 0 ? (
        <p className="nota">
          Este ejercicio no tiene períodos. Passá por
          {" "}
          <code>python -X utf8 backend/migrar_periodos.py</code> para crearlos.
        </p>
      ) : (
        <>
          <p className="nota">
            {abiertos} abierto(s) de 12 · {12 - abiertos} cerrado(s).
          </p>
          <div className="tabla-scroll">
            <table className="tabla">
              <thead>
                <tr>
                  <th>N.º</th>
                  <th>Período</th>
                  <th>Desde</th>
                  <th>Hasta</th>
                  <th>Documentos</th>
                  <th>Asientos</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {periodos.map((p) => (
                  <tr key={p.id_periodo} className={p.cerrado ? "fila-apagada" : ""}>
                    <td className="mono">{p.numero}</td>
                    <td>
                      <b>{p.nombre}</b>
                    </td>
                    <td className="mono">{fecha(p.fecha_inicio)}</td>
                    <td className="mono">{fecha(p.fecha_fin)}</td>
                    <td className="mono">
                      {p.documentos ? (
                        p.documentos
                      ) : (
                        <span className="vacio">—</span>
                      )}
                    </td>
                    <td className="mono">
                      {p.asientos ? (
                        p.asientos
                      ) : (
                        <span className="vacio">—</span>
                      )}
                    </td>
                    <td>
                      <span
                        className={`as-estado ${
                          p.cerrado ? "anulado" : "contabilizado"
                        }`}
                      >
                        {p.cerrado ? "Cerrado" : "Abierto"}
                      </span>
                    </td>
                    <td className="acciones">
                      <button
                        className={`btn btn-sm ${p.cerrado ? "" : "peligro"}`}
                        onClick={() => alternar(p)}
                        title={
                          p.cerrado
                            ? `Reabrir ${p.nombre}`
                            : `Cerrar ${p.nombre}`
                        }
                      >
                        {p.cerrado ? "Reabrir" : "Cerrar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}