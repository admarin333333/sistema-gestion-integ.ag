"""Agrega la sección 4.32 (plan de cuentas) al MEMORIA.md."""

import io
import os

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MEMORIA.md")
)

SECCION = """
### 4.32 Plan de cuentas RT54 — estructura contable (02/10/2026)

**Pedido:** crear la estructura contable **sin tocar** las pantallas de facturas,
recibos ni asientos, y **sin** el motor de asientos todavía.

Fuente: `C:\\estudio contable\\plan de cuentas.xlsx`.
- **Hoja2** = "PLAN DE CUENTAS - ESTRUCTURA RT 54" → es la que se cargó (185 cuentas).
- **Hoja1** = borrador viejo con otros códigos (`1.01`, `1.01.01`). No se usa.

**La tabla `plan_cuentas`** (`backend/migrar_plan_cuentas.py`):

```sql
CREATE TABLE plan_cuentas (
    id_cuenta        INT AUTO_INCREMENT PRIMARY KEY,
    codigo           VARCHAR(20)  NOT NULL UNIQUE,
    nombre           VARCHAR(150) NOT NULL,
    cuenta_padre_id  INT          NULL,      -- FK a plan_cuentas.id_cuenta
    nivel            INT          NOT NULL DEFAULT 1,
    imputable        BOOLEAN      NOT NULL DEFAULT FALSE,
    tipo_auxiliar    VARCHAR(30)  NULL,
    activa           BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_plan_cuentas_padre FOREIGN KEY (cuenta_padre_id)
        REFERENCES plan_cuentas(id_cuenta) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX ix_plan_cuentas_padre     (cuenta_padre_id),
    INDEX ix_plan_cuentas_codigo    (codigo),
    INDEX ix_plan_cuentas_imputable (imputable)
);
```

- **UNA sola tabla jerárquica.** No hay tablas para rubros, subrubros y cuentas.
  El nivel se deduce de cuántas partes tiene el código (1 = "1 ACTIVO",
  2 = "1.1 ACTIVO CORRIENTE", 3 = "1.1.01 Caja y bancos", 4 = la cuenta) y el
  vínculo con el padre es `cuenta_padre_id`, que va NULL en las 7 raíces.
- **imputable**: solo las hojas. Un rubro o agrupador es `imputable = FALSE` y
  sirve para agrupar en los informes. **Ni una sola** cuenta imputable tiene
  subcuentas (verificado en SQL).
- **tipo_auxiliar**: solo en las cuentas imputables — CLIENTE 19, BANCO 8,
  PROVEEDOR 4, NINGUNO el resto. No va en los grupos (decidido el 02/10/2026).

**Decisiones tomadas por el usuario (02/10/2026):**
1. Se carga solo Hoja2.
2. Las cuentas que venían sin código se numeran en orden bajo su grupo.
3. `tipo_auxiliar` va en las cuentas imputables, no en los grupos.
4. Si una cuenta no dice si es imputable, es imputable **si no tiene subcuentas**.

**Lo que hubo que arreglar del Excel** (por eso se revisó antes de cargar):
- 6 filas con el texto "ctas contables": son separadores, no cuentas.
- 1 fila de encabezado de columnas ("codigo | ... | imputable").
- 1 título de hoja ("PLAN DE CUENTAS - ESTRUCTURA RT 54").
- 25 cuentas de verdad sin código (Proveedores, IVA a pagar, Sueldos a pagar,
  Intereses ganados...). Se colgaron de su grupo y se numeraron: los códigos
  quedaron 2.1.01.01 Proveedores, 2.1.03.01 IVA a pagar, 7.1.01 Intereses
  ganados, etc.
- La fila `4.1 Ingresos por ventas` decía imputable=SÍ pero tiene la subcuenta
  `4.1.01`: quedó como grupo (imputable = FALSE).
- Los "typos" del Excel quedaron tal cual: `7.2.01` "resultado po tenencia" y
  `7.3.01` "recpam". Se pueden corregir desde la pantalla.

**Archivos:**
- NUEVO `backend/app/models/plan_cuenta.py` — modelo con las relaciones
  `hijas` / `padre`.
- MODIFICADO `backend/app/models/__init__.py` — solo registrar el modelo.
- NUEVO `backend/migrar_plan_cuentas.py` — `CREATE TABLE` + carga. **Idempotente**
  (`INSERT ... ON DUPLICATE KEY UPDATE`): se puede volver a correr sin duplicar.
  Tiene `--ver` para ver qué se va a cargar sin escribir nada.
- NUEVO `backend/analizar_plan_cuentas.py` — analiza el Excel y reporta los
  problemas (no escribe nada).

**Ojo con el vínculo a la propia tabla:** en `PlanCuenta` el `remote_side` va en
el lado **padre** (muchos-a-uno). Si se lo pone en `hijas`, las dos relaciones
quedan invertidas y `hijas` devuelve `None`.

**No se tocó:** ninguna pantalla de facturas, recibos, anticipos ni compras.
Ningún router. Ninguna tabla existente. 16/16 suites en verde (605 pruebas).
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if "### 4.32" in texto:
        print("La sección 4.32 ya está: no se toca nada")
        return

    marca = "\n## 7. Bugs / incidencias"
    if marca not in texto:
        raise SystemExit("No encontré el lugar para insertar 4.32")

    texto = texto.replace(marca, SECCION + marca, 1)

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("MEMORIA.md: agregada la sección 4.32")


if __name__ == "__main__":
    main()