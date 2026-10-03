/**
 * El PERÍODO en el que el contador está trabajando.
 *
 * No es un filtro más: es una decisión del contador ("estoy con septiembre"), y
 * las dos cosas que se derivan de ella se guardan juntas:
 *
 *  1. **El período** (el número del 1 al 12 dentro del ejercicio). Es lo que
 *     aparece arriba y lo que avisa si el mes está cerrado.
 *  2. **Las fechas del mes**, que se ponen en los filtros de las pantallas.
 *
 * Se guarda en `localStorage` para que al volver al sistema el contador siga
 * en el mes donde estaba y no en "hoy".
 *
 * Por qué NO se derivan solo del filtro de fechas de cada pantalla: porque el
 * error más caro de la contabilidad es trabajar en el mes equivocado. Si cada
 * pantalla tiene su propio filtro, es fácil cargar una factura de septiembre
 * mientras está mirando octubre. Con un período único arriba, la pantalla dice
 * en qué mes estás y los filtros vienen puestos.
 *
 * Se exportan dos cosas: `PeriodoActual` (la barrita) y `usePeriodoTrabajo`
 * (para que `Periodo.jsx`, el filtro de fechas, sepa con qué mes llenarse).
 */

import { useCallback, useEffect, useState } from "react";
import { periodoDeFecha } from "../api/ejercicios.js";

const CLAVE = "gc_periodo";

const HOY = new Date().toISOString().slice(0, 10);

function leerGuardado() {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    return crudo ? JSON.parse(crudo) : null;
  } catch {
    // localStorage puede estar bloqueado (modo privado). No es motivo para
    // romper la pantalla: se sigue sin recordar el período.
    return null;
  }
}

function guardar(valor) {
  try {
    if (valor) window.localStorage.setItem(CLAVE, JSON.stringify(valor));
    else window.localStorage.removeItem(CLAVE);
  } catch {
    /* ver leerGuardado */
  }
}

/* ------------------------------------------------------------- el período */

/**
 * Devuelve el período elegido y cómo cambiarlo.
 *
 * `periodo` trae `numero`, `nombre`, `fecha_inicio`, `fecha_fin` y `cerrado`.
 * La primera vez se pide al backend el período de HOY, así que recién en el
 * primer render `cargando` vale true.
 */
export function usePeriodoTrabajo() {
  const [periodo, setPeriodo] = useState(leerGuardado());
  const [cargando, setCargando] = useState(!periodo);

  useEffect(() => {
    // Si ya hay uno guardado, se respeta: el contador puede estar trabajando
    // en un mes que no es el de hoy (rezagando, por ejemplo).
    if (periodo) return;
    let vivo = true;
    periodoDeFecha(HOY)
      .then((r) => {
        if (!vivo) return;
        if (r.periodo) {
          setPeriodo(r.periodo);
          guardar(r.periodo);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (vivo) setCargando(false);
      });
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const elegir = useCallback((nuevo) => {
    setPeriodo(nuevo);
    guardar(nuevo);
    // Aviso a las pantallas para que recarguen sus datos con el mes nuevo.
    window.dispatchEvent(new CustomEvent("gc:periodo-cambiado", { detail: nuevo }));
  }, []);

  // Si alguien despacha el evento (la pantalla de Configuración, al abrir o
  // cerrar el período que está elegido), la barra se actualiza. Sin esto, el
  // contador cerraría el mes en Configuración y arriba seguiría diciendo
  // "abierto".
  useEffect(() => {
    const fn = (e) => {
      setPeriodo(e.detail);
      guardar(e.detail);
    };
    window.addEventListener("gc:periodo-cambiado", fn);
    return () => window.removeEventListener("gc:periodo-cambiado", fn);
  }, []);

  return { periodo, cargando, elegir };
}

/* ------------------------------------------------------------ la barrita */

/**
 * La barra de arriba: en qué período se está trabajando y si está abierto.
 *
 * Es informativa: no impide hacer nada. Lo que frena es el backend, que
 * devuelve 409 con el nombre del período. Duplicar la regla en el navegador
 * haría que dos pantallas mostraran dos cosas distintas, que es exactamente el
 * problema que hay que evitar.
 */
export function PeriodoActual() {
  const { periodo, cargando, elegir } = usePeriodoTrabajo();
  const [lista, setLista] = useState([]);

  // Los 12 períodos del ejercicio, para el desplegable.
  useEffect(() => {
    if (!periodo) return;
    let vivo = true;
    import("../api/ejercicios.js").then(({ listarPeriodos }) =>
      listarPeriodos(periodo.id_ejercicio)
        .then((r) => {
          if (vivo) setLista(r.periodos);
        })
        .catch(() => {})
    );
    return () => {
      vivo = false;
    };
  }, [periodo?.id_ejercicio]);

  if (cargando || !periodo) return null;

  // El estado (abierto/cerrado) sale de la lista recién consultada, no del
  // período guardado. El guardado dice qué mes elegiste, no si lo cerraste
  // después desde Configuración: si se usara el guardado, la barra seguiría
  // diciendo "abierto" en un mes que recién cerraste.
  const actual = lista.find((p) => p.id_periodo === periodo.id_periodo) || periodo;

  return (
    <div className="periodo-actual">
      <label className="campo campo-periodo">
        <span>Período de trabajo</span>
        <select
          value={actual.id_periodo}
          onChange={(e) => {
            const elegido = lista.find((p) => p.id_periodo === Number(e.target.value));
            if (elegido) elegir(elegido);
          }}
        >
          {lista.map((p) => (
            <option key={p.id_periodo} value={p.id_periodo}>
              {p.numero}. {p.nombre}
              {p.cerrado ? " — cerrado" : ""}
            </option>
          ))}
        </select>
      </label>

      {actual.cerrado && (
        <span className="periodo-cerrado">
          Período <b>cerrado</b>: no se puede cargar, anular ni modificar nada con
          fecha de este mes.
        </span>
      )}
    </div>
  );
}

/* --------------------------------------- el puente con los filtros de fecha */

/**
 * Lee el período guardado. Lo exporta porque `PeriodosConfig.jsx` (la pantalla
 * de Configuración) necesita compararlo con el que está elegido para saber si
 * tiene que avisarle que cambió.
 */
export function leerPeriodoGuardado() {
  return leerGuardado();
}

/** "2026-09-01" → { modo: "mes", mes: "09", anio: "2026", desde, hasta } */
export function filtrosDelPeriodo(p) {
  if (!p) return {};
  const [anio, mes] = p.fecha_inicio.split("-");
  return {
    modo: "mes",
    mes,
    anio,
    desde: p.fecha_inicio,
    // El último día se saca del propio período, no del calendario: el backend
    // ya lo tiene guardado y así el navegador no recalcula nada.
    hasta: p.fecha_fin,
  };
}

/**
 * Llena los filtros de la pantalla con el período de trabajo, y se vuelven a
 * llenar cada vez que el contador cambia de período.
 *
 * Para las pantallas que guardan un objeto `filtros`.
 *
 * `alCambiar` es el `cargar` de la página. Hace falta porque los totales y las
 * listas se calculan en el backend: no alcanza con cambiar las fechas de la
 * pantalla, hay que volver a pedir los datos.
 */
export function usePeriodoEnFiltros(setFiltros, alCambiar) {
  const { periodo } = usePeriodoTrabajo();

  useEffect(() => {
    if (!periodo) return;
    setFiltros((v) => ({ ...v, ...filtrosDelPeriodo(periodo) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo?.id_periodo]);

  useEffect(() => {
    const fn = (e) => {
      setFiltros((v) => ({ ...v, ...filtrosDelPeriodo(e.detail) }));
      alCambiar();
    };
    window.addEventListener("gc:periodo-cambiado", fn);
    return () => window.removeEventListener("gc:periodo-cambiado", fn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alCambiar]);
}

/**
 * El mismo puente para las pantallas que guardan `desde` y `hasta` sueltos, que
 * son las de la Contabilidad.
 */
export function usePeriodoEnFechas(setDesde, setHasta) {
  const { periodo } = usePeriodoTrabajo();

  useEffect(() => {
    if (!periodo) return;
    setDesde(periodo.fecha_inicio);
    setHasta(periodo.fecha_fin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo?.id_periodo]);

  useEffect(() => {
    const fn = (e) => {
      setDesde(e.detail.fecha_inicio);
      setHasta(e.detail.fecha_fin);
    };
    window.addEventListener("gc:periodo-cambiado", fn);
    return () => window.removeEventListener("gc:periodo-cambiado", fn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}