import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ETIQUETAS_CONDICION_IVA, listarClientes, listarProveedores } from "../api/clientes.js";
import Periodo from "../components/Periodo.jsx";
import Variantes from "../components/Variantes.jsx";

const LETRAS = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ".split("");

/**
 * La letra con la que arranca cada cliente, para el índice A–Z.
 *
 * Sale del **apellido** si hay, y si no del nombre: en una persona jurídica el
 * nombre ES la razón social, que es por donde se la busca igual. Se le sacan
 * los tildes para que "Peña" caiga bajo la N y no bajo una letra rara.
 */
function inicial(c) {
  const crudo = (c.apellido || c.nombre || "").trim();
  if (!crudo) return "#";
  const primera = crudo[0].toUpperCase();
  // La Ñ se separa a mano: `normalize` la descompone en "N" + diacrítico, y
  // entonces "Ñuñez" caería bajo la N. Para un contador argentino, la Ñ tiene
  // que tener su propia letra.
  if (primera === "Ñ") return "Ñ";
  // `\u0300-\u036f` son los diacríticos: se sacan para que "Peña" caiga bajo la
  // N y no bajo una letra rara. Se escriben con `\u` para que no dependa de cómo
  // se guarde el archivo.
  const sinTilde = primera.normalize("NFD").replace(/[̀-ͯ]/g, "");
  return LETRAS.includes(sinTilde) ? sinTilde : "#";
}

// El listado arranca ordenado por apellido/razón social, de la Z a la A: es el
// orden en el que el contador busca ("buscame los Pérez") y es el inverso del
// alfabeto, que es como están escritos los libros.
const VACIO = { q: "", desde: "", hasta: "", orden: "nombre", desc: true };

// Las columnas por las que se puede ordenar. El ícono ▲▼ muestra hacia dónde
// va. El `ORDER BY` lo arma el backend (ver `cliente_service.ORDENES`): acá
// solo se elige la columna y se manda. Ordenar en el navegador obligaría a
// traer todas las filas para recién ahí compararlas.
const ORDENES = [
  { id: "nombre", etiqueta: "Apellido y nombre" },
  { id: "razon_social", etiqueta: "Razón social" },
  { id: "apellido", etiqueta: "Apellido" },
  { id: "fecha_alta", etiqueta: "Alta" },
  { id: "nro_cuenta", etiqueta: "Cuenta" },
  { id: "cuit", etiqueta: "CUIT" },
  { id: "localidad", etiqueta: "Localidad" },
];

export default function Clientes({ tipo = "cliente" }) {
  const navigate = useNavigate();
  const esProveedor = tipo === "proveedor";
  const pref = esProveedor ? "proveedor" : "cliente";
  const plural = esProveedor ? "proveedores" : "clientes";
  const singular = esProveedor ? "proveedor" : "cliente";
  const titulo = esProveedor ? "Proveedores" : "Clientes del estudio";
  const [filtros, setFiltros] = useState(VACIO);
  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  // La referencia a la tabla, para que el índice A–Z pueda hacer `scrollIntoView`
  // sobre la fila de esa letra.
  const cuerpoTabla = useRef(null);

  const cargar = async (f = filtros) => {
    setCargando(true);
    setError("");
    try {
      // Cada módulo pide a su propio endpoint: no se mezclan clientes y proveedores.
      setLista(
        esProveedor
          ? await listarProveedores(f.q, f)
          : await listarClientes(f.q, f)
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    setFiltros(VACIO);
    cargar(VACIO);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo]);

  const buscar = (e) => {
    e.preventDefault();
    cargar(filtros);
  };

  /**
   * EL BUSCADOR FILTRA AL ESCRIBIR.
   *
   * Antes filtraba solo al apretar "Buscar" (o Enter). Se escribía el nombre y la
   * tabla seguía mostrando TODOS los clientes: lo primero que parece es que la
   * búsqueda está rota. Ahora escribís y filtra, como el buscador de cliente de
   * las demás pantallas. El botón "Buscar" sigue estando — sirve para aplicar
   * los filtros de período y fecha de una sola vez.
   *
   * Los 300 ms son para no ir a la base con cada tecla: "distribuidora" son 11
   * pedidos donde alcanza con uno.
   *
   * `desdeElCampo` distingue lo que escribió la persona de lo que saltó solo
   * (cargar una variante guardada, limpiar): en esos casos la búsqueda la pide
   * quien la pidió y este efecto haría una segunda al pedo.
   */
  const desdeElCampo = useRef(false);

  const escribir = (e) => {
    desdeElCampo.current = true;
    setFiltros({ ...filtros, q: e.target.value });
  };

  useEffect(() => {
    if (!desdeElCampo.current) return;
    desdeElCampo.current = false;
    const reloj = setTimeout(() => cargar(filtros), 300);
    return () => clearTimeout(reloj);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtros.q]);

  const set = (campo) => (e) =>
    setFiltros({ ...filtros, [campo]: e.target.value });

  // Un clic ordena de la A a la Z; el siguiente, al revés. Si ya estaba en esa
  // columna, se da vuelta: es el comportamiento que espera cualquiera que haya
  // usado una tabla.
  const ordenarPor = (columna) => {
    const nuevo = {
      ...filtros,
      orden: columna,
      desc: filtros.orden === columna ? !filtros.desc : false,
    };
    setFiltros(nuevo);
    cargar(nuevo);
  };

  /**
   * El índice A–Z: salta al primer cliente de esa letra.
   *
   * Solo tiene sentido con la lista ordenada por apellido/razón social: si está
   * ordenada por fecha de alta, las letras salen mezcladas y el índice mentiría.
   * Por eso, si no se está ordenando por nombre, no se muestra.
   *
   * Las letras que no existen en el listado salen apagadas: apretar una letra
   * que no está hace menos claro que apretarla y que no pase nada.
   */
  const porNombre = filtros.orden === "nombre" || filtros.orden === "apellido"
    || filtros.orden === "razon_social";
  const letras = new Set(lista.map(inicial));

  const irALetra = (letra) => {
    if (!letras.has(letra)) return;
    // Con la lista al revés, la letra aparece al final: el salto tiene que
    // buscar la fila, no asumir una posición.
    const fila = [...cuerpoTabla.current.children].find((f) => {
      const nombre = f.querySelector("td:nth-child(2) b");
      return nombre && inicial({ apellido: nombre.textContent }) === letra;
    });
    if (fila) fila.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const th = (columna, etiqueta) => (
    <th
      className={columna === filtros.orden ? "orden-activo" : ""}
      onClick={() => ordenarPor(columna)}
      title={`Ordenar por ${etiqueta.toLowerCase()}`}
    >
      {etiqueta}
      {filtros.orden === columna && (
        <span className="flecha-orden">{filtros.desc ? "▼" : "▲"}</span>
      )}
    </th>
  );

  return (
    <section>
      <span className="kicker">{esProveedor ? "Proveedores" : "Clientes"}</span>
      <h1>{titulo}</h1>
      <p className="lead">
        Buscá por <b>nombre</b>, <b>DNI</b> o <b>CUIT</b> — sin guiones. Los
        filtros de fecha son por <b>fecha de alta</b>. Tocá el título de una
        columna para ordenar.
      </p>

      <form className="buscador" onSubmit={buscar}>
        <input
          value={filtros.q}
          onChange={escribir}
          placeholder="Ej: Pérez, 26473674 o 20-26473674-2"
          aria-label={`Buscar ${singular}`}
        />
        <Periodo filtros={filtros} setFiltros={setFiltros} />
        <button className="btn btn-sm" type="submit">
          Buscar
        </button>
        <button
          className="btn btn-sm fantasma"
          type="button"
          onClick={() => {
            setFiltros(VACIO);
            cargar(VACIO);
          }}
        >
          Limpiar
        </button>
        <button
          className="btn btn-sm"
          type="button"
          onClick={() => navigate(`/${pref}-alta`)}
        >
          + Nuevo {singular}
        </button>
      </form>

      <Variantes
        // Ojo: el backend espera el nombre en plural ("clientes"), no el `tipo`
        // singular que usa el resto de la pantalla.
        pantalla={plural}
        filtros={filtros}
        setFiltros={setFiltros}
        onCargar={cargar}
      />

      {error && <p className="error">{error}</p>}

      {/* El índice A–Z. Solo aparece con la lista ordenada por apellido o razón
          social: con otro orden las letras salen mezcladas y no servirían.

          El corte es a los 8: con menos, la lista entra en una pantalla y el
          índice sobraría. */}
      {porNombre && lista.length > 8 && (
        <nav className="indice-az" aria-label="Ir a la letra">
          {LETRAS.map((l) => (
            <button
              key={l}
              type="button"
              className={letras.has(l) ? "" : "vacio"}
              onClick={() => irALetra(l)}
              disabled={!letras.has(l)}
              title={
                letras.has(l)
                  ? `Ir a los ${l}`
                  : `No hay ninguno que empiece con ${l}`
              }
            >
              {l}
            </button>
          ))}
        </nav>
      )}

      {/* `.tabla-scroll`: la caja con scroll propio y el encabezado clavado, como
          en Recibos. El `max-height` que hace eso está en `styles.css`. */}
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              {th("nro_cuenta", "Cuenta")}
              {th("nombre", esProveedor ? "Proveedor" : "Cliente")}
              {th("razon_social", "Razón social")}
              {th("cuit", "CUIT")}
              <th>DNI</th>
              <th>Cond. IVA</th>
              {th("localidad", "Localidad")}
              {th("fecha_alta", "Alta")}
              <th>Servicios</th>
              <th></th>
            </tr>
          </thead>
          <tbody ref={cuerpoTabla}>
            {cargando && (
              <tr>
                <td colSpan="10" className="vacio">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && lista.length === 0 && (
              <tr>
                <td colSpan="10" className="vacio">
                  {filtros.q
                    ? `No hay nadie que coincida con «${filtros.q}».`
                    : `Todavía no hay ${plural} cargados.`}
                </td>
              </tr>
            )}

            {!cargando &&
              lista.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.nro_cuenta}</td>
                  <td>
                    <b>{c.nombre_completo}</b>
                    <small>
                      {c.tipo_persona === "juridica"
                        ? "Persona jurídica"
                        : "Persona física"}
                    </small>
                  </td>
                  <td>
                    {c.tipo_persona === "juridica" ? (
                      c.razon_social || c.nombre || "—"
                    ) : (
                      <span className="vacio">—</span>
                    )}
                  </td>
                  <td className="mono">{c.cuit || "—"}</td>
                  <td className="mono">{c.dni || "—"}</td>
                  <td>{ETIQUETAS_CONDICION_IVA[c.condicion_iva] || c.condicion_iva || "—"}</td>
                  <td>{c.localidad || "—"}</td>
                  <td className="mono">{c.fecha_alta || "—"}</td>
                  <td className="mono">
                    {esProveedor ? "—" : (c.servicios || []).length}
                  </td>
                  <td className="acciones">
                    <button
                      className="btn btn-sm"
                      onClick={() => navigate(`/${pref}-ficha/${c.id}`)}
                    >
                      Ficha
                    </button>
                    <button
                      className="btn btn-sm fantasma"
                      onClick={() => navigate(`/${pref}-editar/${c.id}`)}
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}

            {/* El total va DENTRO del scroll, no debajo: así queda pegado al
                final de la lista y no se va al final de la página cuando hay
                muchas filas. */}
            {!cargando && lista.length > 0 && (
              <tr className="fila-total">
                <td colSpan="9">
                  {lista.length} {lista.length === 1 ? singular : plural} en el
                  listado
                </td>
                <td className="acciones"></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
