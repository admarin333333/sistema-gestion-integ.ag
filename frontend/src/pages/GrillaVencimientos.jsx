import { useEffect, useState } from "react";
import {
  guardarVencimientos,
  listarVencimientos,
} from "../api/vencimientos.js";
import { MESES } from "./vencimientosComun.js";

/**
 * Grilla de un mes: una fila por dígito (0 a 9) y una columna por concepto.
 * Se usa en dos lugares:
 * - Configuración → Vencimientos (dentro del árbol, al clickear un mes)
 * - /vencimientos (la pantalla de consulta, aunque ahí va más reducida)
 *
 * Ojo con el borrado: el backend NO vacía un mes que tiene datos si le mandás
 * la grilla vacía, salvo que venga `vaciar`. Acá se pide el visto bueno con
 * `confirm()`, así que no se puede perder un mes cargado por un clic sin querer.
 */
export default function GrillaVencimientos({
  anio,
  mes,
  conceptos,
  alGuardar,
  compacto = false,
}) {
  const [grilla, setGrilla] = useState({});   // "digito|clave" -> fecha
  // Copia de lo último que llegó del servidor: sirve para saber si lo que hay
  // en pantalla todavía difiere de lo guardado (cambios sin guardar).
  const [guardado, setGuardado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  // Ojo: `cargar()` NO borra el mensaje de "guardado". Antes lo hacía y por eso
  // el aviso desaparecía en el acto (se ponía y enseguida se pisaba con ""),
  // y el usuario no sabía si se había guardado o no.
  const cargar = async ({ limpiarMensaje = false } = {}) => {
    setCargando(true);
    setError("");
    if (limpiarMensaje) setMensaje("");
    try {
      const filas = await listarVencimientos(anio, mes);
      const nuevo = {};
      filas.forEach((v) => {
        nuevo[`${v.ultimo_digito}|${v.impuesto}`] = v.fecha_vencimiento;
      });
      setGrilla(nuevo);
      setGuardado(nuevo);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    setMensaje("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anio, mes]);

  const celda = (digito, clave) => `${digito}|${clave}`;
  const valor = (digito, clave) => grilla[celda(digito, clave)] || "";
  const cambiar = (digito, clave, v) =>
    setGrilla((g) => ({ ...g, [celda(digito, clave)]: v }));

  const celdasConFecha = Object.values(grilla).filter((v) => v).length;
  const sucias = guardado !== null && grilla !== guardado;

  const guardar = async () => {
    // Se arma la lista de filas solo con las celdas con fecha.
    const filas = [];
    for (let d = 0; d <= 9; d += 1) {
      for (const c of conceptos) {
        const v = valor(d, c.clave);
        if (v) {
          filas.push({
            ultimo_digito: d,
            impuesto: c.clave,
            fecha_vencimiento: v,
          });
        }
      }
    }

    // Si no hay nada con fecha pero el mes ya tenía cosas, el backend lo
    // rechaza. Se avisa antes, con un mensaje claro de qué se va a perder.
    let vaciar = false;
    if (filas.length === 0 && celdasConFecha > 0) {
      vaciar = window.confirm(
        `Querés dejar ${MESES[mes - 1]} ${anio} sin ningún vencimiento?\n\n` +
          `Hoy tiene ${celdasConFecha} celda(s) con fecha. ` +
          "Si te equivocás, después lo podés recuperar desde el respaldo."
      );
      if (!vaciar) return;
    }

    setGuardando(true);
    setError("");
    setMensaje("");
    try {
      const r = await guardarVencimientos(anio, mes, filas, vaciar);
      // Primero recarga (para ver lo que quedó guardado de verdad) y recién
      // después muestra el aviso, así no lo pisa el `cargar()`.
      await cargar();
      setMensaje(
        filas.length === 0
          ? `Listo: ${MESES[mes - 1]} ${anio} quedó sin vencimientos.`
          : `Listo: se guardaron ${r.guardadas} vencimientos de ${MESES[mes - 1]} ${anio}. ` +
            "Podés volver a guardar encima para modificarlos."
      );
      if (alGuardar) alGuardar();
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="panel">
      <h3>
        {MESES[mes - 1]} {anio}
        {!compacto && (
          <small className="eecc-nota">
            {" "}· cargá la fecha de vencimiento de cada concepto para cada último
            dígito del CUIT. Los clientes que terminan en el mismo dígito vencen
            el mismo día. Lo que dejes vacío no se guarda.
          </small>
        )}
      </h3>

      {error && <p className="error">{error}</p>}
      {mensaje && (
        <p className="aviso-guardado" role="status">
          {mensaje}
        </p>
      )}
      {cargando && <p className="nota">Buscando…</p>}

      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>CUIT termina en</th>
              {conceptos.map((c) => (
                <th key={c.clave} className="derecha">{c.nombre}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
              <tr key={d}>
                <td className="mono"><b>{d}</b></td>
                {conceptos.map((c) => (
                  <td key={c.clave}>
                    <input
                      type="date"
                      value={valor(d, c.clave)}
                      onChange={(e) => cambiar(d, c.clave, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="form-acciones">
        <button className="btn" type="button" onClick={guardar} disabled={guardando}>
          {guardando ? "Guardando…" : `Guardar ${MESES[mes - 1]}`}
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => cargar({ limpiarMensaje: true })}
          disabled={cargando || guardando}
        >
          Descartar los cambios sin guardar
        </button>
        <span className="nota contador-celdas">
          {celdasConFecha} celda{celdasConFecha === 1 ? "" : "s"} con fecha
          {sucias ? " · hay cambios sin guardar" : " · todo guardado"}
        </span>
      </div>
    </div>
  );
}