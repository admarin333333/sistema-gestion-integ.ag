import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { getKPIs, getAlertas, getProximasVencimientos } from "../api/dashboard.js";
import { pesos, fecha } from "../formato.js";

const FASES = [
  { n: 1, txt: "Login, roles y base de datos", ok: true },
  { n: 2, txt: "Clientes: alta, modificación y baja", ok: true },
  { n: 3, txt: "Facturas, recibos, anticipos y cuenta corriente", ok: true },
  { n: 4, txt: "Dashboard con totales y alertas", ok: true },
  { n: 5, txt: "PDF e impresión", ok: false },
  { n: 6, txt: "Preparación ARCA", ok: false },
  { n: 7, txt: "Vercel-ready", ok: false },
];

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
  }, []);

  if (cargando) return <p className="nota">Cargando dashboard…</p>;
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
          <b>{kpis.clientes_activos}</b>
          <span>Clientes activos</span>
        </article>
        <article className="kpi">
          <b>{pesos(kpis.facturado_mes)}</b>
          <span>Facturado este mes</span>
        </article>
        <article className="kpi">
          <b>{pesos(kpis.cobrado_mes)}</b>
          <span>Cobrado este mes</span>
        </article>
        <article className="kpi">
          <b>{pesos(kpis.pendiente_mes)}</b>
          <span>Pendiente este mes</span>
        </article>
        <article className="kpi">
          <b>{kpis.facturas_vencidas}</b>
          <span>Facturas vencidas</span>
        </article>
      </div>

      {/* Alertas de vencimiento */}
      {alertas.length > 0 && (
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
      {proximas.length > 0 && (
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

      <h2>Estado del proyecto</h2>
      <ul className="fases">
        {FASES.map((f) => (
          <li key={f.n} className={f.ok ? "ok" : "pendiente"}>
            <b>Fase {f.n}</b> — {f.txt}
          </li>
        ))}
      </ul>
    </section>
  );
  }