import { useEffect, useState } from "react";
import {
  listarCuentas,
  crearCuenta,
  actualizarCuenta,
  darDeBajaCuenta,
  reactivarCuenta,
  listarBancos,
  bancoDesdeCBU,
} from "../api/ctasBancarias.js";

/**
 * SOLAPA "CUENTAS BANCARIAS" de la ficha del cliente.
 *
 * Un cliente puede tener **todas las cuentas que quiera**, así que esto es una
 * lista, no un dato único. Cada fila es una CBU, un CVU o un alias.
 *
 * Lo que hace por el contador:
 *
 * - **El CBU completa solo la sucursal y el número de cuenta.** Los dígitos 9 a 12
 *   son la sucursal y del 13 al 21 la cuenta: no hay que escribirlos.
 * - **El banco se deduce del CBU** (los primeros 8 dígitos) y se crea solo, con
 *   un nombre provisorio. Los códigos de banco no se inventan: salen del CBU que
 *   el contador pega. Después lo puede corregir.
 * - **"Copiar"** pone el CBU (o el CVU, o el alias) en el portapapeles, listo
 *   para pegarlo donde le cobran. Copia UNA sola cosa: si la cuenta tuviera las
 *   tres, el contador no sabría cuál mandar.
 * - **No se borran, se dan de baja.** Una cuenta puede estar usada en un recibo
 *   que ya se emitió; borrarla dejaría ese recibo apuntando a nada. Las dadas de
 *   baja quedan abajo, tachadas, y se pueden volver a habilitar.
 *
 * Todos los errores vienen del backend con el texto que ve el contador
 * ("ese CBU ya está cargado en otra cuenta"), no con un error técnico: las
 * validaciones del CBU viven en el service.
 */
const VACIA = {
  codigo_banco: "",
  cbu: "",
  cvu: "",
  alias_cbu: "",
  cuit_titular: "",
  moneda: "ARS",
  sucursal: "",
  numero_cuenta: "",
};

export default function CuentasBancarias({ clienteId, clienteNombre }) {
  const [cuentas, setCuentas] = useState([]);
  const [bancos, setBancos] = useState([]);
  const [form, setForm] = useState(VACIA);
  const [editando, setEditando] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [verInactivas, setVerInactivas] = useState(false);

  const cargar = async () => {
    if (!clienteId) return;
    try {
      const lista = await listarCuentas(clienteId, verInactivas);
      setCuentas(lista);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    listarBancos().then(setBancos).catch(() => setBancos([]));
    setForm(VACIA);
    setEditando(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId, verInactivas]);

  /** Cuando se pega un CBU, la sucursal y la cuenta se llenan solas. */
  const alPegarCBU = async (cbu) => {
    setForm((f) => ({ ...f, cbu }));
    setError("");
    setAviso("");
    const limpio = (cbu || "").replace(/\D/g, "");
    if (limpio.length !== 22) return;

    try {
      const info = await bancoDesdeCBU(limpio);
      // Los dígitos 9 a 12 son la sucursal, del 13 al 21 la cuenta.
      const cambios = {
        sucursal: limpio.slice(8, 12),
        numero_cuenta: limpio.slice(12, 21),
      };
      if (info.ya_cargado) {
        cambios.codigo_banco = info.codigo;
        setAviso(`${info.nombre} · cuenta ${limpio.slice(12, 21)}`);
      } else {
        // El banco todavía no está en el catálogo: se crea solo al guardar, con
        // un nombre provisorio. Acá solo se avisa.
        cambios.codigo_banco = limpio.slice(0, 8);
        setAviso(
          `Banco ${limpio.slice(0, 8)}: es el primero de este banco, se crea solo. ` +
            `Podés completar el nombre después.`
        );
      }
      setForm((f) => ({ ...f, ...cambios }));
    } catch {
      // El endpoint es solo informativo: si falla, el alta sigue funcionando
      // porque el backend deduce el banco del CBU igual.
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError("");
    setAviso("");
    try {
      if (editando) {
        await actualizarCuenta(editando, form);
      } else {
        await crearCuenta(clienteId, form);
      }
      setForm(VACIA);
      setEditando(null);
      await cargar();
      // El banco puede ser nuevo: hay que recargar la lista para que aparezca.
      listarBancos().then(setBancos).catch(() => {});
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  const baja = async (id) => {
    setError("");
    try {
      await darDeBajaCuenta(id);
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const reactivar = async (id) => {
    setError("");
    try {
      await reactivarCuenta(id);
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const copiar = async (texto) => {
    if (!texto) return;
    try {
      await navigator.clipboard.writeText(texto);
      setAviso(`Copiado: ${texto}`);
    } catch {
      setAviso(`Para copiar a mano: ${texto}`);
    }
  };

  const activas = cuentas.filter((c) => c.activo);
  const inactivas = cuentas.filter((c) => !c.activo);

  return (
    <div className="panel">
      <h3>Cuentas bancarias</h3>
      <p className="nota">
        {clienteNombre ? `De ${clienteNombre}. ` : ""}Un cliente puede tener
        varias. Pegá el CBU y la sucursal, el número de cuenta y el banco se
        completan solos.
      </p>

      {error && <p className="error">{error}</p>}

      {/* ---------------------------------------------------------- formulario */}
      <form className="form-grid" onSubmit={guardar} style={{ marginBottom: "1.5rem" }}>
        <label className="campo">
          <span>Banco</span>
          <select
            value={form.codigo_banco}
            onChange={(e) => setForm({ ...form, codigo_banco: e.target.value })}
          >
            <option value="">Sin banco (CVU o alias)</option>
            {bancos.map((b) => (
              <option key={b.codigo} value={b.codigo}>
                {b.nombre} ({b.codigo})
              </option>
            ))}
          </select>
        </label>

        <label className="campo">
          <span>CBU</span>
          <input
            value={form.cbu}
            onChange={(e) => alPegarCBU(e.target.value)}
            placeholder="2850590940090418135201"
            inputMode="numeric"
            maxLength={22}
            aria-label="CBU"
          />
        </label>

        <label className="campo">
          <span>CVU</span>
          <input
            value={form.cvu}
            onChange={(e) => setForm({ ...form, cvu: e.target.value })}
            placeholder="Solo billetera"
            inputMode="numeric"
            maxLength={22}
            aria-label="CVU"
          />
        </label>

        <label className="campo">
          <span>Alias</span>
          <input
            value={form.alias_cbu}
            onChange={(e) => setForm({ ...form, alias_cbu: e.target.value })}
            placeholder="miestudio.alias"
            aria-label="Alias CBU"
          />
        </label>

        <label className="campo">
          <span>Sucursal</span>
          <input
            value={form.sucursal}
            onChange={(e) => setForm({ ...form, sucursal: e.target.value })}
            placeholder="Se completa sola"
            aria-label="Sucursal"
          />
        </label>

        <label className="campo">
          <span>N.° de cuenta</span>
          <input
            value={form.numero_cuenta}
            onChange={(e) => setForm({ ...form, numero_cuenta: e.target.value })}
            placeholder="Se completa solo"
            aria-label="Número de cuenta"
          />
        </label>

        <label className="campo">
          <span>CUIT del titular</span>
          <input
            value={form.cuit_titular}
            onChange={(e) => setForm({ ...form, cuit_titular: e.target.value })}
            placeholder="20-26473675-8"
            aria-label="CUIT del titular"
          />
        </label>

        <label className="campo">
          <span>Moneda</span>
          <select
            value={form.moneda}
            onChange={(e) => setForm({ ...form, moneda: e.target.value })}
          >
            <option value="ARS">Pesos</option>
            <option value="USD">Dólares</option>
          </select>
        </label>

        <div className="campo" style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem" }}>
          <button className="btn btn-sm" type="submit" disabled={guardando}>
            {editando ? "Guardar cambios" : "+ Agregar cuenta"}
          </button>
          {editando && (
            <button
              className="btn btn-sm fantasma"
              type="button"
              onClick={() => {
                setEditando(null);
                setForm(VACIA);
              }}
            >
              Cancelar
            </button>
          )}
        </div>
      </form>

      {aviso && <p className="nota">{aviso}</p>}

      {/* ---------------------------------------------------------- listado */}
      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && cuentas.length === 0 && (
        <p className="nota">
          Este cliente no tiene ninguna cuenta cargada.
        </p>
      )}

      {!cargando && activas.length > 0 && (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead>
              <tr>
                <th>Banco</th>
                <th>Tipo</th>
                <th>CBU / CVU / Alias</th>
                <th>Sucursal</th>
                <th>N.° cuenta</th>
                <th>CUIT titular</th>
                <th>Moneda</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {activas.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.nombre_banco}
                    {c.nombre_banco === "Sin banco (billetera o alias)" && (
                      <small className="nota"> · {c.codigo_banco}</small>
                    )}
                  </td>
                  <td>{c.tipo}</td>
                  <td className="mono">
                    {c.para_cobrar ? (
                      <button
                        className="btn btn-sm fantasma mono"
                        onClick={() => copiar(c.para_cobrar)}
                        title="Copiar al portapapeles"
                      >
                        {c.para_cobrar}
                      </button>
                    ) : (
                      <span className="vacio">—</span>
                    )}
                  </td>
                  <td className="mono">{c.sucursal || "—"}</td>
                  <td className="mono">{c.numero_cuenta || "—"}</td>
                  <td className="mono">{c.cuit_titular || "—"}</td>
                  <td>{c.moneda}</td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => {
                        setEditando(c.id);
                        setForm({
                          codigo_banco: c.codigo_banco === "00000000" ? "" : c.codigo_banco,
                          cbu: c.cbu || "",
                          cvu: c.cvu || "",
                          alias_cbu: c.alias_cbu || "",
                          cuit_titular: c.cuit_titular || "",
                          moneda: c.moneda,
                          sucursal: c.sucursal || "",
                          numero_cuenta: c.numero_cuenta || "",
                        });
                      }}
                      title="Modificar"
                    >
                      Editar
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => baja(c.id)}
                      title="Dar de baja (no se borra: puede estar usada en un recibo)"
                    >
                      Dar de baja
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {inactivas.length > 0 && (
        <>
          <p className="nota" style={{ marginTop: "1rem" }}>
            <label style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={verInactivas}
                onChange={(e) => setVerInactivas(e.target.checked)}
              />
              Ver las {inactivas.length} dada(s) de baja
            </label>
          </p>
          {verInactivas && (
            <div className="tabla-envoltura">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Banco</th>
                    <th>Tipo</th>
                    <th>CBU / CVU / Alias</th>
                    <th>Moneda</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {inactivas.map((c) => (
                    <tr key={c.id} className="fila-vencida">
                      <td>{c.nombre_banco}</td>
                      <td>{c.tipo}</td>
                      <td className="mono">{c.para_cobrar || "—"}</td>
                      <td>{c.moneda}</td>
                      <td className="acciones">
                        <button
                          className="btn btn-sm fantasma"
                          onClick={() => reactivar(c.id)}
                          title="Volver a habilitar"
                        >
                          Reactivar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}