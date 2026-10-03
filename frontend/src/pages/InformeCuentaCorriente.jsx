import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  obtenerCuentaCorriente,
  exportarCuentaCorriente,
} from "../api/informes.js";
import { NOMBRE_ESTUDIO, pesos } from "../formato.js";

/**
 * LA CUENTA CORRIENTE DE TODOS LOS CLIENTES.
 *
 * Qué es y qué no es:
 *
 * - El **estado de deuda** es el detalle de UN cliente: todas sus facturas, una
 *   por una. Sirve para revisar una cuenta.
 * - Esto es **la lista de a quién llamar**: las partidas abiertas SUMADAS por
 *   cliente, con el teléfono al lado.
 *
 * Por qué van separadas las dos cosas —vencido y no vencido— y no un total
 * único: son dos cobranças distintas. Lo vencido hay que ir a buscarlo hoy, lo que
 * todavía tiene plazo se cobra solo en su momento. Un total único esconde las dos
 * y el contador termina persiguiendo a alguien que tiene 15 días.
 *
 * **El orden NO es alfabético** (lo decide el backend): es por importe vencido,
 * de mayor a menor. Al que va a llamar le interesa el que más debe, no el
 * primero de la A. Por eso el orden no se puede cambiar desde acá.
 *
 * Todos los totales salen del backend: si los sumara el navegador, el número de
 * la pantalla y el del Excel no coincidirían.
 */
export default function CuentaCorriente() {
  const navigate = useNavigate();
  const [filtros, setFiltros] = useState({ desde: "", hasta: "", solo_vencidos: false });
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [filtroRapido, setFiltroRapido] = useState("");

  const cargar = async (f = filtros) => {
    setCargando(true);
    setError("");
    try {
      setData(
        await obtenerCuentaCorriente({
          desde: f.desde || undefined,
          hasta: f.hasta || undefined,
          solo_vencidos: f.solo_vencidos || undefined,
        })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtros.desde, filtros.hasta, filtros.solo_vencidos]);

  // Los rangos que el contador usa todos los días para ir a cobrar.
  const aplicarRango = (clave) => {
    setFiltroRapido(clave);
    const hoy = new Date();
    const iso = (d) => d.toISOString().slice(0, 10);
    let desde = "";
    let hasta = iso(hoy);

    if (clave === "mes") {
      desde = iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1));
    } else if (clave === "anio") {
      desde = iso(new Date(hoy.getFullYear(), 0, 1));
    } else if (clave === "30") {
      desde = iso(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 30));
    }
    // "todo" deja las fechas vacías: el informe va por lo que esté pendiente,
    // sin acotar por fecha de emisión.

    setFiltros((v) => ({ ...v, desde, hasta: clave === "todo" ? "" : hasta }));
  };

  const cambiar = (campo) => (e) => {
    setFiltroRapido("");
    setFiltros({ ...filtros, [campo]: e.target.value });
  };

  const exportar = async () => {
    try {
      await exportarCuentaCorriente({
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        solo_vencidos: filtros.solo_vencidos || undefined,
      });
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Cuenta corriente — partidas abiertas</span>
      </div>

      <span className="kicker">Informes</span>
      <h1>Cuenta corriente</h1>
      <p className="lead">
        Cuánto le debe <b>cada cliente</b>, separado en <b>vencido</b> (hay que
        ir a cobrarlo) y <b>no vencido</b> (todavía tiene plazo). Con el teléfono
        al lado para llamar. Ordenado por importe vencido: primero el que más debe.
      </p>

      <form className="buscador" onSubmit={(e) => e.preventDefault()}>
        <label className="campo">
          <span>Rango</span>
          <select
            value={filtroRapido}
            onChange={(e) => aplicarRango(e.target.value)}
          >
            <option value="">Todo lo pendiente</option>
            <option value="30">Últimos 30 días</option>
            <option value="mes">Del mes</option>
            <option value="anio">Del año</option>
          </select>
        </label>

        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>

        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>

        <label className="campo">
          <span>Mostrar</span>
          <select
            value={filtros.solo_vencidos ? "vencidos" : "todos"}
            onChange={(e) =>
              setFiltros({
                ...filtros,
                solo_vencidos: e.target.value === "vencidos",
              })
            }
          >
            <option value="todos">Todos los que deben</option>
            <option value="vencidos">Solo los que tienen vencido</option>
          </select>
        </label>

        <button className="btn btn-sm fantasma" type="button" onClick={exportar} disabled={cargando || !data}>
          Descargar Excel
        </button>
        <button className="btn btn-sm fantasma" type="button" onClick={() => window.print()}>
          Imprimir
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && data && data.cantidad_clientes === 0 && (
        <p className="nota">
          No hay clientes con saldo pendiente en este rango.
        </p>
      )}

      {!cargando && data && data.cantidad_clientes > 0 && (
        <>
          {/* Las tres cifras del día. Lo vencido va aparte y en rojo cuando hay
              algo: es la única que dispara una llamada. */}
          <div className="panel resumen-deuda">
            <div>
              <span>Total a cobrar</span>
              <b>{pesos(data.total_pendiente)}</b>
              <small>{data.cantidad_clientes} cliente(s)</small>
            </div>
            <div className={data.total_vencido > 0 ? "alerta" : ""}>
              <span>Vencido</span>
              <b>{pesos(data.total_vencido)}</b>
              <small>{data.cantidad_vencidos} cliente(s)</small>
            </div>
            <div>
              <span>No vencido</span>
              <b>{pesos(data.total_no_vencido)}</b>
              <small>todavía dentro del plazo</small>
            </div>
            <div>
              <span>Sin teléfono</span>
              <b>{data.sin_telefono}</b>
              <small>cargarles el contacto</small>
            </div>
          </div>

          {data.sin_telefono > 0 && (
            <p className="nota">
              {data.sin_telefono === 1
                ? "Hay 1 cliente sin teléfono cargado."
                : `Hay ${data.sin_telefono} clientes sin teléfono cargado.`}{" "}
              Cargáselo en la ficha para poder llamar.
            </p>
          )}

          <div className="tabla-scroll">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Teléfono</th>
                  <th className="derecha">Vencido</th>
                  <th className="derecha">No vencido</th>
                  <th className="derecha">Total a cobrar</th>
                  <th className="derecha">Días</th>
                  <th className="derecha">Comprob.</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((f) => (
                  <tr
                    key={f.cliente_id ?? f.cliente}
                    className={f.vencido > 0 ? "fila-vencida" : ""}
                  >
                    <td>
                      <b>{f.cliente}</b>
                      {f.email && <small className="nota">{f.email}</small>}
                    </td>
                    <td className="mono">
                      {f.telefono || <span className="vacio">sin cargar</span>}
                    </td>
                    <td className="mono derecha">
                      {f.vencido > 0 ? (
                        <b className="vencida">{pesos(f.vencido)}</b>
                      ) : (
                        <span className="vacio">—</span>
                      )}
                    </td>
                    <td className="mono derecha">{pesos(f.no_vencido)}</td>
                    <td className="mono derecha">
                      <b>{pesos(f.pendiente)}</b>
                    </td>
                    <td className="mono derecha">
                      {f.dias_max > 0 ? (
                        <b className="vencida">{f.dias_max}</b>
                      ) : (
                        <span className="vacio">—</span>
                      )}
                    </td>
                    <td className="mono derecha">{f.comprobantes}</td>
                    <td className="acciones">
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => navigate(`/cliente-ficha/${f.cliente_id}`)}
                        disabled={!f.cliente_id}
                        title="Ver la ficha del cliente"
                      >
                        Ficha
                      </button>
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => navigate(`/estado-deuda?cliente=${f.cliente_id}`)}
                        disabled={!f.cliente_id}
                        title="Ver el detalle de sus comprobantes"
                      >
                        Detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="2"><b>TOTALES</b></td>
                  <td className="mono derecha"><b>{pesos(data.total_vencido)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.total_no_vencido)}</b></td>
                  <td className="mono derecha"><b>{pesos(data.total_pendiente)}</b></td>
                  <td colSpan="3"></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="nota">
            Al {data.hoy}. Una factura vence {data.dias_plazo} días después de su
            fecha.
          </p>
        </>
      )}
    </section>
  );
}