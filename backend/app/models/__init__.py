from app.models.alicuota import AlicuotaIva
from app.models.balance_rt54 import (
    BalanceEjercicio,
    BalanceNota,
    BalanceNotaCelda,
    BalanceValor,
)
from app.models.centrocosto import CentroCosto
from app.models.compra import Compra
from app.models.variante import Variante
from app.models.tipogasto import TipoGasto
from app.models.anticipo import Anticipo, AplicacionAnticipo
from app.models.clave_fiscal import ClaveFiscalHistorial
from app.models.cliente import Cliente
from app.models.concepto_vencimiento import ConceptoVencimiento
from app.models.vencimiento_mes import VencimientoMes
from app.models.factura import Factura
from app.models.localidad import Localidad
from app.models.recibo import Aplicacion, Recibo
from app.models.servicio import ClienteServicio, Servicio
from app.models.sugerencia import Sugerencia
from app.models.usuario import Usuario
from app.models.vencimiento_impositivo import VencimientoImpositivo
from app.models.persona import Persona
from app.models.plan_cuenta import PlanCuenta
from app.models.comprobante_interno import ComprobanteInterno
from app.models.asiento import Asiento, AsientoDetalle
from app.models.asiento_origen import AsientoOrigen
from app.models.ejercicio import Ejercicio
from app.models.periodo import Periodo
from app.models.proveedor import Proveedor
from app.models.propietario import Propietario
from app.models.cta_bancaria import Banco, CtaBariaCliente

# `IndiceMoneda` faltaba en esta lista. El modelo existía y era correcto, pero
# sin importarse acá nunca entraba en `Base.metadata`: el ORM no lo veía y
# Alembic creía que la tabla `config_indices_moneda` (con sus 404 filas de
# histórico de precios) no tenía modelo y quería crearla de cero.
#
# **Este import es obligatorio, no cosmético.** Sin él, un `--autogenerate`
# proposingía crear una tabla vacía con el mismo nombre y la real quedaría
# conflictuando.
from app.models.indice import IndiceMoneda

# Las cuatro tablas de configuración. Antes se consultaban con SQL a mano y no
# tenían modelo, así que Alembic las veía como tablas sobrantes y proponía
# borrarlas. Modelarlas las hace visibles: ahora las compara de verdad, y las
# crea en una base nueva (que sin ellas no podría facturar).
from app.models.config import (
    ConfigAsiento,
    ConfigComprobante,
    ConfigCuentaFormaPago,
    ConfigSistema,
)