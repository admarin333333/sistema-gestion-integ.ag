"""El núcleo del motor contable: comprobantes internos, asientos y su detalle.

Son 3 tablas nuevas. **No se modifica ni se borra ninguna de las que ya están.**

- `comprobantes_internos`: la cabecera numerada (AI-000125, OP-000007...).
- `asientos`: el asiento contable, con su estado.
- `asiento_detalle`: las cuentas que se mueven, con su importe en Debe o Haber.

Decisiones del usuario (02/10/2026):
- El **número correlativo se reinicia cada año**: en 2027 el próximo OP vuelve a
  ser OP-000001. Por eso el único es (codigo, anio, numero).
- **El saldo no se guarda**: se calcula siempre por SQL sobre los asientos
  contabilizados. Ninguna tabla tiene columna `saldo`.
- Los auxiliares van en **dos columnas** de `asiento_detalle`
  (`tipo_auxiliar` + `id_auxiliar`), hoy en NULL.
- Los 6 códigos (AI, OP, RC, CO, TR, AJ) son fijos y están en el código del
  programa: no hay tabla de tipos de comprobante.

Ojo: esto NO es lo mismo que el `tipo_comprobante` de las facturas, que es el
tipo **fiscal** (A, B, C...). Acá son los internos.

Uso:  python -X utf8 migrar_motor_contable.py
"""

from sqlalchemy import text

from app.database import engine

SQL_COMPROBANTES = """
CREATE TABLE IF NOT EXISTS comprobantes_internos (
    id_comprobante     INT AUTO_INCREMENT PRIMARY KEY,

    -- Código interno: AI, OP, RC, CO, TR, AJ. Separado del número para poder
    -- filtrar por tipo sin leer texto.
    codigo_comprobante VARCHAR(10) NOT NULL,

    -- El número se reinicia cada año, así que el año va en la clave.
    anio   SMALLINT NOT NULL,
    numero INT      NOT NULL,

    fecha    DATE        NOT NULL,
    concepto VARCHAR(200) NOT NULL,
    estado   VARCHAR(15) NOT NULL DEFAULT 'BORRADOR',

    CONSTRAINT uq_comprobante UNIQUE (codigo_comprobante, anio, numero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SQL_ASIENTOS = """
CREATE TABLE IF NOT EXISTS asientos (
    id_asiento     INT AUTO_INCREMENT PRIMARY KEY,

    -- Puede haber asientos sin comprobante (por ejemplo, uno de ajuste
    -- interno). Por eso es NULL y no obligatorio.
    id_comprobante INT NULL,

    fecha    DATE        NOT NULL,
    concepto VARCHAR(200) NOT NULL,

    -- BORRADOR -> se puede editar | CONTABILIZADO -> ya suma a los saldos
    -- y no se toca | ANULADO -> queda fuera de los saldos
    estado VARCHAR(15) NOT NULL DEFAULT 'BORRADOR',

    -- Suma de Debe y de Haber del detalle. Se recalcula al guardar el detalle,
    -- NO se carga a mano: no es el saldo de la cuenta, es el control del
    -- asiento. El saldo de cada cuenta nunca se guarda.
    total_debe  DECIMAL(16,4) NOT NULL DEFAULT 0,
    total_haber DECIMAL(16,4) NOT NULL DEFAULT 0,

    CONSTRAINT fk_asiento_comprobante FOREIGN KEY (id_comprobante)
        REFERENCES comprobantes_internos(id_comprobante)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SQL_DETALLE = """
CREATE TABLE IF NOT EXISTS asiento_detalle (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    id_asiento INT NOT NULL,
    id_cuenta  INT NOT NULL,

    -- Importe del movimiento en cada lado. Con 4 decimales para los índices y
    -- coeficientes que maneja el estudio.
    debe  DECIMAL(16,4) NOT NULL DEFAULT 0,
    haber DECIMAL(16,4) NOT NULL DEFAULT 0,

    -- Preparado para los auxiliares (todavía en NULL):
    -- tipo_auxiliar = CLIENTE | PROVEEDOR | BANCO
    -- id_auxiliar   = el id del cliente / proveedor / banco
    tipo_auxiliar VARCHAR(30) NULL,
    id_auxiliar   INT          NULL,

    CONSTRAINT fk_detalle_asiento FOREIGN KEY (id_asiento)
        REFERENCES asientos(id_asiento)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_detalle_cuenta FOREIGN KEY (id_cuenta)
        REFERENCES plan_cuentas(id_cuenta)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

INDICES = [
    "CREATE INDEX ix_comprobantes_fecha ON comprobantes_internos(fecha)",
    "CREATE INDEX ix_comprobantes_estado ON comprobantes_internos(estado)",
    "CREATE INDEX ix_asientos_comprobante ON asientos(id_comprobante)",
    "CREATE INDEX ix_asientos_fecha ON asientos(fecha)",
    "CREATE INDEX ix_asientos_estado ON asientos(estado)",
    "CREATE INDEX ix_detalle_asiento ON asiento_detalle(id_asiento)",
    "CREATE INDEX ix_detalle_cuenta ON asiento_detalle(id_cuenta)",
    "CREATE INDEX ix_detalle_auxiliar ON asiento_detalle(tipo_auxiliar, id_auxiliar)",
]

# Marcas de tiempo. En un libro contable importa saber cuándo se cargó y cuándo
# se tocó cada cosa, así que van en las dos cabeceras.
FECHAS = {
    "comprobantes_internos": [
        "ADD COLUMN creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ADD COLUMN actualizado DATETIME NULL",
    ],
    "asientos": [
        "ADD COLUMN creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ADD COLUMN actualizado DATETIME NULL",
    ],
}


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


def main():
    with engine.begin() as conn:
        for sql in (SQL_COMPROBANTES, SQL_ASIENTOS, SQL_DETALLE):
            conn.execute(text(sql))
            print("  tabla creada")

        for tabla, columnas in FECHAS.items():
            for alt in columnas:
                # "ADD COLUMN creado DATETIME ..." -> creado
                nombre = alt.split()[2]
                if not _tiene_columna(conn, tabla, nombre):
                    conn.execute(text(f"ALTER TABLE {tabla} {alt}"))
                    print(f"  {tabla}: {nombre}")

        # Los índices se crean aparte porque MySQL no los admite dentro de
        # CREATE TABLE, y no tiene CREATE INDEX IF NOT EXISTS: se chequea antes.
        for sql in INDICES:
            # "CREATE INDEX ix_nombre ON tabla(...)" -> ix_nombre
            nombre = sql.split()[2]
            existe = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND index_name = :i"
                ),
                {"i": nombre},
            ).scalar()
            if not existe:
                conn.execute(text(sql))
                print(f"  índice {nombre}")

    with engine.connect() as conn:
        print("\nTablas del motor contable:")
        for t in ("comprobantes_internos", "asientos", "asiento_detalle"):
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = :t"
                ),
                {"t": t},
            ).scalar()
            filas = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:<24} existe={bool(n)}  filas={filas}")


if __name__ == "__main__":
    main()