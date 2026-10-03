"""Agrega la sección 4.34 (asientos automáticos) al MEMORIA.md."""

import io
import os

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MEMORIA.md")
)

SECCION = """
### 4.34 Asientos automáticos desde facturas y recibos (02/10/2026)

Conecta la facturación con el motor contable. **Dos asientos por operación**:

```
Cargar factura  ->  Asiento 1:  DEBE  Documentos a cobrar
                               HABER Ingresos por servicios
                               HABER IVA a pagar
Aplicar recibo  ->  Asiento 2:  DEBE  Caja / Banco
                               HABER Documentos a cobrar
```

#### Cambios en las tablas que ya existían
```sql
ALTER TABLE facturas
  ADD COLUMN tipo_operacion     VARCHAR(12) NOT NULL DEFAULT 'SERVICIOS',
  ADD COLUMN neto               DECIMAL(16,4) NULL,
  ADD COLUMN iva                DECIMAL(16,4) NULL,
  ADD COLUMN alicuota_iva_id         INT NULL,
  ADD COLUMN alicuota_iva_aplicada   DECIMAL(6,2) NULL;
ALTER TABLE recibos
  ADD COLUMN cuenta_cobro_id INT NULL;
```
`importe` **no se toca**: sigue siendo el total, y la regla es
`importe = neto + iva`. Por eso los recibos, el estado de cuenta y los informes
que ya funcionaban no se rompieron.

#### Tres tablas nuevas
- **`config_comprobantes`** — los **8** códigos internos: AI, AB, OP, RC, CO,
  TR, AJ, FV. Con la columna `origen` (FACTURA / RECIBO / MANUAL / NULL), que es
  lo que le dice al sistema qué comprobante va con qué registro. **Cada código
  numera por su cuenta**, así que "numeración diferente" sale del UNIQUE
  (codigo, anio, numero): la factura es FV-000001 y el recibo RC-000001.
  Se Dougan de tabla, no en el código, porque las descripciones las inventé yo
  y porque se pueden agregar códigos sin tocar el programa.
- **`config_asientos`** — qué cuenta va en cada caso (5 filas: 4 de venta por
  servicio/artículo × contado/crédito, más COBRANZA). **Es una tabla**: cambiar
  "Documentos a cobrar" por "Clientes" es un cambio de datos.
- **`asiento_origen`** — de qué registro salió el asiento. Los **dos UNIQUE**
  (`origen, id_factura` y `origen, id_recibo`) son los que impiden asentar dos
  veces lo mismo, y también sirven para anular la factura junto con su asiento.

#### Decisiones del usuario (02/10/2026)
1. Código nuevo **AB**, genérico, para los asientos manuales.
2. **Factura y recibo con código y numeración distintos.**
3. Servicios o artículos: **columna nueva** en la factura.
4. **El IVA va en el asiento** (desglosarlo en la factura). OJO: esto es
   *asentar* el IVA; las declaraciones de IVA siguen sin tocarse.
5. **Los dos asientos**: al cargar la factura y al aplicar el recibo.
6. **En qué cuenta entró la plata se elige al cargar el recibo**
   (`cuenta_cobro_id`), porque con 4 bancos la forma de pago no alcanza.
7. **Un asiento por recibo** (con un Haber por factura aplicada), y se genera
   **en el momento de aplicar**, aunque la factura quede parcial.

#### Comportamientos que conviene conocer
- **Sin IVA cargado** el asiento igual se genera, con el importe entero a
  ingresos y un aviso: si el contador se equivoca al desglosar, no puede
  dejar de facturar.
- **Factura o recibo anulado** → no genera asiento.
- El asiento se **contabiliza solo**: una factura emitida es un hecho.
- La línea del Debe de la venta lleva el auxiliar **CLIENTE**, para que el
  saldo de cada cliente quede separado.

**Archivos**: `migrar_asientos_automaticos.py`, `app/services/asiento_automatico.py`,
`app/models/asiento_origen.py`, y los modelos `factura.py` / `recibo.py`.
`asiento_service.crear_comprobante` ahora valida contra `config_comprobantes`
(no contra la constante `CODIGOS_COMPROBANTE`), con fallback a la lista de
fábrica para bases viejas.

**Pruebas**: `test_asientos_automaticos.py` (45) y `test_motor_contable.py`
(69, actualizado a 8 códigos). 19 suites en verde (758 pruebas).

**Lo que falta para que se use**: la pantalla. Hoy la generación se dispara
desde el service, no desde la pantalla de facturas ni desde la de recibos, y la
columna `cuenta_cobro_id` todavía no está en el formulario de recibo.
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if "### 4.34" in texto:
        print("La sección 4.34 ya está: no se toca nada")
        return

    marca = "\n## 7. Bugs / incidencias"
    if marca not in texto:
        raise SystemExit("No encontré el lugar para insertar 4.34")

    texto = texto.replace(marca, SECCION + marca, 1)

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("MEMORIA.md: agregada la sección 4.34")


if __name__ == "__main__":
    main()