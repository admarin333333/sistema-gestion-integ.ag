import { createHotContext as __vite__createHotContext } from "/@vite/client";
import.meta.hot = __vite__createHotContext("/src/App.jsx");
import __vite__cjsImport0_react_jsxDevRuntime from "/node_modules/.vite/deps/react_jsx-dev-runtime.js?v=3844b28a"; const jsxDEV = __vite__cjsImport0_react_jsxDevRuntime["jsxDEV"];
import * as RefreshRuntime from "/@react-refresh";
const inWebWorker = typeof WorkerGlobalScope !== "undefined" && self instanceof WorkerGlobalScope;
let prevRefreshReg;
let prevRefreshSig;
if (import.meta.hot && !inWebWorker) {
  if (!window.$RefreshReg$) {
    throw new Error(
      "@vitejs/plugin-react can't detect preamble. Something is wrong."
    );
  }
  prevRefreshReg = window.$RefreshReg$;
  prevRefreshSig = window.$RefreshSig$;
  window.$RefreshReg$ = RefreshRuntime.getRefreshReg("C:/proyecto-gestion-contable/frontend/src/App.jsx");
  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;
}
var _s = $RefreshSig$();
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useAuth } from "/src/context/AuthContext.jsx";
import Layout from "/src/components/Layout.jsx";
import Login from "/src/pages/Login.jsx";
import Dashboard from "/src/pages/Dashboard.jsx";
import Clientes from "/src/pages/Clientes.jsx";
import ClienteForm from "/src/pages/ClienteForm.jsx";
import ClienteFicha from "/src/pages/ClienteFicha.jsx";
import Facturas from "/src/pages/Facturas.jsx";
import FacturaForm from "/src/pages/FacturaForm.jsx";
import Recibos from "/src/pages/Recibos.jsx";
import ReciboForm from "/src/pages/ReciboForm.jsx";
import EstadoCuenta from "/src/pages/EstadoCuenta.jsx";
import Anticipos from "/src/pages/Anticipos.jsx";
import AnticipoForm from "/src/pages/AnticipoForm.jsx";
import EstadoDeudaTotal from "/src/pages/EstadoDeudaTotal.jsx";
import AnticiposPendientes from "/src/pages/AnticiposPendientes.jsx";
import EstadoDeudaTotal from "/src/pages/EstadoDeudaTotal.jsx";
import AnticiposPendientes from "/src/pages/AnticiposPendientes.jsx";

export default function App() {
  const { user, cargando } = useAuth();

  if (cargando) return (
    <div className="pantalla-carga">Cargando…</div>
  );

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <>
              {user ? <Layout /> : <Navigate to="/login" replace />}
            </>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="cliente-alta" element={<ClienteForm />} />
          <Route path="cliente-ficha/:id" element={<ClienteFicha />} />
          <Route path="cliente-editar/:id" element={<ClienteForm />} />
          <Route path="facturas" element={<Facturas />} />
          <Route path="factura-alta" element={<FacturaForm />} />
          <Route path="factura-editar/:id" element={<FacturaForm />} />
          <Route path="recibos" element={<Recibos />} />
          <Route path="recibo-alta" element={<ReciboForm />} />
          <Route path="recibo-editar/:id" element={<ReciboForm />} />
          <Route path="anticipos" element={<Anticipos />} />
          <Route path="anticipo-alta" element={<AnticipoForm />} />
          <Route path="anticipo-editar/:id" element={<AnticipoForm />} />
          <Route path="cuenta" element={<EstadoCuenta />} />
          <Route path="estado-deuda" element={<EstadoDeudaTotal />} />
          <Route path="anticipos-pendientes" element={<AnticiposPendientes />} />
        </Routes>
      </BrowserRouter>
    );
  }
}

export default App;