"""Asientos automáticos: el vínculo entre facturación y el motor contable.

Agrega:
- a `facturas`: qué tipo de operación es y cómo se desglosa el IVA.
- a `recibos`: en qué cuenta entró la plata (`cuenta_cobro_id`).
- `config_asientos`: qué cuenta va en cada caso. **Es una tabla, no código**:
  cambiar una cuenta es un cambio de datos.
- `config_comprobantes`: los 8 códigos internos, con su descripción.
- `asiento_origen`: de qué registro salió cada asiento (para no duplicar y
  para anular junto).

`importe` de las facturas **no se toca**: sigue siendo el total facturado, y
la regla queda `importe = neto + iva`. Así los recibos, el estado de cuenta y
los informes que ya funcionan no se rompen.

Uso:  python -X utf8 migrar_asientos_automaticos.py
"""

from sqlalchemy import text

from app.database import engine

# ---------------------------------------------------------------- columnas

COLUMNAS_FACTURA = [
    ("tipo_operacion", "VARCHAR(12) NOT NULL DEFAULT 'SERVICIOS'"),
    ("neto", "DECIMAL(16,4) NULL"),
    ("iva", "DECIMAL(16,4) NULL"),
    ("alicuota_iva_id", "INT NULL"),
    ("alicuota_iva_aplicada", "DECIMAL(6,2) NULL"),
]

COLUMNAS_RECIBO = [
    ("cuenta_cobro_id", "INT NULL"),
]

# ---------------------------------------------------------------- tablas

SQL_CONFIG_ASIENTOS = """
CREATE TABLE IF NOT EXISTS config_asientos (
    id_config            INT AUTO_INCREMENT PRIMARY KEY,
    clave                VARCHAR(40)  NOT NULL UNIQUE,
    nombre               VARCHAR(100) NOT NULL,
    -- El Debe: a dónde entra la plata (caja, banco o documentos a cobrar).
    cuenta_debe           INT NULL,
    -- El Haber de ingresos (ventas de artículos / ingresos por servicios).
    cuenta_haber_ingresos INT NULL,
    -- El Haber del IVA.
    cuenta_haber_iva      INT NULL,
    -- Solo para COBRANZA: la cuenta a la que va el Haber (documentos a cobrar).
    cuenta_haber_cobranza INT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_cfg_debe     FOREIGN KEY (cuenta_debe)
        REFERENCES plan_cuentas(id_cuenta) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_cfg_ingresos FOREIGN KEY (cuenta_haber_ingresos)
        REFERENCES plan_cuentas(id_cuenta) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_cfg_iva      FOREIGN KEY (cuenta_haber_iva)
        REFERENCES plan_cuentas(id_cuenta) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_cfg_cobranza FOREIGN KEY (cuenta_haber_cobranza)
        REFERENCES plan_cuentas(id_cuenta) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SQL_CONFIG_COMPROBANTES = """
CREATE TABLE IF NOT EXISTS config_comprobantes (
    id_comprobante_tipo INT AUTO_INCREMENT PRIMARY KEY,
    codigo  VARCHAR(10)  NOT NULL UNIQUE,
    nombre  VARCHAR(100) NOT NULL,
    -- FACTURA | RECIBO | NULL (si no se genera desde ningún registro)
    origen  VARCHAR(20) NULL,
    activa  BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SQL_ASIENTO_ORIGEN = """
CREATE TABLE IF NOT EXISTS asiento_origen (
    id_origen  INT AUTO_INCREMENT PRIMARY KEY,
    id_asiento INT NOT NULL,
    origen     VARCHAR(20) NOT NULL,
    id_factura INT NULL,
    id_recibo  INT NULL,

    -- Los dos UNIQUE son los que impiden asentar dos veces lo mismo.
    CONSTRAINT uq_origen_factura UNIQUE (origen, id_factura),
    CONSTRAINT uq_origen_recibo  UNIQUE (origen, id_recibo),

    CONSTRAINT fk_origen_asiento FOREIGN KEY (id_asiento)
        REFERENCES asientos(id_asiento) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_origen_factura FOREIGN KEY (id_factura)
        REFERENCES facturas(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_origen_recibo FOREIGN KEY (id_recibo)
        REFERENCES recibos(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# ---------------------------------------------------------------- semillas

# Los 8 códigos internos. Cada uno numera por su cuenta: la clave única del
# comprobante es (codigo, anio, numero), así que "numeración diferente" sale
# solo. `origen` le dice al sistema de qué registro se genera cada uno.
CODIGOS = [
    ("AI", "Asiento Inicial", None),
    ("AB", "Asiento en blanco (manual)", "MANUAL"),
    ("FV", "Factura de venta", "FACTURA"),
    ("RC", "Recibo de Cobranza", "RECIBO"),
    ("OP", "Orden de Pago", None),
    ("CO", "Comprobante de Egreso", None),
    ("TR", "Transferencia", None),
    ("AJ", "Asiento de Ajuste", None),
]


def _tiene_columna(conn, tabla: str, columna: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "AND column_name = :c"
            ),
            {"t": tabla, "c": columna},
        ).scalar()
    )


def _id_cuenta(conn, codigo: str):
    return conn.execute(
        text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"),
        {"c": codigo},
    ).scalar()


def main():
    with engine.begin() as conn:
        # --- columnas ---
        for tabla, cols in (("facturas", COLUMNAS_FACTURA), ("recibos", COLUMNAS_RECIBO)):
            for nombre, tipo in cols:
                if not _tiene_columna(conn, tabla, nombre):
                    conn.execute(
                        text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
                    )
                    print(f"  {tabla}.{nombre}")

        # --- tablas ---
        for sql in (SQL_CONFIG_ASIENTOS, SQL_CONFIG_COMPROBANTES, SQL_ASIENTO_ORIGEN):
            conn.execute(text(sql))
            print("  tabla creada")

        # --- los 8 códigos internos ---
        for codigo, nombre, origen in CODIGOS:
            conn.execute(
                text(
                    "INSERT INTO config_comprobantes (codigo, nombre, origen) "
                    "VALUES (:c, :n, :o) "
                    "ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), "
                    "origen = VALUES(origen)"
                ),
                {"c": codigo, "n": nombre, "o": origen},
            )
        print(f"  {len(CODIGOS)} códigos internos cargados")

        # --- qué cuenta va en cada caso ---
        # Las cuentas salen del código del plan, así que el seed se arma con
        # _id_cuenta y no con id fijos: así funciona en cualquier base.
        ING_SERVICIOS = _id_cuenta(conn, "4.2.01")   # Ingresos por servicios
        ING_ARTICULOS = _id_cuenta(conn, "4.1.01")   # Ventas artículos
        IVA_PAGAR = _id_cuenta(conn, "2.1.03.01")    # IVA a pagar
        DOC_COBRAR = _id_cuenta(conn, "1.1.03.02")  # Documentos a cobrar
        BANCO = _id_cuenta(conn, "1.1.01.03")        # Banco Nación cta cte
        # **No hay cuenta de Caja para las ventas.** Una factura es una deuda
        # del cliente, no plata recibida: va a Documentos a cobrar SIEMPRE,
        # al contado o a cuenta corriente. La plata entra en Caja o Banco
        # recién en tesorería, cuando se registra el cobro.

        faltantes = []
        for codigo, nombre, _ in CODIGOS:
            if codigo in ("FV", "RC") and _id_cuenta(conn, "1.1.03.02") is None:
                faltantes.append(codigo)
        if faltantes:
            raise SystemExit(
                "No encontré una cuenta clave del plan de cuentas. "
                "Cargá el plan primero (migrar_plan_cuentas.py)."
            )

        CONFIG = [
            # clave, nombre, debe, haber ingresos, haber iva, haber cobranza
            # El Debe es SIEMPRE Documentos a cobrar (con el cliente como
            # auxiliar), en las cuatro combinaciones. La diferencia entre
            # contado y cuenta corriente no está en la cuenta: una venta al
            # contado también genera deuda, se cobre después con un recibo.
            ("VENTA_SERVICIOS_CONTADO", "Venta de servicios al contado",
             DOC_COBRAR, ING_SERVICIOS, IVA_PAGAR, None),
            ("VENTA_SERVICIOS_CTA_CORRIENTE", "Venta de servicios a cuenta corriente",
             DOC_COBRAR, ING_SERVICIOS, IVA_PAGAR, None),
            ("VENTA_ARTICULOS_CONTADO", "Venta de artículos al contado",
             DOC_COBRAR, ING_ARTICULOS, IVA_PAGAR, None),
            ("VENTA_ARTICULOS_CTA_CORRIENTE", "Venta de artículos a cuenta corriente",
             DOC_COBRAR, ING_ARTICULOS, IVA_PAGAR, None),
            # En la cobranza el Debe lo dice el recibo (cuenta_cobro_id), así que
            # acá solo va la cuenta del Haber.
            ("COBRANZA", "Cobranza de facturas",
             None, None, None, DOC_COBRAR),
        ]
        for clave, nombre, debe, hab_ing, hab_iva, hab_cob in CONFIG:
            conn.execute(
                text(
                    "INSERT INTO config_asientos "
                    "(clave, nombre, cuenta_debe, cuenta_haber_ingresos, "
                    " cuenta_haber_iva, cuenta_haber_cobranza, activa) "
                    "VALUES (:k, :n, :d, :i, :v, :c, 1) "
                    "ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), "
                    "cuenta_debe = VALUES(cuenta_debe), "
                    "cuenta_haber_ingresos = VALUES(cuenta_haber_ingresos), "
                    "cuenta_haber_iva = VALUES(cuenta_haber_iva), "
                    "cuenta_haber_cobranza = VALUES(cuenta_haber_cobranza)"
                ),
                {"k": clave, "n": nombre, "d": debe, "i": hab_ing,
                 "v": hab_iva, "c": hab_cob},
            )
        print(f"  {len(CONFIG)} configuraciones de asiento cargadas")

    # ------------------------------------------------------------ resumen
    with engine.connect() as conn:
        print("\nconfig_comprobantes:")
        for r in conn.execute(
            text("SELECT codigo, nombre, origen FROM config_comprobantes ORDER BY codigo")
        ):
            print(f"  {r[0]:<4} {r[1]:<32} origen: {r[2] or '-'}")

        print("\nconfig_asientos:")
        for r in conn.execute(
            text(
                "SELECT c.clave, c.cuenta_debe, di.codigo, "
                "       c.cuenta_haber_ingresos, hi.codigo, "
                "       c.cuenta_haber_iva, hv.codigo, "
                "       c.cuenta_haber_cobranza, hc.codigo "
                "FROM config_asientos c "
                "LEFT JOIN plan_cuentas di ON di.id_cuenta = c.cuenta_debe "
                "LEFT JOIN plan_cuentas hi ON hi.id_cuenta = c.cuenta_haber_ingresos "
                "LEFT JOIN plan_cuentas hv ON hv.id_cuenta = c.cuenta_haber_iva "
                "LEFT JOIN plan_cuentas hc ON hc.id_cuenta = c.cuenta_haber_cobranza "
                "ORDER BY c.clave"
            )
        ):
            print(
                f"  {r[0]:<30} debe={r[2] or '-':<12} "
                f"ingresos={r[4] or '-':<12} iva={r[6] or '-':<12} cobranza={r[8] or '-'}"
            )


if __name__ == "__main__":
    main()