const TOKEN_KEY = "gc_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

/** Todas las llamadas a la API pasan por acá (usa proxy de Vite: /api -> 127.0.0.1:8010). */
export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    window.location.assign("/");
    throw new Error("Sesión expirada");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Error inesperado");
  return data;
}

/**
 * Descarga un archivo (Excel o PDF) con el token y lo guarda en el equipo.
 * Devuelve el nombre que eligió el servidor.
 */
export async function descargar(path) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { headers });

  // Si falla, recién ahí leemos el cuerpo para sacar el mensaje de error.
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error((data && data.detail) || "No se pudo descargar");
  }

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = /filename="([^"]+)"/.exec(cd);

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = m ? m[1] : path.split("/").pop();
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return a.download;
}
