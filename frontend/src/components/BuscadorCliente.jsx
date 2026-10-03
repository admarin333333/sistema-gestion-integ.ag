import { useRef, useState } from "react";

/**
 * Buscador de cliente con desplegable: filtro local (sin pedidos al servidor)
 * por apellido y nombre o razón social + CUIT/DNI, donde todas las palabras
 * escritas deben coincidir ("norte srl" encuentra a Distribuidora Norte SRL).
 *
 * - `seleccion`: cliente elegido (o null) — se muestra su nombre en el campo.
 * - `onElegir(cliente)`: al elegir una opción; `onElegir(null)` si el usuario
 *   empieza a escribir de nuevo (limpia la selección).
 * - `tipo_registro`: "cliente" o "proveedor" para filtrar solo ese módulo.
 *   Si no se especifica, muestra todos (compatibilidad hacia atrás).
 */
export default function BuscadorCliente({
  clientes,
  seleccion,
  onElegir,
  etiqueta = "Cliente",
  placeholder = "Apellido y nombre o razón social…",
  tipo_registro,
  // Para los formularios donde el cliente ya no se puede cambiar (editar un
  // anticipo): el campo se ve pero no se escribe. El `<select>` que había antes
  // se deshabilitaba con `disabled`, así que se conserva ese comportamiento.
  disabled = false,
}) {
  const [busqueda, setBusqueda] = useState("");
  const [abierto, setAbierto] = useState(false);
  const inputRef = useRef(null);

  const texto = busqueda.trim().toLowerCase();
  const palabras = texto ? texto.split(/\s+/) : [];

  /**
   * Saca tildes y pasa a minúscula.
   *
   * Sin esto, escribir "Perez" no encontraba a "Pérez", y eso es lo que escribe
   * cualquiera en un teclado: la tilde es una molestia y el contador la saltea.
   * La búsqueda tiene que perdonar la tilde, como perdona los guiones del CUIT.
   *
   * Se hace con `NFD`, que parte "é" en "e" + acento, y se tira lo que queda
   * arriba: los diacríticos (`\u0300-\u036f`).
   */
  const normalizar = (s) =>
    (s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");

  // Filtrar por tipo de registro si viene informado
  const clientesFiltrados = tipo_registro
    ? clientes.filter((c) => c.tipo === tipo_registro)
    : clientes;
  const filtrados = texto
    ? clientesFiltrados.filter((c) => {
        const juntos = normalizar(
          `${c.nombre_completo || ""} ${c.cuit || ""} ${c.dni || ""}`
        );
        return palabras.every((p) => juntos.includes(normalizar(p)));
      })
    : [];
  const coincidencias = filtrados.slice(0, 10);

  const alEscribir = (e) => {
    if (disabled) return;
    setBusqueda(e.target.value);
    setAbierto(true);
    if (seleccion) onElegir(null); // escribir de nuevo limpia la selección
  };

  const elegir = (c) => {
    if (disabled) return;
    setBusqueda("");
    setAbierto(false);
    onElegir(c);
    // El campo queda con el nombre elegido y todo seleccionado: la próxima
    // tecla arranca una búsqueda nueva (si no, se pegaba al nombre).
    requestAnimationFrame(() => inputRef.current?.select());
  };

  return (
    <label className="campo cliente-buscador">
      <span>{etiqueta}</span>
      <input
        ref={inputRef}
        type="text"
        aria-label={etiqueta}
        placeholder={placeholder}
        autoComplete="off"
        disabled={disabled}
        value={seleccion ? seleccion.nombre_completo : busqueda}
        onChange={alEscribir}
        onFocus={(e) => e.target.select()}
        onBlur={() => setAbierto(false)}
      />
      {abierto && texto && !disabled && (
        <ul className="opciones">
          {coincidencias.length === 0 ? (
            <li className="vacio">Sin coincidencias para «{busqueda.trim()}»</li>
          ) : (
            <>
              {coincidencias.map((c) => (
                <li
                  key={c.id}
                  onMouseDown={(e) => {
                    e.preventDefault(); // evita el blur antes del clic
                    elegir(c);
                  }}
                >
                  <span>{c.nombre_completo}</span>
                  <small>
                    {c.cuit ? `CUIT ${c.cuit}` : c.dni ? `DNI ${c.dni}` : ""}
                  </small>
                </li>
              ))}
              {filtrados.length > coincidencias.length && (
                <li className="vacio">
                  Mostrando 10 de {filtrados.length} — seguí escribiendo
                </li>
              )}
            </>
          )}
        </ul>
      )}
    </label>
  );
}
