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
import {
  obtenerCuentaCorriente,
  exportarCuentaCorriente,
} from "../api/cuentaCorriente.js";
import { NOMBRE_ESTUDIO, fecha, pesos, whatsappLink, formatearTelefono } from "../formato.js";

const hoy = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
};

const PESTANAS = [
  { id: "datos", label: "Datos" },
  { id: "servicios", label: "Servicios" },
  { id: "facturas", label: "Facturas", fase: 3 },
  { id: "recibos", label: "Recibos", fase: 3 },
  { id: "cuenta", label: "Cuenta corriente" },
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

  // cuenta corriente
  const [cc, setCc] = useState(null);
  const [ccCargando, setCcCargando] = useState(false);
  const [ccError, setCcError] = useState("");
  const [filtrosCC, setFiltrosCC] = useState({ desde: "", hasta: "" });

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

  const cargarCuentaCorriente = async () => {
    setCcCargando(true);
    setCcError("");
    try {
      const data = await obtenerCuentaCorriente(clienteId, filtrosCC);
      setCc(data);
    } catch (e) {
      setCcError(e.message);
    } finally {
      setCcCargando(false);
    }
  };

  useEffect(() => {
    if (pestana === "cuenta") {
      cargarCuentaCorriente();
    }
  }, [pestana, filtrosCC]);

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

  const exportarExcelCC = async () => {
    try {
      await exportarCuentaCorriente(clienteId, filtrosCC);
    } catch (e) {
      setError(e.message);
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
          {(cliente.cod_area || cliente.telefono) && (
            <a
              className="btn btn-sm"
              href={whatsappLink(cliente.cod_area, cliente.telefono)}
              target="_blank"
              rel="noopener noreferrer"
              title={`Enviar WhatsApp a ${formatearTelefono(cliente.cod_area, cliente.telefono)}`}
            >
              WhatsApp
            </a>
          )}
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
              <dd className="mono">{formatearTelefono(cliente.cod_area, cliente.telefono)}</dd>
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

      {pestana === "cuenta" && (
        <CuentaCorrienteTab
          cliente={cliente}
          cc={cc}
          cargando={ccCargando}
          error={ccError}
          filtros={filtrosCC}
          onFiltrosChange={setFiltrosCC}
          onRecargar={cargarCuentaCorriente}
          onExportar={exportarExcelCC}
        />
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

function CuentaCorrienteTab({
  cliente,
  cc,
  cargando,
  error,
  filtros,
  onFiltrosChange,
  onRecargar,
  onExportar,
}) {
  const cambiarFiltro = (k) => (e) =>
    onFiltrosChange({ ...filtros, [k]: e.target.value });

  const limpiarFiltros = () => {
    onFiltrosChange({ desde: "", hasta: "" });
  };

  if (cargando) return <p className="nota">Cargando estado de cuenta…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!cc) return <p className="nota">Sin datos</p>;

  const tel = [cliente.cod_area, cliente.telefono].filter(Boolean).join(" ");

  return (
    <div className="panel">
      {/* Cabecera del cliente */}
      <div className="cc-cabecera">
        <div>
          <h3>{cliente.nombre_completo}</h3>
          <p className="nota">
            {cliente.tipo_persona === "juridica" ? "Persona jurídica" : "Persona física"} ·
            CUIT: {cliente.cuit || "—"} · DNI: {cliente.dni || "—"}
          </p>
        </div>
        <div className="cc-datos">
          <div><b>Condición IVA:</b> {cliente.tipo_actividad.replace(/_/g, " ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}</div>
          <div><b>Email:</b> {cliente.email || "—"}</div>
          <div><b>Teléfono:</b> {tel || "—"}</div>
        </div>
      </div>

      {/* Filtros */}
      <form className="buscador" onSubmit={(e) => { e.preventDefault(); onRecargar(); }}>
        <label className="campo">
          <span>Desde</span>
          <input type="date" value={filtros.desde} onChange={cambiarFiltro("desde")} />
        </label>
        <label className="campo">
          <span>Hasta</span>
          <input type="date" value={filtros.hasta} onChange={cambiarFiltro("hasta")} />
        </label>
        <button className="btn btn-sm" type="submit">Filtrar</button>
        <button className="btn btn-sm fantasma" type="button" onClick={limpiarFiltros}>Limpiar</button>
        <button className="btn btn-sm" type="button" onClick={onExportar}>Descargar Excel</button>
        <button className="btn btn-sm fantasma" type="button" onClick={() => window.print()}>Imprimir</button>
      </form>

      {/* Tabla movimientos */}
      <div className="tabla-envoltura">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Concepto</th>
              <th className="derecha">DEBE</th>
              <th className="derecha">HABER</th>
              <th className="derecha">SALDO</th>
            </tr>
          </thead>
          <tbody>
            {cc.movimientos.length === 0 ? (
              <tr>
                <td colSpan="5" className="vacio">No hay movimientos en el período seleccionado.</td>
              </tr>
            ) : (
              cc.movimientos.map((m) => (
                <tr key={`${m.fecha}-${m.concepto}`}>
                  <td className="mono">{fecha(m.fecha)}</td>
                  <td>{m.concepto}</td>
                  <td className="mono derecha">{m.debe ? pesos(m.debe) : "—"}</td>
                  <td className="mono derecha">{m.haber ? pesos(m.haber) : "—"}</td>
                  <td className="mono derecha"><b>{pesos(m.saldo)}</b></td>
                </tr>
              ))
            )}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan="2"><b>TOTALES</b></td>
              <td className="mono derecha"><b>{pesos(cc.total_debe)}</b></td>
              <td className="mono derecha"><b>{pesos(cc.total_haber)}</b></td>
              <td className="mono derecha"><b>{pesos(cc.saldo)}</b></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="nota">Saldo final a la fecha: <b>{pesos(cc.saldo)}</b></p>

      <style jsx>{`
        .cc-cabecera {
          display: flex;
          flex-wrap: wrap;
          gap: 2rem;
          margin-bottom: 1rem;
          padding-bottom: 1rem;
          border-bottom: 1px solid var(--line);
        }
        .cc-cabecera h3 { margin: 0 0 0.3rem; }
        .cc-datos { display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 0.85rem; color: var(--muted); }
        .cc-datos b { color: var(--text); }
        @media print {
          .buscador { display: none !important; }
        }
      `}</style>
    </div>
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