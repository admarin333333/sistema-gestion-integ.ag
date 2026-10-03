import { createContext, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "../api/client.js";

const AuthContext = createContext(null);

/**
 * Lee el rol del JWT en el navegador sin llamar al backend.
 * Es solo para pintar la pantalla de entrada sin esperar /auth/me: el servidor
 * valida el token de verdad en cada llamada a la API (y el /auth/me corre en
 * segundo plano igual, confirmando o rechazando la sesión).
 * Si el token no se puede leer o ya venció, devuelve null (no se confía).
 */
function usuarioDelToken() {
  const token = getToken();
  if (!token) return null;
  try {
    const base = token.split(".")[1];
    if (!base) return null;
    const datos = JSON.parse(atob(base.replace(/-/g, "+").replace(/_/g, "/")));
    if (datos.rol && datos.exp && datos.exp * 1000 > Date.now()) {
      return { nombre: "…", rol: datos.rol, provisional: true };
    }
  } catch {
    /* token ilegible → esperamos /auth/me */
  }
  return null;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(usuarioDelToken);
  // Sin token, o con token legible: no hay nada que esperar para pintar.
  // Solo bloqueamos si hay token pero no se pudo leer del JWT.
  const [cargando, setCargando] = useState(() => !!getToken() && !usuarioDelToken());

  // Validamos el token contra el backend en segundo plano.
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
