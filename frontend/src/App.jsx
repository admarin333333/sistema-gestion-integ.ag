import { useAuth } from "./context/AuthContext.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";

export default function App() {
  const { user, cargando } = useAuth();

  if (cargando) return <div className="pantalla-carga">Cargando…</div>;
  return user ? <Layout /> : <Login />;
}
