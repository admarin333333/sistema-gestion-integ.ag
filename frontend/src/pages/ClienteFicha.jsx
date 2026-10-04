import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import {
  actualizarCliente,
  actualizarProveedor,
  actualizarSugerencia,
  aPayload,
  crearSugerencia,
  eliminarCliente,
  eliminarProveedor,
  eliminarSugerencia,
  obtenerCliente,
  obtenerProveedor,
  listarHistorialClaveFiscal,
} from "../api/clientes.js";
import {
  obtenerCuentaCorriente,
  exportarCuentaCorriente,
} from "../api/cuentaCorriente.js";
import CuentasBancarias from "../components/CuentasBancarias.jsx";
import { NOMBRE_ESTUDIO, fecha, fechaHora, pesos, whatsappLink, formatearTelefono } from "../formato.js";

const hoy = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
};

const PESTANAS = [
  { id: "datos", label: "Datos" },
  { id: "servicios", label: "Servicios", soloCliente: true },
  { id: "facturas", label: "Facturas", fase: 3 },
  { id: "recibos", label: "Recibos", fase: 3 },
  { id: "cuenta", label: "Cuenta corriente" },
  // Las cuentas bancarias van acá y no en "Datos" porque un cliente puede tener
  // varias, y en Datos los campos son uno por dato: ahí no se pueden mostrar
  // cinco CBU. Es su propia solapa, y se lee sola: el CBU completa el banco, la
  // sucursal y el número de cuenta.
  { id: "bancos", label: "Cuentas bancarias" },
  // El balance es de ESTE cliente. Es un módulo aparte (vive en su propia
  // pantalla, porque es largo) pero el acceso se pone acá: el contador que
  // está en la ficha tiene el cliente ya a la vista y es donde lo busca.
  { id: "balance", label: "Balance", soloCliente: true },
  { id: "observaciones", label: "Observaciones" },
  { id: "sugerencias", label: "Sugerencias" },
  { id: "informes", label: "Informes", fase: 5 },
];

export default function ClienteFicha({ tipo = "cliente" }) {
  const { id: clienteId } = useParams();
  const navigate = useNavigate();
  const { user, cargando: authCargando } = useAuth();
  const esAdmin = user?.rol === "admin";
  const esProveedor = tipo === "proveedor";
  // Cada módulo tiene su propio endpoint: los clientes y los proveedores
  // viven en tablas separadas y no se mezclan.
  const obtener = esProveedor ? obtenerProveedor : obtenerCliente;
  const actualizarRegistro = esProveedor ? actualizarProveedor : actualizarCliente;
  const eliminarRegistro = esProveedor ? eliminarProveedor : eliminarCliente;

  const [cliente, setCliente] = useState(null);
  const [error, setError] = useState("");
  const [pestana, setPestana] = useState("datos");
  // Historial de cambios de la clave fiscal de ARCA (vacío = nunca cambió).
  const [historialClave, setHistorialClave] = useState([]);

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
      setCliente(await obtener(clienteId));
      // Si nunca se cargó una clave fiscal, no hay historial que pedir.
      try {
        setHistorialClave(await listarHistorialClaveFiscal(clienteId, esProveedor));
      } catch {
        setHistorialClave([]);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    recargar();
  }, [clienteId, tipo]);

  const guardarObservaciones = async (texto) => {
    setGuardando(true);
    setAviso("");
    try {
      setCliente(await actualizarRegistro(cliente.id, aPayload({ ...cliente, observaciones: texto }, !esProveedor)));
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
      await eliminarRegistro(cliente.id);
      navigate(esProveedor ? "/proveedores" : "/clientes");
    } catch (err) {
      setError(err.message);
    }
  };

  const cargarCuentaCorriente = async (filtros = filtrosCC) => {
    if (!clienteId) return;
    setCcCargando(true);
    setCcError("");
    try {
      setCc(await obtenerCuentaCorriente(clienteId, filtros));
    } catch (e) {
      setCcError(e.message);
    } finally {
      setCcCargando(false);
    }
  };

  const exportarExcelCC = async () => {
    try {
      await exportarCuentaCorriente(clienteId, filtrosCC);
    } catch (e) {
      setError(e.message);
    }
  };

  // La cuenta corriente se pide sola: al abrir la ficha y cada vez que se
  // cambia el cliente (no en cada cambio de filtro, eso lo pide el botón).
  useEffect(() => {
    if (pestana === "cuenta") {
      cargarCuentaCorriente();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId, pestana]);

  const dato = (v) => (v ? <>{v}</> : <span className="vacio">—</span>);

  return (
    <section>
      <div className="cabecera-ficha">
        <div>
          <span className="kicker">Ficha del {cliente?.tipo === "proveedor" ? "proveedor" : "cliente"}</span>
          <h1>{cliente?.nombre_completo}</h1>
          <p className="nota">
            {cliente?.tipo === "proveedor" ? "Proveedor" : "Cliente"} · Cuenta n° {cliente?.nro_cuenta} · alta {fecha(cliente?.fecha_alta)} ·{" "}
            {cliente?.tipo_persona === "juridica" ? "Persona jurídica" : "Persona física"}
          </p>
        </div>
        <div className="form-acciones">
          <button className="btn fantasma btn-sm" onClick={() => navigate(cliente?.tipo === "proveedor" ? "/proveedores" : "/clientes")}>
            ← Volver
          </button>
          <button className="btn btn-sm" onClick={() => navigate(`/${cliente?.tipo || "cliente"}-editar/${clienteId}`)}>
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
        {PESTANAS.filter((p) => !(p.soloCliente && esProveedor)).map((p) => (
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
              <dd>{dato(cliente?.nombre)}</dd>
            </div>
            {cliente?.apellido && (
              <div>
                <dt>Apellido</dt>
                <dd>{dato(cliente.apellido)}</dd>
              </div>
            )}
            <div>
              <dt>CUIT</dt>
              <dd className="mono">
                {dato(cliente?.cuit)}
                {/* El dígito verificador que no cierra avisa, pero no bloquea:
                    el CUIT se puede guardar igual. */}
                {cliente?.cuit_advertencia && (
                  <span className="aviso-cuit" role="status">
                    {cliente.cuit_advertencia}
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>DNI</dt>
              <dd className="mono">{dato(cliente?.dni)}</dd>
            </div>
            <div>
              <dt>Clave fiscal ARCA</dt>
              <dd className="mono">
                {cliente?.clave_fiscal ? (
                  cliente.clave_fiscal
                ) : (
                  <span className="faltante">sin cargar</span>
                )}
              </dd>
            </div>
            {cliente?.clave_fiscal && (
              <>
                <div>
                  <dt>Clave cargada el</dt>
                  <dd className="mono">{fecha(cliente.fecha_carga_clave_fiscal)}</dd>
                </div>
                <div>
                  <dt>Última modificación</dt>
                  <dd className="mono">
                    {fechaHora(cliente.fecha_modif_clave_fiscal)}
                  </dd>
                </div>
              </>
            )}
            <div>
              <dt>Email</dt>
              <dd>{dato(cliente?.email)}</dd>
            </div>
            <div>
              <dt>Teléfono</dt>
              <dd className="mono">{formatearTelefono(cliente?.cod_area, cliente?.telefono)}</dd>
            </div>
            <div>
              <dt>Calle</dt>
              <dd>{dato(cliente?.calle)}</dd>
            </div>
            <div>
              <dt>Número</dt>
              <dd className="mono">{dato(cliente?.numero_calle)}</dd>
            </div>
            <div>
              <dt>Localidad</dt>
              <dd>{dato(cliente?.localidad)}</dd>
            </div>
            <div>
              <dt>Código postal</dt>
              <dd className="mono">{dato(cliente?.codigo_postal)}</dd>
            </div>
            <div>
              <dt>Provincia</dt>
              <dd>{dato(cliente?.provincia)}</dd>
            </div>
            <div>
              <dt>Actividad económica</dt>
              <dd>{dato(cliente?.actividad_economica)}</dd>
            </div>
            <div>
              <dt>Tipo de actividad</dt>
              <dd>{dato(cliente?.tipo_actividad)}</dd>
            </div>
            <div>
              <dt>Condición ante el IVA</dt>
              <dd>{dato(cliente?.condicion_iva?.replace(/_/g, " ").split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" "))}</dd>
            </div>
            {cliente?.alicuota_iva && (
              <div>
                <dt>Alícuota de IVA</dt>
                <dd className="mono">{dato(cliente.alicuota_iva.nombre)}</dd>
              </div>
            )}
            <div>
              <dt>Fecha de cierre de ejercicio</dt>
              <dd className="mono">
                {dato(
                  cliente?.fecha_cierre_ejercicio
                    ? (() => {
                        const d = new Date(
                          cliente.fecha_cierre_ejercicio + "T12:00:00"
                        );
                        const mes = new Intl.DateTimeFormat("es-AR", {
                          month: "long",
                        }).format(d);
                        return `día ${d.getDate()} de ${mes}`;
                      })()
                    : null
                )}
              </dd>
            </div>
          </dl>

          {historialClave.length > 0 && (
            <>
              <h4 className="subtitulo-ficha">
                Cambios de clave fiscal ({historialClave.length})
              </h4>
              <div className="tabla-envoltura">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th className="mono">Clave anterior</th>
                      <th className="mono">Clave nueva</th>
                      <th>Quién</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historialClave.map((h) => (
                      <tr key={h.id}>
                        <td className="mono">{fechaHora(h.fecha_cambio)}</td>
                        <td className="mono">
                          {h.clave_fiscal_anterior || (
                            <span className="vacio">—</span>
                          )}
                        </td>
                        <td className="mono">
                          {h.clave_fiscal_nueva || (
                            <i style={{ fontStyle: "normal" }}>se quitó</i>
                          )}
                        </td>
                        <td>{h.usuario || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {pestana === "servicios" && (
        <div className="panel">
          {cliente?.servicios?.length === 0 ? (
            <p className="lista-vacia">Este cliente no tiene servicios contratados.</p>
          ) : (
            <ul className="fases">
              {cliente?.servicios?.map((s) => (
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

      {/* El balance vive en su propia pantalla (es largo). Acá va el acceso: se
          le pasa el cliente por la URL para que la pantalla lo abra sola y el
          contador no tenga que elegirlo de nuevo en el buscador. */}
      {pestana === "balance" && (
        <div className="panel">
          <p>
            El balance general del cliente (modelo RT54). Cada cliente tiene el
            suyo, con sus ejercicios y sus importes.
          </p>
          <div className="form-acciones">
            <button
              className="btn"
              type="button"
              onClick={() => navigate(`/balance-rt54?cliente=${clienteId}`)}
            >
              Abrir el balance de {cliente?.nombre_completo}
            </button>
          </div>
          <p className="nota">
            El balance del estudio es otra cosa: ese está en Contabilidad →
            Asientos contables y en los mayores generales.
          </p>
        </div>
      )}

      {pestana === "bancos" && (
            <CuentasBancarias
              clienteId={cliente?.id}
              clienteNombre={cliente?.nombre_completo}
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

          {cliente?.sugerencias?.length === 0 ? (
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
                  {cliente?.sugerencias?.map((s) => (
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

  const tel = [cliente?.cod_area, cliente?.telefono].filter(Boolean).join(" ");

  return (
    <div className="panel">
      {/* Cabecera del cliente */}
      <div className="cc-cabecera">
        <div>
          <h3>{cliente?.nombre_completo}</h3>
          <p className="nota">
            {cliente?.tipo_persona === "juridica" ? "Persona jurídica" : "Persona física"} ·
            CUIT: {cliente?.cuit || "—"} · DNI: {cliente?.dni || "—"}
          </p>
        </div>
        <div className="cc-datos">
          <div><b>Condición IVA:</b> {cliente?.tipo_actividad?.replace(/_/g, " ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}</div>
          <div><b>Email:</b> {cliente?.email || "—"}</div>
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
            {cc?.movimientos?.length === 0 ? (
              <tr>
                <td colSpan="5" className="vacio">No hay movimientos en el período seleccionado.</td>
              </tr>
            ) : (
              cc?.movimientos?.map((m) => (
                <tr key={`${m.fecha}-${m.concepto}`}>
                  <td className="mono">{fecha(m.fecha)}</td>
                  <td>{m.concepto}</td>
                  <td className="mono derecha">{m.debe ? pesos(m.debe) : "—"}</td>
                  <td className="mono derecha">{m.haber ? pesos(m.haber) : "—"}</td>
                  <td className="mono derecha"><b>{pesos(m.saldo)}</b></td>
                </tr>
              )))}
          </tbody>
            <tfoot>
              <tr>
                <td colSpan="2"><b>TOTALES</b></td>
                <td className="mono derecha"><b>{pesos(cc?.total_debe)}</b></td>
                <td className="mono derecha"><b>{pesos(cc?.total_haber)}</b></td>
                <td className="mono derecha"><b>{pesos(cc?.saldo)}</b></td>
              </tr>
            </tfoot>
          </table>
        </div>

      <p className="nota">Saldo final a la fecha: <b>{pesos(cc?.saldo)}</b></p>
    </div>
  );
}

function Observaciones({ cliente, onGuardar, guardando }) {
  const [texto, setTexto] = useState(cliente?.observaciones || "");

  useEffect(() => {
    setTexto(cliente?.observaciones || "");
  }, [cliente?.id]);

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