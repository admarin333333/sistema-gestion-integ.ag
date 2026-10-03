// Rutas del sistema (React Router).
// Las pantallas (salvo Login y Dashboard, que son la entrada) se cargan bajo
// demanda con React.lazy: el JS inicial queda mucho más liviano.
import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "/src/context/AuthContext.jsx";
import Layout from "/src/components/Layout.jsx";
import Login from "/src/pages/Login.jsx";
import Dashboard from "/src/pages/Dashboard.jsx";

const Clientes = lazy(() => import("/src/pages/Clientes.jsx"));
const ClienteForm = lazy(() => import("/src/pages/ClienteForm.jsx"));
const ClienteFicha = lazy(() => import("/src/pages/ClienteFicha.jsx"));
const Servicios = lazy(() => import("/src/pages/Servicios.jsx"));
const Facturas = lazy(() => import("/src/pages/Facturas.jsx"));
const FacturaForm = lazy(() => import("/src/pages/FacturaForm.jsx"));
const Recibos = lazy(() => import("/src/pages/Recibos.jsx"));
const Recibo = lazy(() => import("/src/pages/Recibo.jsx"));
const ReciboForm = lazy(() => import("/src/pages/ReciboForm.jsx"));
const EstadoCuenta = lazy(() => import("/src/pages/EstadoCuenta.jsx"));
const Anticipos = lazy(() => import("/src/pages/Anticipos.jsx"));
const AnticipoForm = lazy(() => import("/src/pages/AnticipoForm.jsx"));
const EstadoDeudaTotal = lazy(() => import("/src/pages/EstadoDeudaTotal.jsx"));
const AnticiposPendientes = lazy(() => import("/src/pages/AnticiposPendientes.jsx"));
const Configuracion = lazy(() => import("/src/pages/Configuracion.jsx"));
const Compras = lazy(() => import("/src/pages/Compras.jsx"));
const CompraForm = lazy(() => import("/src/pages/CompraForm.jsx"));
const InformeCentros = lazy(() => import("/src/pages/InformeCentros.jsx"));
const InformeResultados = lazy(() => import("/src/pages/InformeResultados.jsx"));
const InformeClavesFiscales = lazy(() => import("/src/pages/InformeClavesFiscales.jsx"));
const InformeCuentaCorriente = lazy(() => import("/src/pages/InformeCuentaCorriente.jsx"));
const LibroIVA = lazy(() => import("/src/pages/LibroIVA.jsx"));
const BalanceRT54 = lazy(() => import("/src/pages/BalanceRT54.jsx"));
const Vencimientos = lazy(() => import("/src/pages/Vencimientos.jsx"));
const PlanCuentas = lazy(() => import("/src/pages/PlanCuentas.jsx"));
const Asientos = lazy(() => import("/src/pages/Asientos.jsx"));
const Mayores = lazy(() => import("/src/pages/Mayores.jsx"));

function ProtectedLayout() {
  const { user, cargando } = useAuth();
  
  if (cargando) {
    return <div className="pantalla-carga">Cargando…</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return <Layout />;
}

export default function App() {
  const { cargando } = useAuth();

  if (cargando) {
    return <div className="pantalla-carga">Cargando…</div>;
  }

  return (
    <Suspense fallback={<div className="pantalla-carga">Cargando…</div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<ProtectedLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="cliente-alta" element={<ClienteForm />} />
        <Route path="cliente-ficha/:id" element={<ClienteFicha />} />
        <Route path="cliente-editar/:id" element={<ClienteForm />} />
        <Route path="servicios" element={<Servicios />} />
        <Route path="facturas" element={<Facturas />} />
        <Route path="factura-alta" element={<FacturaForm />} />
        <Route path="factura-editar/:id" element={<FacturaForm />} />
        <Route path="recibos" element={<Recibos />} />
        <Route path="recibo/:id" element={<Recibo />} />
        <Route path="recibo-alta" element={<ReciboForm />} />
        <Route path="recibo-editar/:id" element={<ReciboForm />} />
        <Route path="anticipos" element={<Anticipos />} />
        <Route path="anticipo-alta" element={<AnticipoForm />} />
        <Route path="anticipo-editar/:id" element={<AnticipoForm />} />
        <Route path="cuenta" element={<EstadoCuenta />} />
        <Route path="estado-deuda" element={<EstadoDeudaTotal />} />
        <Route path="anticipos-pendientes" element={<AnticiposPendientes />} />
        <Route path="proveedores" element={<Clientes tipo="proveedor" />} />
        <Route path="proveedor-alta" element={<ClienteForm tipo="proveedor" />} />
        <Route path="proveedor-ficha/:id" element={<ClienteFicha tipo="proveedor" />} />
        <Route path="proveedor-editar/:id" element={<ClienteForm tipo="proveedor" />} />
        <Route path="configuracion" element={<Configuracion />} />
        <Route path="compras" element={<Compras />} />
        <Route path="compra-alta" element={<CompraForm />} />
        <Route path="compra-editar/:id" element={<CompraForm />} />
        <Route path="informe-centros" element={<InformeCentros />} />
        <Route path="informe-resultados" element={<InformeResultados />} />
        <Route path="informe-claves-fiscales" element={<InformeClavesFiscales />} />
<Route path="informe-cuenta-corriente" element={<InformeCuentaCorriente />} />
<Route path="libro-iva-ventas" element={<LibroIVA />} />
        <Route path="balance-rt54" element={<BalanceRT54 />} />
        <Route path="vencimientos" element={<Vencimientos />} />
        <Route path="plan-cuentas" element={<PlanCuentas />} />
        <Route path="asientos" element={<Asientos />} />
        <Route path="mayores" element={<Mayores />} />
        </Route>
      </Routes>
    </Suspense>
  );
}