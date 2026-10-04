import Alicuotas from "./Alicuotas.jsx";
import CentrosCostos from "./CentrosCostos.jsx";
import TiposGastos from "./TiposGastos.jsx";
import IndiceMoneda from "./IndiceMoneda.jsx";
import VencimientosConfig from "./VencimientosConfig.jsx";
import EjercicioConfig from "./EjercicioConfig.jsx";
import PeriodosConfig from "./PeriodosConfig.jsx";
import ConfigAsientos from "./ConfigAsientos.jsx";
import Propietario from "./Propietario.jsx";
import Bancos from "../components/Bancos.jsx";
import { obtenerPropietario, guardarPropietario } from "../api/propietario.js";

export default function Configuracion() {
  return (
    <section>
      <span className="kicker">Sistema</span>
      <h1>Configuración</h1>
      <p className="lead">
        Tablas y valores del sistema.
      </p>

      {/* El ejercicio va primero: sin ejercicio abierto no se puede asentar
          nada, así que es lo primero que hay que mirar si algo no carga. */}
      <EjercicioConfig />

      {/* Y los períodos enseguida abajo, porque son el otro lado de lo mismo:
          el ejercicio dice "nadie escribe en el año", el período dice "nadie
          escribe en este mes". */}
      <div style={{ marginTop: "3rem" }}>
        <PeriodosConfig />
      </div>

      <div style={{ marginTop: "3rem" }}>
        <Alicuotas />
      </div>

      {/* El catálogo de bancos va acá porque se llena SOLO, con los CBU que se
          cargan en las fichas de los clientes. Lo que hay que hacer a mano es
          ponerle el nombre a los que quedaron provisorios. */}
      <div style={{ marginTop: "3rem" }}>
        <Bancos />
      </div>

      <div style={{ marginTop: "3rem" }}>
        <TiposGastos />
      </div>

      <div style={{ marginTop: "3rem" }}>
        <IndiceMoneda />
      </div>

      <div style={{ marginTop: "3rem" }}>
        <VencimientosConfig />
      </div>

      {/* Va al final y no arriba porque no se mira todos los días: se abre
          cuando una factura no se asenta, o cuando hay que cambiar a qué
          cuenta va una venta. */}
      <div style={{ marginTop: "3rem" }}>
        <ConfigAsientos />
      </div>

      <div style={{ marginTop: "3rem" }}>
        <Propietario obtener={obtenerPropietario} guardar={guardarPropietario} />
      </div>
    </section>
  );
}
