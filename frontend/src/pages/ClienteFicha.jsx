import { useEffect, useState } from "react";
import {
  actualizarCliente,
  actualizarSugerencia,
  aPayload,
  crearSugerencia,
  eliminarCliente,
  eliminarSugerencia,
  obtenerCliente,
} from "../api/clientes.js";

const hoy = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
};

const fecha = (f) => (f ? f.split("-").reverse().join("/") : "—");

const PESTANAS = [
  { id: "datos", label: "Datos" },
  { id: "servicios", label: "Servicios" },
  { id: "facturas", label: "Facturas", fase: 3 },
  { id: "recibos", label: "Recibos", fase: 3 },
  { id: "cuenta", label: "Cuenta corriente", fase: 3 },
  { id: "observaciones", label: "Observaciones" },
  { id: "sugerencias", label: "Sugerencias" },
  { id: "informes", label: "Informes", fase: 5 },
];

export default function ClienteFicha({ clienteId, esAdmin, onVolver, onEditar }) {
  const [cliente, setCliente] = useState(null);
  const [error, setError] = useState("");
  const [pestana, setPestana] = useState("datos");

  // sugerencias
  const [nueva, setNueva] = useState({ fecha: hoy(), descripcion: "" });
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState("");

  const recargar = async () => {
    try {
      setCliente(await obtenerCliente(clienteId));
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    recargar();
  }, [clienteId]);

  if (error) return <p className="error">{error}</p>;
  if (!cliente) return <p className="nota">Cargando ficha…</p>;

  const guardarObservaciones = async (texto) => {
    setGuardando(true);
    setAviso("");
    try {
      setCliente(await actualizarCliente(cliente.id, aPayload({ ...cliente, observaciones: texto })));
      setAviso("Observaciones guardadas ✅");
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  const altaSugerencia = async (e) => {
    e.preventDefault();
    if (!nueva.descripcion.trim()) return;
    setGuardando(true);
    setAviso("");
    try {
      await crearSugerencia(cliente.id, {
        fecha: nueva.fecha,
        descripcion: nueva.descripcion.trim(),
        estado: "pendiente",
      });
      setNueva({ fecha: hoy(), descripcion: "" });
      await recargar();
      setAviso("Sugerencia agregada ✅");
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  const cambiarEstado = async (s) => {
    try {
      await actualizarSugerencia(s.id, {
        fecha: s.fecha,
        descripcion: s.descripcion,
        estado: s.estado === "pendiente" ? "atendida" : "pendiente",
      });
      await recargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const borrarSugerencia = async (s) => {
    if (!confirm(`¿Borrar la sugerencia del ${fecha(s.fecha)}?`)) return;
    try {
      await eliminarSugerencia(s.id);
      await recargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const borrarCliente = async () => {
    if (!confirm(`¿Eliminar a ${cliente.nombre_completo}? Esta acción no se puede deshacer.`))
      return;
    try {
      await eliminarCliente(cliente.id);
      onVolver();
    } catch (err) {
      setError(err.message);
    }
  };

  const dato = (v) => (v ? <>{v}</> : <span className="vacio">—</span>);

  return (
    <section>
      <div className="cabecera-ficha">
        <div>
          <span className="kicker">Ficha del cliente</span>
          <h1>{cliente.nombre_completo}</h1>
          <p className="nota">
            Cuenta n° {cliente.id} · alta {fecha(cliente.fecha_alta)} ·{" "}
            {cliente.tipo_persona === "juridica" ? "Persona jurídica" : "Persona física"}
          </p>
        </div>
        <div className="form-acciones">
          <button className="btn fantasma btn-sm" onClick={onVolver}>
            ← Volver
          </button>
          <button className="btn btn-sm" onClick={onEditar}>
            Editar
          </button>
          {esAdmin && (
            <button className="btn peligro btn-sm" onClick={borrarCliente}>
              Eliminar
            </button>
          )}
        </div>
      </div>

      <div className="pestanas">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            className={pestana === p.id ? "pestana activa" : "pestana"}
            disabled={Boolean(p.fase)}
            onClick={() => setPestana(p.id)}
            title={p.fase ? `Disponible en la Fase ${p.fase}` : ""}
          >
            {p.label}
            {p.fase && <i>F{p.fase}</i>}
          </button>
        ))}
      </div>

      {aviso && <p className="nota">{aviso}</p>}

      {pestana === "datos" && (
        <div className="panel">
          <dl className="detalle">
            <div>
              <dt>Nombre / Razón social</dt>
              <dd>{dato(cliente.nombre)}</dd>
            </div>
            {cliente.apellido && (
              <div>
                <dt>Apellido</dt>
                <dd>{dato(cliente.apellido)}</dd>
              </div>
            )}
            <div>
              <dt>CUIT</dt>
              <dd className="mono">{dato(cliente.cuit)}</dd>
            </div>
            <div>
              <dt>DNI</dt>
              <dd className="mono">{dato(cliente.dni)}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{dato(cliente.email)}</dd>
            </div>
            <div>
              <dt>Teléfono</dt>
              <dd className="mono">
                {dato(
                  [cliente.cod_area, cliente.telefono].filter(Boolean).join(" ")
                )}
              </dd>
            </div>
            <div>
              <dt>Domicilio</dt>
              <dd>{dato(cliente.domicilio)}</dd>
            </div>
            <div>
              <dt>Localidad</dt>
              <dd>{dato(cliente.localidad)}</dd>
            </div>
            <div>
              <dt>Código postal</dt>
              <dd className="mono">{dato(cliente.codigo_postal)}</dd>
            </div>
            <div>
              <dt>Provincia</dt>
              <dd>{dato(cliente.provincia)}</dd>
            </div>
            <div>
              <dt>Actividad económica</dt>
              <dd>{dato(cliente.actividad_economica)}</dd>
            </div>
            <div>
              <dt>Tipo de actividad</dt>
              <dd>{dato(cliente.tipo_actividad)}</dd>
            </div>
          </dl>
        </div>
      )}

      {pestana === "servicios" && (
        <div className="panel">
          {cliente.servicios.length === 0 ? (
            <p className="lista-vacia">Este cliente no tiene servicios contratados.</p>
          ) : (
            <ul className="fases">
              {cliente.servicios.map((s) => (
                <li key={s.id} className="ok">
                  <b>S{s.orden}</b> {s.nombre}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {pestana === "observaciones" && (
        <Observaciones cliente={cliente} onGuardar={guardarObservaciones} guardando={guardando} />
      )}

      {pestana === "sugerencias" && (
        <div className="panel">
          <h3>Sugerencias del estudio</h3>

          <form className="buscador" onSubmit={altaSugerencia}>
            <input
              type="date"
              value={nueva.fecha}
              onChange={(e) => setNueva({ ...nueva, fecha: e.target.value })}
              aria-label="Fecha de la sugerencia"
            />
            <input
              value={nueva.descripcion}
              onChange={(e) => setNueva({ ...nueva, descripcion: e.target.value })}
              placeholder="Ej: Buscar asesor legal…"
              aria-label="Descripción"
              style={{ flex: "2 1 320px" }}
            />
            <button className="btn btn-sm" type="submit" disabled={guardando}>
              + Agregar
            </button>
          </form>

          {cliente.sugerencias.length === 0 ? (
            <p className="lista-vacia">Todavía no hay sugerencias para este cliente.</p>
          ) : (
            <div className="tabla-envoltura">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Sugerencia</th>
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {cliente.sugerencias.map((s) => (
                    <tr key={s.id}>
                      <td className="mono">{fecha(s.fecha)}</td>
                      <td>{s.descripcion}</td>
                      <td>
                        <span className={`chip ${s.estado}`}>{s.estado}</span>
                      </td>
                      <td className="acciones">
                        <button
                          className="btn btn-sm fantasma"
                          onClick={() => cambiarEstado(s)}
                        >
                          {s.estado === "pendiente" ? "Marcar hecha" : "Reabrir"}
                        </button>
                        {esAdmin && (
                          <button
                            className="btn peligro btn-sm"
                            onClick={() => borrarSugerencia(s)}
                          >
                            Borrar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {PESTANAS.filter((p) => p.id === pestana && p.fase).map((p) => (
        <div className="panel" key={p.id}>
          <p className="lista-vacia">
            «{p.label}» se habilita en la <b>Fase {p.fase}</b>.
          </p>
        </div>
      ))}
    </section>
  );
}

function Observaciones({ cliente, onGuardar, guardando }) {
  const [texto, setTexto] = useState(cliente.observaciones || "");

  useEffect(() => {
    setTexto(cliente.observaciones || "");
  }, [cliente.id]);

  return (
    <div className="panel">
      <h3>Observaciones — un solo texto</h3>
      <label className="campo">
        <span>Descripción del servicio que solicita el cliente</span>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Escribí acá… se sobreescribe cada vez que guardás."
        />
      </label>
      <div className="form-acciones" style={{ marginTop: "1rem" }}>
        <button
          className="btn btn-sm"
          disabled={guardando}
          onClick={() => onGuardar(texto)}
        >
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        <button className="btn fantasma btn-sm" onClick={() => setTexto("")}>
          Limpiar
        </button>
      </div>
    </div>
  );
}
