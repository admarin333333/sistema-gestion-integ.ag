import { useEffect, useState } from "react";
import { detalleVencimientos } from "../api/vencimientos.js";
import { fecha } from "../formato.js";
import { MESES, diasPara } from "./vencimientosComun.js";

const hoy = new Date();

/**
 * Pantalla de consulta: qué vence a cada dígito de CUIT y a qué clientes les
 * toca. Los datos se cargan en Configuración → Vencimientos.
 */
export default function Vencimientos() {
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [detalle, setDetalle] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setDetalle(await detalleVencimientos(anio, mes));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anio, mes]);

  const selectorPeriodo = (
    <div className="buscador">
      <label className="campo">
        <span>Año</span>
        <input
          type="number"
          value={anio}
          min="2000"
          max="2100"
          onChange={(e) => setAnio(Number(e.target.value) || hoy.getFullYear())}
        />
      </label>
      <label className="campo">
        <span>Mes</span>
        <select value={mes} onChange={(e) => setMes(Number(e.target.value))}>
          {MESES.map((m, i) => (
            <option key={m} value={i + 1}>{m}</option>
          ))}
        </select>
      </label>
      <button className="btn btn-sm" type="button" onClick={cargar} disabled={cargando}>
        {cargando ? "Buscando…" : "Ver"}
      </button>
    </div>
  );

  return (
    <section>
      <span className="kicker">Calendario impositivo</span>
      <h1>Vencimientos impositivos</h1>
      <p className="lead">
        Fechas de vencimiento de cada concepto, agrupadas por el último dígito
        del CUIT del cliente.
      </p>

      {selectorPeriodo}
      {error && <p className="error">{error}</p>}
      {cargando && <p className="nota">Buscando…</p>}

      {detalle && !cargando && (
        <>
          <p className="nota">
            {MESES[mes - 1]} {anio} — {detalle.total_vencimientos} vencimientos
            cargados.
          </p>

          {detalle.grupos.length === 0 && (
            <p className="nota">
              Todavía no cargaste los vencimientos de este mes. Cargalos en
              Configuración → "Vencimientos impositivos".
            </p>
          )}

          {detalle.grupos.map((g) => (
            <div className="panel" key={g.ultimo_digito}>
              <h3>
                CUIT termina en {g.ultimo_digito}
                <small className="eecc-nota">
                  {" "}· {g.cantidad_clientes} cliente{g.cantidad_clientes === 1 ? "" : "s"}
                </small>
              </h3>
              <div className="tabla-envoltura">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Concepto</th>
                      <th className="derecha">Vence</th>
                      <th>Días</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.items
                      .slice()
                      .sort((a, b) => a.fecha_vencimiento.localeCompare(b.fecha_vencimiento))
                      .map((it) => (
                        <tr key={it.impuesto}>
                          <td>{it.impuesto_label}</td>
                          <td className="mono">{fecha(it.fecha_vencimiento)}</td>
                          <td className="mono">{diasPara(it.fecha_vencimiento)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              <p className="eecc-nota">
                <b>Clientes:</b>{" "}
                {g.clientes.length === 0
                  ? "ninguno con este dígito"
                  : g.clientes.map((c) => `${c.nombre} (${c.cuit})`).join(" · ")}
              </p>
            </div>
          ))}

          {detalle.sin_cuit && detalle.sin_cuit.length > 0 && (
            <div className="panel">
              <h3>
                Sin CUIT cargado
                <small className="eecc-nota"> · no se pueden agrupar</small>
              </h3>
              <p className="nota">
                Estos clientes no tienen CUIT, así que no se sabe cuándo les vence
                cada concepto. Cargales el CUIT en su ficha.
              </p>
              <ul>
                {detalle.sin_cuit.map((c) => (
                  <li key={c.nombre}>
                    <b>{c.nombre}</b>
                    {c.dni ? ` — DNI ${c.dni}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}