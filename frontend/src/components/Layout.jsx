import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { listarServicios, obtenerCliente } from "../api/clientes.js";
import Dashboard from "../pages/Dashboard.jsx";
import Clientes from "../pages/Clientes.jsx";
import ClienteForm from "../pages/ClienteForm.jsx";
import ClienteFicha from "../pages/ClienteFicha.jsx";
import Facturas from "../pages/Facturas.jsx";
import FacturaForm from "../pages/FacturaForm.jsx";
import Recibos from "../pages/Recibos.jsx";
import ReciboForm from "../pages/ReciboForm.jsx";
import EstadoCuenta from "../pages/EstadoCuenta.jsx";
import Anticipos from "../pages/Anticipos.jsx";
import AnticipoForm from "../pages/AnticipoForm.jsx";
import EstadoDeudaTotal from "../pages/EstadoDeudaTotal.jsx";
import AnticiposPendientes from "../pages/AnticiposPendientes.jsx";

const MENU = [
  { label: "Dashboard", fase: 1, ir: "dashboard" },
  { label: "Clientes", fase: 2, ir: "clientes" },
  { label: "Facturas", fase: 3, ir: "facturas" },
  { label: "Recibos", fase: 3, ir: "recibos" },
  { label: "Anticipos", fase: 3, ir: "anticipos" },
  { label: "Estado de cuenta", fase: 3, ir: "cuenta" },
  { label: "Estado de deuda", fase: 4, ir: "estado-deuda" },
  { label: "Anticipos pendientes", fase: 4, ir: "anticipos-pendientes" },
  { label: "Informes", fase: 5 },
];

/** Qué pantallas pertenecen a qué lugar del menú. */
const GRUPOS = {
  dashboard: "dashboard",
  clientes: "clientes",
  "cliente-alta": "clientes",
  "cliente-editar": "clientes",
  "cliente-ficha": "clientes",
  facturas: "facturas",
  "factura-alta": "facturas",
  "factura-editar": "facturas",
  recibos: "recibos",
  "recibo-alta": "recibos",
  "recibo-editar": "recibos",
  anticipos: "anticipos",
  "anticipo-alta": "anticipos",
  "anticipo-editar": "anticipos",
  cuenta: "cuenta",
  "estado-deuda": "estado-deuda",
  "anticipos-pendientes": "anticipos-pendientes",
};

const fechaHoy = () =>
  new Date().toLocaleDateString("es-AR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

export default function Layout() {
  const { user, logout } = useAuth();
  const [pagina, setPagina] = useState({ n: "dashboard" });
  const [servicios, setServicios] = useState([]);
  const [cliente, setCliente] = useState(null);

  const ir = (n, id, aviso) => setPagina({ n, id, aviso });

  useEffect(() => {
    listarServicios()
      .then(setServicios)
      .catch(() => setServicios([]));
  }, []);

  useEffect(() => {
    if (pagina.n !== "cliente-editar") return;
    setCliente(null);
    obtenerCliente(pagina.id)
      .then(setCliente)
      .catch((e) => alert(e.message));
  }, [pagina]);

  const contenido = () => {
    switch (pagina.n) {
      case "facturas":
        return <Facturas ir={ir} aviso={pagina.aviso} />;
      case "factura-alta":
        return (
          <FacturaForm
            onGuardado={(r, aviso) => ir("facturas", null, aviso)}
            onCancelar={() => ir("facturas")}
          />
        );
      case "factura-editar":
        return (
          <FacturaForm
            facturaId={pagina.id}
            onGuardado={(r, aviso) => ir("facturas", null, aviso)}
            onCancelar={() => ir("facturas")}
          />
        );
      case "clientes":
        return <Clientes ir={ir} />;
      case "cliente-alta":
        return (
          <ClienteForm
            servicios={servicios}
            onGuardado={(c) => ir("cliente-ficha", c.id)}
            onCancelar={() => ir("clientes")}
          />
        );
      case "cliente-editar":
        if (!cliente) return <p className="nota">Cargando…</p>;
        return (
          <ClienteForm
            cliente={cliente}
            servicios={servicios}
            onGuardado={(c) => ir("cliente-ficha", c.id)}
            onCancelar={() => ir("cliente-ficha", cliente.id)}
          />
        );
      case "cliente-ficha":
        return (
          <ClienteFicha
            clienteId={pagina.id}
            esAdmin={user.rol === "admin"}
            onVolver={() => ir("clientes")}
            onEditar={() => ir("cliente-editar", pagina.id)}
          />
        );
      case "recibos":
        return <Recibos ir={ir} aviso={pagina.aviso} />;
      case "recibo-alta":
        return (
          <ReciboForm
            onGuardado={(r, aviso) => ir("recibos", null, aviso)}
            onCancelar={() => ir("recibos")}
          />
        );
      case "recibo-editar":
        return (
          <ReciboForm
            reciboId={pagina.id}
            onGuardado={(r, aviso) => ir("recibos", null, aviso)}
            onCancelar={() => ir("recibos")}
          />
        );
      case "anticipos":
        return <Anticipos ir={ir} aviso={pagina.aviso} />;
      case "anticipo-alta":
        return (
          <AnticipoForm
            onGuardado={(r, aviso) => ir("anticipos", null, aviso)}
            onCancelar={() => ir("anticipos")}
          />
        );
      case "anticipo-editar":
        return (
          <AnticipoForm
            anticipoId={pagina.id}
            onGuardado={(r, aviso) => ir("anticipos", null, aviso)}
            onCancelar={() => ir("anticipos")}
          />
        );
      case "cuenta":
        return <EstadoCuenta ir={ir} />;
      case "estado-deuda":
        return <EstadoDeudaTotal ir={ir} />;
      case "anticipos-pendientes":
        return <AnticiposPendientes ir={ir} />;
      default:
        return <Dashboard ir={ir} />;
    }
  };

  return (
    <>
      <header className="topbar">
        <div className="wrap">
          <a className="brand" href="/" onClick={(e) => { e.preventDefault(); ir("dashboard"); }}>
            Gestión <span>Estudio contable</span>
          </a>

          <div className="hoy">
            <b>{fechaHoy()}</b>
            <small>
              {user.nombre} · {user.rol}
            </small>
          </div>

          <button className="btn btn-sm fantasma" onClick={logout}>
            Salir
          </button>
        </div>
      </header>

      <nav className="menu wrap">
        {MENU.map((m) => {
          const activo = m.ir && GRUPOS[pagina.n] === m.ir;
          return (
            <span
              key={m.label}
              className={`item${activo ? " activo" : ""}${m.ir ? " disponible" : ""}`}
              onClick={m.ir ? () => ir(m.ir) : undefined}
              title={m.ir ? "" : `Disponible en la Fase ${m.fase}`}
            >
              {m.label}
              {!m.ir && <i>F{m.fase}</i>}
            </span>
          );
        })}
      </nav>

      <main className="wrap">{contenido()}</main>

      <footer className="pie">
        <div className="wrap">Sistema de gestión · Fase 3 · datos locales</div>
      </footer>
    </>
  );
}
