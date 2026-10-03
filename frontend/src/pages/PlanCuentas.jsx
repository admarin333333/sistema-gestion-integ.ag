import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  apagarPlanCuenta,
  crearPlanCuenta,
  editarPlanCuenta,
  listarPlanCuentas,
} from "../api/planCuentas.js";
import { NOMBRE_ESTUDIO } from "../formato.js";

const TIPOS_AUXILIAR = ["NINGUNO", "CLIENTE", "PROVEEDOR", "BANCO"];

/**
 * El plan de cuentas en árbol.
 *
 * Cosas que hay que tener en cuenta al tocar esto:
 * - El **código no se edita nunca**: es lo que van a usar los asientos.
 * - Un **agrupador** (el que tiene subcuentas) no puede ser imputable, y el
 *   backend lo rechaza si se intenta. Acá el botón sale deshabilitado.
 * - Una cuenta **no se borra, se apaga**: así los asientos viejos siguen
 *   apuntando a algo real.
 */
export default function PlanCuentas() {
  const { user } = useAuth();
  const esAdmin = user.rol === "admin";

  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  const [buscar, setBuscar] = useState("");
  const [verApagadas, setVerApagadas] = useState(false);
  const [abiertos, setAbiertos] = useState([]);   // códigos abiertos
  const [editando, setEditando] = useState(null);  // id en edición
  const [agregando, setAgregando] = useState(null); // id del padre
  const [soloImputables, setSoloImputables] = useState(false);

  const cargar = async () => {
    setCargando(true);
    setError("");
    try {
      setLista(await listarPlanCuentas({ todas: verApagadas }));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verApagadas]);

  // ---- armar el árbol en memoria --------------------------------------
  // El backend manda la lista plana ordenada por código (que ya viene en
  // orden de árbol) con `codigo_padre`. Acá se cuelga cada una de su padre.
  const { raices, hijasDe, visibles, filtradas } = useMemo(() => {
    const porCodigo = new Map();
    const porId = new Map();
    lista.forEach((c) => {
      porId.set(c.id_cuenta, c);
      porCodigo.set(c.codigo, c);
    });

    const hijas = new Map();
    const raices = [];
    for (const c of lista) {
      const padre = c.codigo_padre ? porCodigo.get(c.codigo_padre) : null;
      if (padre) {
        if (!hijas.has(padre.id_cuenta)) hijas.set(padre.id_cuenta, []);
        hijas.get(padre.id_cuenta).push(c);
      } else {
        raices.push(c);
      }
    }

    // El buscador y el filtro de imputables. Si está filtrando, se muestra
    // la cuenta que coincide aunque su padre esté collapsing: si no, no se
    // vería nada y el buscador parecería roto.
    const texto = buscar.trim().toLowerCase();
    let cuantos = 0;
    const filtradas = new Set();
    if (texto || soloImputables) {
      const califica = (c) => {
        if (soloImputables && !c.imputable) return false;
        if (!texto) return true;
        return (
          c.nombre.toLowerCase().includes(texto) ||
          c.codigo.toLowerCase().includes(texto)
        );
      };
      for (const c of lista) {
        if (!califica(c)) continue;
        filtradas.add(c.id_cuenta);
        // Se muestran también todos sus padres, para que se vea de dónde sale.
        let padre = c.codigo_padre ? porCodigo.get(c.codigo_padre) : null;
        while (padre) {
          if (filtradas.has(padre.id_cuenta)) break;
          filtradas.add(padre.id_cuenta);
          padre = padre.codigo_padre ? porCodigo.get(padre.codigo_padre) : null;
        }
        cuantos += 1;
      }
    }

    return {
      raices,
      hijasDe: hijas,
      visibles: Array.from(porId.values()).filter(
        (c) => filtradas.size === 0 || filtradas.has(c.id_cuenta)
      ),
      filtradas: { set: filtradas, cuantos },
    };
  }, [lista, buscar, soloImputables]);

  // Al buscar, se abren todos los niveles para que se vea dónde está cada cosa.
  const estaAbierto = (c) => {
    if (filtradas.set.size > 0) return true;
    return abiertos.includes(c.codigo);
  };

  const alternar = (codigo) =>
    setAbiertos((v) =>
      v.includes(codigo) ? v.filter((x) => x !== codigo) : [...v, codigo]
    );

  // ---- acciones -------------------------------------------------------
  const renombrar = async (c, nombre) => {
    const limpio = (nombre || "").trim();
    setEditando(null);
    if (!limpio || limpio === c.nombre) return;
    setError("");
    setMensaje("");
    try {
      await editarPlanCuenta(c.id_cuenta, { nombre: limpio });
      await cargar();
      setMensaje(`Listo: ${c.codigo} ahora se llama "${limpio}".`);
    } catch (e) {
      setError(e.message);
    }
  };

  const cambiarImputable = async (c) => {
    setError("");
    setMensaje("");
    try {
      await editarPlanCuenta(c.id_cuenta, { imputable: !c.imputable });
      await cargar();
    } catch (e) {
      setError(e.message);
    }
  };

  const cambiarAuxiliar = async (c, tipo) => {
    setError("");
    setMensaje("");
    try {
      await editarPlanCuenta(c.id_cuenta, { tipo_auxiliar: tipo });
      await cargar();
    } catch (e) {
      setError(e.message);
    }
  };

  const apagar = async (c) => {
    const ok = window.confirm(
      `¿Apagar la cuenta ${c.codigo} ${c.nombre}?\n\n` +
        "No se borra: queda en la base pero deja de ofrecerse. " +
        "Los asientos que ya la rebuten siguen viéndola."
    );
    if (!ok) return;
    setError("");
    setMensaje("");
    try {
      await apagarPlanCuenta(c.id_cuenta);
      await cargar();
      setMensaje(`Listo: ${c.codigo} quedó apagada.`);
    } catch (e) {
      setError(e.message);
    }
  };

  const agregar = async (e, padre) => {
    e.preventDefault();
    const form = e.target;
    const nombre = form.elements.nombre.value.trim();
    const tipo = form.elements.tipo_auxiliar.value;
    if (!nombre) return;
    setError("");
    setMensaje("");
    try {
      const r = await crearPlanCuenta({
        cuenta_padre_id: padre.id_cuenta,
        nombre,
        imputable: true,
        tipo_auxiliar: tipo,
      });
      await cargar();
      setAgregando(null);
      // Se abre el padre para que se vea la cuenta recién creada.
      setAbiertos((v) => (v.includes(padre.codigo) ? v : [...v, padre.codigo]));
      setMensaje(`Listo: se agregó ${r.codigo} ${r.nombre}.`);
    } catch (err) {
      setError(err.message);
    }
  };

  // ---- una fila del árbol ---------------------------------------------
  const fila = (c, nivelVisual = 0) => {
    const abierta = estaAbierto(c);
    const hijas = hijasDe.get(c.id_cuenta) || [];
    const tieneHijas = c.tiene_hijas || hijas.length > 0;
    const enEdicion = editando === c.id_cuenta;

    return (
      <div key={c.id_cuenta}>
        <div
          className={`pc-fila ${c.imputable ? "imputable" : "grupo"} ${
            c.activa ? "" : "apagada"
          }`}
          style={{ paddingLeft: `${0.6 + nivelVisual * 1.1}rem` }}
        >
          <button
            type="button"
            className="pc-flecha"
            onClick={() => alternar(c.codigo)}
            disabled={!tieneHijas}
            aria-label={abierta ? "Cerrar" : "Abrir"}
          >
            {tieneHijas ? (abierta ? "▾" : "▸") : "·"}
          </button>

          <span className="pc-codigo mono">{c.codigo}</span>

          <span className="pc-nombre">
            {enEdicion ? (
              <input
                type="text"
                autoFocus
                defaultValue={c.nombre}
                maxLength={150}
                onBlur={(e) => renombrar(c, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") renombrar(c, e.currentTarget.value);
                  if (e.key === "Escape") setEditando(null);
                }}
              />
            ) : (
              c.nombre
            )}
            {!c.activa && <span className="nota"> · apagada</span>}
          </span>

          {c.imputable ? (
            <span
              className={`pc-dh ${c.deudora_acreadora === "DEUDORA" ? "deudora" : "acreedora"}`}
              title={
                c.deudora_acreadora === "DEUDORA"
                  ? "Deudora: su saldo aumenta en el Debe"
                  : "Acreedora: su saldo aumenta en el Haber"
              }
            >
              {c.deudora_acreadora === "DEUDORA" ? "D" : "A"}
            </span>
          ) : (
            <span className="nota pc-dh" title="Un agrupador puede mezclar deudoras y acreedoras">—</span>
          )}

          {c.imputable ? (
            <select
              className="pc-aux"
              value={c.tipo_auxiliar || "NINGUNO"}
              onChange={(e) => cambiarAuxiliar(c, e.target.value)}
              disabled={!esAdmin}
              aria-label="Tipo de auxiliar"
              title="Qué dato extra se le pide al movimiento"
            >
              {TIPOS_AUXILIAR.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          ) : (
            <span className="nota pc-aux">agrupador</span>
          )}

          {esAdmin && (
            <span className="acciones">
              <button
                className="btn btn-sm fantasma"
                onClick={() => cambiarImputable(c)}
                disabled={tieneHijas && !c.imputable}
                title={
                  tieneHijas && !c.imputable
                    ? "Tiene subcuentas: no puede ser imputable"
                    : "Cambiar entre agrupador y cuenta"
                }
              >
                {c.imputable ? "Quitar imputable" : "Hacer imputable"}
              </button>
              {esAdmin && (
                <button className="btn btn-sm fantasma" onClick={() => setAgregando(agregando === c.id_cuenta ? null : c.id_cuenta)}>
                  + Subcuenta
                </button>
              )}
              <button className="btn btn-sm fantasma" onClick={() => setEditando(c.id_cuenta)}>
                Renombrar
              </button>
              <button
                className="btn btn-sm peligro"
                onClick={() => apagar(c)}
                disabled={tieneHijas || !c.imputable}
                title={
                  tieneHijas
                    ? "Primero apagá las subcuentas"
                    : !c.imputable
                    ? "Un agrupador no se borra, dejalo apagado"
                    : "Apagar la cuenta"
                }
              >
                Apagar
              </button>
            </span>
          )}
        </div>

        {agregando === c.id_cuenta && (
          <form
            className="pc-alta"
            style={{ paddingLeft: `${2.2 + nivelVisual * 1.1}rem` }}
            onSubmit={(e) => agregar(e, c)}
          >
            <input
              name="nombre"
              placeholder={`Nombre de la cuenta nueva bajo ${c.codigo}`}
              maxLength={150}
              autoFocus
            />
            <select name="tipo_auxiliar" defaultValue="NINGUNO">
              {TIPOS_AUXILIAR.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button className="btn btn-sm" type="submit">Agregar</button>
            <button
              className="btn btn-sm fantasma"
              type="button"
              onClick={() => setAgregando(null)}
            >
              Cancelar
            </button>
            <span className="nota">
              El código lo arma el sistema ({c.codigo}.__)
            </span>
          </form>
        )}

        {abierta &&
          hijas.map((h) => fila(h, nivelVisual + 1))}
      </div>
    );
  };

  return (
    <section>
      <div className="solo-impresion">
        <b>{NOMBRE_ESTUDIO}</b>
        <span>Plan de cuentas</span>
      </div>

      <span className="kicker">Contabilidad</span>
      <h1>Plan de cuentas</h1>
      <p className="lead">
        El plan es un <b>árbol en una sola tabla</b>: el código dice en qué nivel
        está (1 ACTIVO, 2 ACTIVO CORRIENTE, 3 Caja y bancos, 4 la cuenta). Los
        <b> agrupadores</b> sirven para agrupar en los informes; solo las
        <b> cuentas de detalle</b> (imputables) reciben movimientos.
      </p>

      <div className="pc-leyenda">
        <span>
          <b>Naturaleza:</b> BALANCE (activo, pasivo, patrimonio neto) o
          RESULTADO (ingresos, costos, gastos, resultados financieros). Define si
          la cuenta va al patrimonio o al resultado del ejercicio.
        </span>
        <span>
          <b>
            <i className="pc-dh deudora">D</i> Deudora
          </b>{" "}
          suma en el Debe ·{" "}
          <b>
            <i className="pc-dh acreedora">A</i> Acreedora
          </b>{" "}
          suma en el Haber. Los agrupadores pueden mezclar las dos, por eso
          llevan <span className="pc-dh">—</span>.
        </span>
      </div>

      <div className="buscador">
        <input
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          placeholder="Buscar por código o nombre…"
          aria-label="Buscar en el plan de cuentas"
        />
        <label className="campo">
          <span>&nbsp;</span>
          <label className="check">
            <input
              type="checkbox"
              checked={soloImputables}
              onChange={(e) => setSoloImputables(e.target.checked)}
            />
            Solo imputables
          </label>
        </label>
        <label className="campo">
          <span>&nbsp;</span>
          <label className="check">
            <input
              type="checkbox"
              checked={verApagadas}
              onChange={(e) => setVerApagadas(e.target.checked)}
            />
            Mostrar apagadas
          </label>
        </label>
        {abiertos.length > 0 && (
          <button
            className="btn btn-sm fantasma"
            type="button"
            onClick={() => setAbiertos([])}
          >
            Cerrar todo
          </button>
        )}
        <button className="btn btn-sm fantasma" type="button" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {mensaje && (
        <p className="aviso-guardado" role="status">
          {mensaje}
        </p>
      )}

      <div className="pc-arbol">
        {cargando && <p className="nota">Buscando…</p>}

        {!cargando && lista.length === 0 && (
          <p className="nota">No hay cuentas cargadas.</p>
        )}

        {!cargando && (
          <>
            {(filtradas.cuantos > 0 || (buscar && soloImputables)) && (
              <p className="nota">
                {filtradas.cuantos} cuenta{filtradas.cuantos === 1 ? "" : "s"}{" "}
                coinciden (se muestran los grupos del medio).
              </p>
            )}
            {raices.map((c) => fila(c))}
          </>
        )}
      </div>

      <p className="nota">
        {cargando
          ? ""
          : `${lista.length} cuenta${lista.length === 1 ? "" : "s"} · ` +
            `${lista.filter((c) => c.imputable).length} imputables · ` +
            `${lista.filter((c) => !c.imputable).length} agrupadores` +
            (verApagadas ? " (incluye apagadas)" : "")}
      </p>

      <p className="nota">
        <b>El código no se toca.</b> Aunque renombres una cuenta, su código queda
        como está, porque es lo que van a usar los asientos. Para cambiar la
        estructura hay que dar de alta una cuenta nueva y apagar la vieja.
      </p>
    </section>
  );
}