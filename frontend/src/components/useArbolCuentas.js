import { useMemo, useState } from "react";

/**
 * El ÁRBOL DEL PLAN DE CUENTAS, compartido entre PlanCuentas y Mayores.
 *
 * Las dos pantallas lo usan porque es la misma pregunta: "¿cuál de estas
 * cuentas me interesa?". Si cada una armara su árbol por su lado, el contador
 * vería dossubseteq distintos para las mismas cuentas —una losWords planos, la
 * otra en jerarquía— y no sabría si son la misma cosa.
 *
 * El backend manda la lista PLANA ordenada por código (que ya viene en orden de
 * árbol) con `codigo_padre`. Acá se cuelga cada una de su padre.
 *
 * `soloImputables` esconde las agrupadoras: para el Plan de Cuentas se ven
 * (son las que agrupan), pero para elegir QUÉ cuenta abrir en un mayor, una
 * agrupadora no sirve: no recibe movimientos.
 */
export function useArbolCuentas(lista, { buscar = "", soloImputables = false } = {}) {
  // Las cuentas abiertas, por código. El código y no el id porque es lo que la
  // persona ve: "dejame abierto 1.1.01 Caja y bancos".
  const [abiertos, setAbiertos] = useState([]);

  const { raices, hijasDe, porId, filtradas } = useMemo(() => {
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

    // El buscador y el filtro de imputables. Si está filtrando, se muestra la
    // cuenta que coincide aunque su padre esté cerrado: si no, no se vería nada
    // y el buscador parecería roto.
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

    return { raices, hijasDe: hijas, porId, filtradas: { set: filtradas, cuantos } };
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

  const abrirRama = (codigo) =>
    setAbiertos((v) => (v.includes(codigo) ? v : [...v, codigo]));

  const estaFiltrando = filtradas.set.size > 0;

  return {
    raices,
    hijasDe,
    porId,
    abierta: estaAbierto,
    alternar,
    abrirRama,
    estaFiltrando,
    cuantas: filtradas.cuantos,
    /** Las cuentas que se ven con el filtro actual, en orden de árbol. */
    visibles: lista.filter((c) => !estaFiltrando || filtradas.set.has(c.id_cuenta)),
  };
}