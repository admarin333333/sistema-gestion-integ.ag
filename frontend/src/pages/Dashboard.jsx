import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { getKPIs, getAlertas, getProximasVencimientos, getResultadoPorPeriodo } from "../api/dashboard.js";
import { exportarProveedores, exportarCompras, exportarCentros, exportarResultados } from "../api/informes.js";
import Periodo from "../components/Periodo.jsx";
import Variantes from "../components/Variantes.jsx";
import GraficoResultado from "../components/GraficoResultado.jsx";
import { pesos, fecha } from "../formato.js";

const CHIP_COLOR = {
  rojo: "rojo",
  naranja: "naranja",
  amarillo: "amarillo",
  verde: "verde",
};

export default function Dashboard() {
  const { user } = useAuth();
  const [kpis, setKPIs] = useState({
    clientes_activos: 0,
    facturado_mes: 0,
    cobrado_mes: 0,
    pendiente_mes: 0,
    facturas_vencidas: 0,
  });
  const [alertas, setAlertas] = useState([]);
  const [proximas, setProximas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  // El gráfico va aparte del error general: si el gráfico falla (por ejemplo que
  // no haya ejercicio vigente) los KPIs y las alertas siguen sirviendo. Un solo
  // `error` dejaría la pantalla en blanco por un chart que no cargó.
  const [resultado, setResultado] = useState(null);
  const [errorGrafico, setErrorGrafico] = useState("");
  const [filtros, setFiltros] = useState({ desde: "", hasta: "" });

  useEffect(() => {
    const cargar = async () => {
      setCargando(true);
      setError("");
      try {
        const [k, a, p] = await Promise.all([
          getKPIs(),
          getAlertas(30),
          getProximasVencimientos(7),
        ]);
        setKPIs(k);
        setAlertas(a);
        setProximas(p);
      } catch (e) {
        setError(e.message);
      } finally {
        setCargando(false);
      }
    };
    cargar();
    // El gráfico se pide aparte y a propósito no corta el resto: si falla, los
    // KPIs, las alertas y los vencimientos ya están y se siguen viendo.
    getResultadoPorPeriodo()
      .then(setResultado)
      .catch((e) => setErrorGrafico(e.message));
  }, []);

  // Mientras carga: el layout completo con placeholders — sin pantalla en
  // blanco, así el LCP pinta apenas arranca React (mejora de rendimiento).
  if (error) return <p className="error">Error: {error}</p>;

  const CHIP_STYLE = {
    rojo: { background: "rgba(248,113,113,0.15)", border: "1px solid #f87171", color: "#fca5a5" },
    naranja: { background: "rgba(251,146,60,0.15)", border: "1px solid #fb923c", color: "#fdba74" },
    amarillo: { background: "rgba(250,204,21,0.15)", border: "1px solid #facc15", color: "#fde047" },
    verde: { background: "rgba(52,211,153,0.15)", border: "1px solid #34d399", color: "#86efac" },
  };

  return (
    <section>
      <span className="kicker">Panel</span>
      <h1>Hola, Contador/a</h1>
      <p className="lead">
        Entraste como <b>{user.rol}</b>. Dashboard con KPIs y alertas de vencimiento.
      </p>

      {/* KPIs */}
      <div className="kpis">
        <article className="kpi">
          <b>{cargando ? "…" : kpis.clientes_activos}</b>
          <span>Clientes activos</span>
        </article>
        <article className="kpi">
          <b>{cargando ? "…" : pesos(kpis.facturado_mes)}</b>
          <span>Facturado este mes</span>
        </article>
        <article className="kpi">
          <b>{cargando ? "…" : pesos(kpis.cobrado_mes)}</b>
          <span>Cobrado este mes</span>
        </article>
        <article className="kpi">
          <b>{cargando ? "…" : pesos(kpis.pendiente_mes)}</b>
          <span>Pendiente este mes</span>
        </article>
        <article className="kpi">
          <b>{cargando ? "…" : kpis.facturas_vencidas}</b>
          <span>Facturas vencidas</span>
        </article>
      </div>

      {/* Informes en Excel */}
      <div style={{ marginTop: "2rem" }}>
        <h2>🧾 Informes</h2>
        <p className="nota">
          Elegí el período y descargá el Excel. Si dejás las fechas vacías, se
          toma todo.
        </p>
        <form
          className="buscador"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <Periodo filtros={filtros} setFiltros={setFiltros} />
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => exportarProveedores(filtros)}
          >
            Proveedores
          </button>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => exportarCompras(filtros)}
          >
            Compras
          </button>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => exportarCentros(filtros)}
          >
            Centro de costos
          </button>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => exportarResultados(filtros)}
          >
            Resultados
          </button>
        </form>
        <Variantes pantalla="dashboard" filtros={filtros} setFiltros={setFiltros} />
      </div>

      {/* Alertas de vencimiento */}
      {cargando && (
        <div style={{ marginTop: "2rem" }}>
          <h2>⚠️ Alertas de vencimiento (30 días)</h2>
          <div className="tabla-envoltura" style={{ minHeight: "9rem" }}>
            <p className="nota">Cargando alertas…</p>
          </div>
        </div>
      )}
      {!cargando && alertas.length > 0 && (
        <div style={{ marginTop: "2rem" }}>
          <h2>⚠️ Alertas de vencimiento (30 días)</h2>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Nivel</th>
                  <th>Factura</th>
                  <th>Cliente</th>
                  <th>Vencimiento</th>
                  <th className="derecha">Importe</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {alertas.map((a) => (
                  <tr key={a.factura_id} style={{ background: CHIP_STYLE[a.nivel]?.background }}>
                    <td>
                      <span className={`chip ${a.nivel}`} style={{ ...CHIP_STYLE[a.nivel] }}>{a.label}</span>
                    </td>
                    <td className="mono">{a.tipo_comprobante} {a.punto_venta}-{a.numero}</td>
                    <td>{a.cliente_nombre}</td>
                    <td className="mono">{fecha(a.fecha_vencimiento)}</td>
                    <td className="mono derecha">{pesos(a.importe)}</td>
                    <td><span className={`chip ${a.nivel}`} style={{ ...CHIP_STYLE[a.nivel] }}>{a.nivel}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Próximos vencimientos (7 días) */}
      {cargando && (
        <div style={{ marginTop: "2rem" }}>
          <h2>📅 Próximos vencimientos (7 días)</h2>
          <div className="tabla-envoltura" style={{ minHeight: "9rem" }}>
            <p className="nota">Cargando vencimientos…</p>
          </div>
        </div>
      )}
      {!cargando && proximas.length > 0 && (
        <div style={{ marginTop: "2rem" }}>
          <h2>📅 Próximos vencimientos (7 días)</h2>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Factura</th>
                  <th>Cliente</th>
                  <th>Vencimiento</th>
                  <th className="derecha">Importe</th>
                  <th>Días</th>
                </tr>
              </thead>
              <tbody>
                {proximas.map((f) => (
                  <tr key={f.id}>
                    <td className="mono">{f.tipo_comprobante} {f.punto_venta}-{f.numero}</td>
                    <td>{f.cliente_nombre}</td>
                    <td className="mono">{fecha(f.fecha_vencimiento)}</td>
                    <td className="mono derecha">{pesos(f.importe)}</td>
                    <td className="mono">
                      <span className={`chip ${f.dias_restantes <= 3 ? "naranja" : "amarillo"}`}>
                        {f.dias_restantes} día{f.dias_restantes !== 1 ? "s" : ""}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ingresos y gastos mes a mes del ejercicio (en el lugar del antiguo
          "Estado del proyecto", que era andamiaje de desarrollo). */}
      <div style={{ marginTop: "2rem" }}>
        <h2>📊 Ingresos y gastos por mes</h2>
        {!cargando && errorGrafico && <p className="nota">{errorGrafico}</p>}
        <GraficoResultado data={resultado} />
      </div>
    </section>
  );
  }