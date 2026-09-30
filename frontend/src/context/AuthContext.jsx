import { createContext, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [cargando, setCargando] = useState(true);

  // Si ya había token guardado, recuperamos el usuario.
  useEffect(() => {
    if (!getToken()) {
      setCargando(false);
      return;
    }
    api("/auth/me")
      .then(setUser)
      .catch(() => {
        // Token inválido/expirado → limpiamos y redirigimos a login
        clearToken();
        setUser(null);
      })
      .finally(() => setCargando(false));
  }, []);

  async function login(usuario, password) {
    // Limpiamos cualquier token anterior ANTES de loguear
    clearToken();
    const { access_token } = await api("/auth/login", {
      method: "POST",
      body: { usuario, password },
    });
    setToken(access_token);
    setUser(await api("/auth/me"));
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, cargando, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
