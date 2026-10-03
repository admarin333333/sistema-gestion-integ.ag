import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { Link, useNavigate, useLocation, Outlet, NavLink } from "react-router-dom";
import { PeriodoActual } from "./PeriodoActual.jsx";

// Un ítem puede ser una pantalla (to) o un grupo con submenú (items).
// Lo que todavía no existe va con disabled: se ve apagado y no lleva a
// ningún lado, en vez de romper con un 404.
const MENU = [
  { label: "Dashboard", to: "/", exact: true },
  {
    // Lo del cliente: quién es, qué servicios tiene y qué le hacemos. El
    // catálogo de servicios es de TODOS los clientes, por eso va acá y no en la
    // ficha: si estuviera en la ficha, habría que duplicarlo por cliente.
    label: "Clientes",
    items: [
      { label: "Listado de clientes", to: "/clientes" },
      { label: "Servicios", to: "/servicios" },
    ],
  },
  { label: "Proveedores", to: "/proveedores" },
  { label: "Facturas", to: "/facturas" },
  { label: "Recibos", to: "/recibos" },
  { label: "Anticipos", to: "/anticipos" },
  { label: "Estado de cuenta", to: "/cuenta" },
  { label: "Estado de deuda", to: "/estado-deuda" },
  { label: "Anticipos pendientes", to: "/anticipos-pendientes" },
  { label: "Compras", to: "/compras" },
  {
    // Los INFORMES van todos juntos. Antes "Informe por centro" y "Informe de
    // resultados" eran dos botones sueltos entre medio del menú, y el de claves
    // fiscales estaba al final, al lado de Configuración: el contador tenía que
    // acordarse de dónde estaba cada uno. Los tres son informes, así que van en
    // un solo lugar y el que agranda son ellos, no el menú.
    label: "Informes",
    items: [
      // Cuenta corriente va PRIMERO: es el informe del día — cuánto debe cada
      // cliente y a quién llamar. Los otros son de cierre o de control.
      { label: "Cuenta corriente", to: "/informe-cuenta-corriente" },
      // Libro de IVA: informe fiscal, no de gestión. Va después de la cuenta
      // corriente porque esa es la consulta del día; el libro se arma una vez
      // al mes, para el contador.
      { label: "Libro de IVA ventas", to: "/libro-iva-ventas" },
      { label: "Por centro de costos", to: "/informe-centros" },
      { label: "De resultados", to: "/informe-resultados" },
      { label: "De claves fiscales", to: "/informe-claves-fiscales" },
    ],
  },
  {
    // Los módulos de contabilidad de un CLIENTE (los que el estudio le presta).
    // Van juntos porque se abren siempre desde la ficha de un cliente: el balance
    // es de ese cliente, no del estudio. Acá entran los que se agreguen después
    // (conciliación, impuesto, certificates).
    label: "Contabilidad del cliente",
    items: [
      // "Balance general" es el mismo módulo que era "Balance RT54": el balance
      // patrimonial que fija la Resolución 54/2012. Para el contador es el
      // balance del cliente.
      { label: "Balance general", to: "/balance-rt54" },
    ],
  },
  {
    // La contabilidad DEL ESTUDIO: el plan de cuentas y los libros. No se
    // mezclan con la del cliente: son dos cosas distintas y confundirlas es
    // justo el error que hicieron las tablas de ejercicios.
    label: "Contabilidad",
    items: [
      { label: "Plan de cuentas", to: "/plan-cuentas" },
      { label: "Mayores generales", to: "/mayores" },
      { label: "Asientos contables", to: "/asientos" },
    ],
  },
  { label: "Vencimientos", to: "/vencimientos" },
  { label: "Configuración", to: "/configuracion" },
];

const fechaHoy = () =>
  new Date().toLocaleDateString("es-AR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  /**
   * Qué grupo está abierto, como UN solo nombre o ninguno.
   *
   * Antes era un `Set` y por eso pasaba esto: abriste "Clientes", después
   * "Contabilidad", y los dos seguían abiertos con su flecha para arriba. Con un
   * `Set` no hay forma de saber cuál es el que querés, y además el grupo que
   * contiene la pantalla actual se abría solo y se sumaba al que habías abierto
   * a mano.
   *
   * Ahora hay una sola regla y es simple: **un grupo abierto a la vez**. El que
   * contiene la pantalla actual se abre solo; si abriste otro a mano, gana el
   // que abriste vos hasta que lo cierres.
   */
  const [abiertoManual, setAbiertoManual] = useState(null);

  // El panel se cierra solo en tres casos, porque dejarlo abierto tapando el
  // contenido era lo más molesto:
  //   1. apretás un ítem del panel (navegás a esa pantalla);
  //   2. apretás en cualquier lado que no sea el menú;
  //   3. apretás el título del mismo grupo otra vez (ahí lo hace `alternarGrupo`).
  const zonaMenu = useRef(null);

  useEffect(() => {
    if (abiertoManual === null) return undefined;

    // (1) Al navegar: si se abrió a mano, se cierra. El que se abre solo por la
    // pantalla en la que estás no se cierra (ese es justamente su propósito).
    const alNavegar = () => setAbiertoManual(null);
    window.addEventListener("gc:navegado", alNavegar);

    // (2) Clic afuera del menú.
    const alClic = (e) => {
      if (zonaMenu.current && !zonaMenu.current.contains(e.target)) {
        setAbiertoManual(null);
      }
    };
    // `mousedown` y no `click`: el `click` dispara después, y con `mousedown` el
    // panel ya está cerrado cuando el click llega al otro lado.
    document.addEventListener("mousedown", alClic);

    // Escape también cierra: para quien trabaja con teclado.
    const alEscape = (e) => {
      if (e.key === "Escape") setAbiertoManual(null);
    };
    document.addEventListener("keydown", alEscape);

    return () => {
      window.removeEventListener("gc:navegado", alNavegar);
      document.removeEventListener("mousedown", alClic);
      document.removeEventListener("keydown", alEscape);
    };
  }, [abiertoManual]);

  // Al cambiar de pantalla, si el grupo que estaba abierto a mano ya no está
  // (o ya no tenés razón para tenerlo abierto), se cierra igual.
  useEffect(() => {
    if (abiertoManual === null) return;
    const sigue = MENU.some(
      (m) => m.items && m.label === abiertoManual && contienePagina(m)
    );
    if (sigue) setAbiertoManual(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const menuItem = ({ label, to, exact = false, disabled }) => {
    if (disabled || !to) {
      return (
        <span
          key={label}
          className="item"
          style={{ opacity: 0.5, cursor: "not-allowed" }}
          title="Próximamente"
        >
          {label}
          {disabled && <i>F5</i>}
        </span>
      );
    }

    return (
      <NavLink
        key={to}
        to={to}
        className={({ isActive }) => `item${isActive ? " activo" : ""}`}
        end={exact}
        // El panel se cierra solo al apretar un ítem: si no, queda abierto
        // tapando la pantalla que recién abriste.
        onClick={() => window.dispatchEvent(new CustomEvent("gc:navegado"))}
      >
        {label}
      </NavLink>
    );
  };

  /** Un grupo del menú (hoy: Contabilidad). Se abre al apretar el título y se
   *  mantiene abierto mientras estés adentro de él, así no se pierde el
   *  lugar donde estás parado.
   *
   *  OJO: el desplegable NO se dibuja acá adentro. Antes colgaba del botón
   *  (`position: absolute` sobre `.grupo-menu`), y como la fila del menú es un
   *  `flex-wrap`, el panel caía ENCIMA de los botones que tenía al lado y de los
   *  que envolvían a la fila siguiente: no se podían apretar. Por eso se dibuja
   *  una sola vez, debajo de toda la fila — ver `grupoAbierto` más abajo. */
  const contienePagina = ({ items }) =>
    items.some((i) => i.to && location.pathname.startsWith(i.to));

  /** Un grupo a la vez: el que abriste vos, o —si no abriste ninguno— el que
   *  tiene la pantalla en la que estás. Nunca los dos. */
  const estaAbierto = (grupo) =>
    abiertoManual === grupo.label ||
    (abiertoManual === null && contienePagina(grupo));

  const alternarGrupo = (label) =>
    setAbiertoManual((v) => (v === label ? null : label));

  const menuGrupo = (grupo) => {
    const { label, items } = grupo;
    const dentro = items.some((i) => i.to && location.pathname.startsWith(i.to));
    const abierto = estaAbierto(grupo);

    return (
      <div key={label} className="grupo-menu">
        <button
          type="button"
          className={`item grupo-titulo${abierto ? " abierto" : ""}${
            dentro ? " activo" : ""
          }`}
          onClick={() => alternarGrupo(label)}
          aria-expanded={abierto ? "true" : "false"}
        >
          {label}
          <i className="flecha">{abierto ? "▴" : "▾"}</i>
        </button>
      </div>
    );
  };

  // El desplegable del grupo que esté abierto, uno solo, debajo de la fila.
  // Se DERIVA del estado (no se guarda): el grupo abierto es "el que eligió el
  // contador, o el que contiene la pantalla en la que está".
  const grupoAbierto = MENU.find((m) => m.items && estaAbierto(m));

  return (
    <>
      <header className="topbar">
        <div className="wrap">
          <Link to="/" className="brand" onClick={(e) => { e.preventDefault(); navigate("/"); }}>
            Gestión <span>Estudio contable</span>
          </Link>

          <div className="hoy">
            <b>{fechaHoy()}</b>
            <small>
              {user.nombre} · {user.rol}
            </small>
          </div>

          <button className="btn btn-sm fantasma" onClick={logout}>
            Salir
          </button>
        </div>
      </header>

      {/* El menú y su panel van en el MISMO contenedor: el panel tiene que caer
          debajo de toda la fila (si cuelga del botón tapa los de al lado), pero
          seguir siendo parte de la zona del menú, para que un clic afuera lo
          cierre. */}
      <div ref={zonaMenu}>
        <nav className="menu wrap">
          {MENU.map((m) => (m.items ? menuGrupo(m) : menuItem(m)))}
        </nav>

        {grupoAbierto && (
          <div className="grupo-panel wrap">
            <div className="grupo-panel-titulo">{grupoAbierto.label}</div>
            <div className="grupo-items">
              {grupoAbierto.items.map((i) => menuItem({ ...i, exact: false }))}
            </div>
          </div>
        )}
      </div>

      {/* El período de trabajo va en la barra y no dentro de cada pantalla: es
          una decisión del contador, no de una pantalla. */}
      <div className="wrap">
        <PeriodoActual />
      </div>

      <main className="wrap">
        <Outlet />
      </main>

      <footer className="pie">
        <div className="wrap">Sistema de gestión · Fase 4 · datos locales</div>
      </footer>
    </>
  );
}