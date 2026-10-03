"""A qué cuenta va cada FORMA DE PAGO de un recibo.

    python -X utf8 migrar_cuentas_forma_pago.py [--ver]

## El problema que resuelve

El recibo tiene una sola cuenta de cobro, configurada a mano en
`config_sistema` (`cuenta_cobro_fija`), y el mismo para todos: 38 recibos en
efectivo fueron a `1.1.01.01 Caja` y 25 transferencias a `1.1.01.03 Banco
Nación`, aunque la mitad de esas transferencias fueron de otro banco. El
contador elige la forma de pago pero **la cuenta no sale de ahí**.

## Lo que se arma

Una tabla con la cuenta que corresponde a cada forma de pago. Es DATO, no código,
por eso está en tabla: si el estudio cambia de banco, se cambia acá.

| Forma de pago | Cuenta |
|---|---|
| efectivo | `1.1.01.02 Fondo fijo` — el efectivo del mostrador |
| cheque | `1.1.01.10 Valores a depositar` — hasta que se deposita |
| tarjeta_credito | `1.1.01.09 Fondos en plataformas de cobro` |
| transferencia | se elige el banco (tiene `cuenta = NULL`) |
| tarjeta_debito | se elige el banco (tiene `cuenta = NULL`) |

**Lo que va con `cuenta = NULL` necesita que el contador elija el banco** en el
formulario del recibo. Sin eso no hay cuenta del Debe y el asiento no se puede
armar, así que el backend avisa en vez de asentar a una cuenta inventada.

El Haber siempre es `1.1.03.02 Documentos a cobrar`, con el cliente como
auxiliar. Eso NO se configura acá porque es el mismo para todos los cobros: es
la deuda que se cancela.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv

FONDOS_FIJO = "1.1.01.02"
VALORES = "1.1.01.10"
PLATAFORMAS = "1.1.01.09"

SQL = """\
CREATE TABLE IF NOT EXISTS config_cuentas_forma_pago (
    forma_pago     VARCHAR(20) NOT NULL PRIMARY KEY,
    cuenta_id      INT NULL,          -- NULL = el contador elige el banco
    requiere_banco BOOLEAN NOT NULL DEFAULT FALSE,
    descripcion    VARCHAR(200) NULL,
    CONSTRAINT fk_config_fp_cuenta
        FOREIGN KEY (cuenta_id) REFERENCES plan_cuentas (id_cuenta)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

INSERT INTO config_cuentas_forma_pago
    (forma_pago, cuenta_id, requiere_banco, descripcion) VALUES
    ('efectivo',          <1.1.01.02 Fondo fijo>,           FALSE, 'El efectivo del mostrador va al fondo fijo'),
    ('cheque',            <1.1.01.10 Valores a depositar>,   FALSE, 'El cheque se asienta hasta que se deposita'),
    ('tarjeta_credito',   <1.1.01.09 Plataformas de cobro>,  FALSE, 'La tarjeta de crédito entra por la plataforma'),
    ('transferencia',     NULL,                               TRUE,  'Elegí el banco de la cuenta corriente'),
    ('tarjeta_debito',    NULL,                               TRUE,  'Elegí el banco de la cuenta corriente'),
    ('otro',              NULL,                               TRUE,  'Contá por dónde entró la plata');
"""

print("SQL que se va a aplicar:\n")
print(SQL)

# Las tres cuentas que van fijas. El resto se resuelve en el formulario.
FIJAS = {
    "efectivo": FONDOS_FIJO,
    "cheque": VALORES,
    "tarjeta_credito": PLATAFORMAS,
}


def id_de(conn, codigo):
    return conn.execute(
        text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"), {"c": codigo}
    ).scalar()


with engine.connect() as conn:
    cuentas = {c: id_de(conn, c) for c in (FONDOS_FIJO, VALORES, PLATAFORMAS)}
print(f"cuentas del plan: {cuentas}")
faltan = [c for c, i in cuentas.items() if i is None]
if faltan:
    raise SystemExit(
        f"Faltan cuentas del plan: {', '.join(faltan)}. "
        "Cargá el plan primero (migrar_plan_cuentas.py)."
    )

if VER:
    print("\n--ver: no se aplicó nada.")
    raise SystemExit(0)

DESCRIPCIONES = {
    "efectivo": "El efectivo del mostrador va al fondo fijo",
    "cheque": "El cheque se asienta hasta que se deposita",
    "tarjeta_credito": "La tarjeta de crédito entra por la plataforma",
    "transferencia": "Elegí el banco de la cuenta corriente",
    "tarjeta_debito": "Elegí el banco de la cuenta corriente",
    "otro": "Contá por dónde entró la plata",
}

with engine.begin() as conn:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS config_cuentas_forma_pago ("
            "  forma_pago     VARCHAR(20) NOT NULL PRIMARY KEY,"
            "  cuenta_id      INT NULL,"
            "  requiere_banco BOOLEAN NOT NULL DEFAULT FALSE,"
            "  descripcion    VARCHAR(200) NULL,"
            "  CONSTRAINT fk_config_fp_cuenta"
            "    FOREIGN KEY (cuenta_id) REFERENCES plan_cuentas (id_cuenta)"
            "    ON DELETE RESTRICT ON UPDATE CASCADE"
            ") ENGINE=InnoDB"
        )
    )

    for forma, desc in DESCRIPCIONES.items():
        # Las de cuenta fija usan el id del plan; las que requieren banco
        # quedan en NULL, y el backend avisa si no se eligió.
        cuenta = cuentas[FIJAS[forma]] if forma in FIJAS else None
        requiere = forma not in FIJAS
        conn.execute(
            text(
                "INSERT INTO config_cuentas_forma_pago "
                "  (forma_pago, cuenta_id, requiere_banco, descripcion) "
                "VALUES (:f, :c, :r, :d) "
                "ON DUPLICATE KEY UPDATE cuenta_id = VALUES(cuenta_id), "
                "  requiere_banco = VALUES(requiere_banco), "
                "  descripcion = VALUES(descripcion)"
            ),
            {"f": forma, "c": cuenta, "r": requiere, "d": desc},
        )

print("\n--- cómo quedó ---")
with engine.connect() as conn:
    for r in conn.execute(
        text(
            "SELECT c.forma_pago, c.requiere_banco, p.codigo, p.nombre, c.descripcion "
            "  FROM config_cuentas_forma_pago c "
            "  LEFT JOIN plan_cuentas p ON p.id_cuenta = c.cuenta_id "
            " ORDER BY c.requiere_banco, c.forma_pago"
        )
    ):
        donde = r[2] or "ELEGIR EL BANCO"
        print(f"  {r[0]:<16} {donde:<32} {r[4]}")

print("\nListo. Falta que el recibo use esto y genere su asiento.")