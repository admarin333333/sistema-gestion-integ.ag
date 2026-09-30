import { useAuth } from "../context/AuthContext.jsx";

const FASES = [
  { n: 1, txt: "Login, roles y base de datos", ok: true },
  { n: 2, txt: "Clientes: alta, modificación y baja", ok: true },
  { n: 3, txt: "Facturas, recibos y cuenta corriente", ok: false },
  { n: 4, txt: "Dashboard con totales y alertas", ok: false },
  { n: 5, txt: "PDF e impresión", ok: false },
  { n: 6, txt: "Preparación ARCA", ok: false },
];

export default function Dashboard() {
  const { user } = useAuth();

  return (
    <section>
      <span className="kicker">Panel</span>
      <h1>Hola, Contador/a</h1>
      <p className="lead">
        Entraste como <b>{user.rol}</b>. La Fase 2 está operativa: alta,
        modificación, baja condicional y la ficha con sus pestañas.
      </p>

      <div className="kpis">
        <article className="kpi">
          <b>—</b>
          <span>Clientes activos</span>
        </article>
        <article className="kpi">
          <b>—</b>
          <span>Facturado este mes</span>
        </article>
        <article className="kpi">
          <b>—</b>
          <span>Cobrado este mes</span>
        </article>
        <article className="kpi">
          <b>—</b>
          <span>Pendiente</span>
        </article>
        <article className="kpi">
          <b>—</b>
          <span>Facturas vencidas</span>
        </article>
      </div>
      <p className="nota">Los KPIs se calculan cuando esté la Fase 4.</p>

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
