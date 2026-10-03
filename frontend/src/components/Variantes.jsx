import { useEffect, useState } from "react";
import {
  listarVariantes,
  guardarVariante,
  eliminarVariante,
} from "../api/variantes.js";

/**
 * Variantes de selección (idea SAP): guarda los filtros de la pantalla con un
 * nombre. Al elegir una del selector se cargan y (si se pasa onCargar) se
 * aplica la búsqueda. Privadas por defecto; "Compartir" las hace visibles
 * para el equipo.
 */
export default function Variantes({ pantalla, filtros, setFiltros, onCargar }) {
  const [lista, setLista] = useState([]);
  const [seleccion, setSeleccion] = useState("");
  const [nombre, setNombre] = useState("");
  const [compartida, setCompartida] = useState(false);
  const [error, setError] = useState("");

  const cargar = async () => {
    try {
      setLista(await listarVariantes(pantalla));
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    setSeleccion("");
    setNombre("");
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pantalla]);

  const elegir = (e) => {
    const id = e.target.value;
    setSeleccion(id);
    const v = lista.find((x) => String(x.id) === id);
    if (!v) return;
    const nuevos = { ...filtros, ...v.filtros };
    setFiltros(nuevos);
    setNombre(v.nombre);
    setCompartida(v.compartida);
    setError("");
    if (onCargar) onCargar(nuevos);
  };

  const guardar = async () => {
    if (!nombre.trim()) {
      setError("Poné un nombre para la variante");
      return;
    }
    try {
      const creada = await guardarVariante({
        pantalla,
        nombre: nombre.trim(),
        filtros,
        compartida,
      });
      setError("");
      await cargar();
      setSeleccion(String(creada.id));
    } catch (e) {
      setError(e.message);
    }
  };

  const borrar = () => {
    const v = lista.find((x) => String(x.id) === seleccion);
    if (!v) return;
    if (window.confirm(`¿Borrar la variante "${v.nombre}"?`)) {
      eliminarVariante(v.id)
        .then(() => {
          setSeleccion("");
          setNombre("");
          return cargar();
        })
        .catch((e) => setError(e.message));
    }
  };

  return (
    <div className="buscador">
      <label className="campo" style={{ flex: "2 1 200px" }}>
        <span>Variantes guardadas</span>
        <select value={seleccion} onChange={elegir} aria-label="Variantes">
          <option value="">Elegí una variante…</option>
          {lista.map((v) => (
            <option key={v.id} value={v.id}>
              {v.nombre}
              {v.es_mia ? (v.compartida ? " 🔗" : "") : " (compartida)"}
            </option>
          ))}
        </select>
      </label>

      <label className="campo" style={{ flex: "2 1 200px" }}>
        <span>Nombre (para guardar)</span>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          maxLength={60}
          placeholder="Ej: Septiembre 2026"
        />
      </label>

      <label className="campo" style={{ flex: "0 0 auto" }}>
        <span>Compartir</span>
        <input
          type="checkbox"
          checked={compartida}
          onChange={(e) => setCompartida(e.target.checked)}
          style={{ width: "auto" }}
        />
      </label>

      <button className="btn btn-sm" type="button" onClick={guardar}>
        Guardar variante
      </button>
      {seleccion && (
        <button className="btn btn-sm peligro" type="button" onClick={borrar}>
          Borrar
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
