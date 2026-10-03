"""Agrega la sección 4.33 (motor contable) al MEMORIA.md."""

import io
import os

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MEMORIA.md")
)

SECCION = """
### 4.33 Motor contable: comprobantes, asientos y partida doble (02/10/2026)

El núcleo, en este orden y sin nada más:

```
COMPROBANTE INTERNO -> ASIENTO -> DETALLE -> PLAN DE CUENTAS
                    -> DEBE = HABER -> SALDOS
```

**Tres tablas nuevas** (`backend/migrar_motor_contable.py`, idempotente).
No se tocó ni se borró ninguna tabla existente.

#### `comprobantes_internos`
```sql
id_comprobante     INT AUTO_INCREMENT PK
codigo_comprobante VARCHAR(10) NOT NULL   -- AI, OP, RC, CO, TR, AJ
anio               SMALLINT NOT NULL
numero             INT      NOT NULL
fecha              DATE     NOT NULL
concepto           VARCHAR(200) NOT NULL
estado             VARCHAR(15) NOT NULL DEFAULT 'BORRADOR'
UNIQUE (codigo_comprobante, anio, numero)
```
El **código y el número van separados**. Se muestra `OP-000125`
(`numero_completo`, siempre 6 dígitos). El **correlativo se reinicia cada año**
(decidido el 02/10/2026), por eso el año está en la clave.

Los 6 códigos son **fijos** en el código del programa
(`CODIGOS_COMPROBANTE`), no hay tabla de tipos.

> OJO: esto NO es el `tipo_comprobante` de `facturas`/`compras`, que es el tipo
> **fiscal** (A, B, C...). No se mezclan.

#### `asientos`
```sql
id_asiento     INT AUTO_INCREMENT PK
id_comprobante INT NULL   -- puede haber asiento sin comprobante
fecha, concepto, estado (BORRADOR|CONTABILIZADO|ANULADO)
total_debe, total_haber  DECIMAL(16,4)
```
`total_debe` / `total_haber` son el **control del asiento**, no el saldo de una
cuenta: los calcula el sistema al guardar el detalle.

#### `asiento_detalle`
```sql
id_detalle, id_asiento (FK CASCADE), id_cuenta (FK RESTRICT a plan_cuentas)
debe, haber  DECIMAL(16,4)
tipo_auxiliar VARCHAR(30) NULL, id_auxiliar INT NULL   -- preparados, hoy en NULL
```

**Reglas del motor** (`app/services/asiento_service.py`):
1. Una línea solo va a una cuenta **imputable**. Un agrupador se rechaza con un
   mensaje que lo explica.
2. Importes negativos: no. Se elige en qué lado va.
3. Línea con debe=0 y haber=0: se ignora.
4. **No se contabiliza si el Debe no cierra con el Haber**: responde 400 diciendo
   cuánto falta y de qué lado.
5. Un asiento **CONTABILIZADO** no se puede volver a editar (409). Sí se puede
   pasar a BORRADOR con `/borrador`.
6. **ANULADO es terminal**: no vuelve ni a borrador ni a contabilizado.
7. Al contabilizar, el comprobante también pasa a CONTABILIZADO.

**Los saldos NO se guardan.** `GET /saldos` los calcula por SQL siempre.
- Por defecto devuelve **todas** las imputables (141), aunque estén en cero;
  con `?con_movimientos=true` solo las que se movieron.
- El `saldo` sale con el **signo de la naturaleza**: deudora → `debe - haber`,
  acreedora → `haber - debe`. Positivo = a favor (decidido el 02/10/2026).
- Solo entran asientos **CONTABILIZADO**.

**Control general** (`GET /control-general`): verifica que todo asiento
contabilizado tenga `debe = haber`. Si hay alguno que no cierra, lo dice
**cuál** (con su etiqueta `OP-000001` si tiene comprobante) y **por cuánto**.

**Bug que costó encontrar**: en el `LEFT JOIN` de los saldos, la condición del
`ON` se armaba con el `and` **de Python** entre dos expresiones de SQLAlchemy,
en vez de `and_()`. El filtro de "contabilizado" se perdía y **los asientos
anulados entraban en los saldos**. Con `and_()` el SQL queda
`LEFT OUTER JOIN asientos ON ... AND asientos.estado = 'CONTABILIZADO'` y además
el `SUM` va con `CASE WHEN asientos.id_asiento IS NOT NULL`, porque si se sumara
todo `asiento_detalle` también contarían los borradores.

**Endpoints** (`/api`): `comprobantes-internos` (GET/POST + `/codigos`),
`asientos` (GET/POST, `/asientos/{id}`, `/{id}/detalle` PUT, `/{id}/contabilizar`,
`/{id}/borrador`, `/{id}/anular`), `saldos`, `control-general`.

**Fuera de alcance (decidido el 02/10/2026)**: facturación, recibos, órdenes de
pago completas, IVA, cuentas corrientes, cierres de ejercicio, estados
contables, integración con ARCA y pantallas nuevas del frontend.

**Pruebas**: `test_motor_contable.py` (66) y `test_plan_cuentas.py` (38).
Las 18 suites del proyecto en verde (709 pruebas).
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if "### 4.33" in texto:
        print("La sección 4.33 ya está: no se toca nada")
        return

    marca = "\n## 7. Bugs / incidencias"
    if marca not in texto:
        raise SystemExit("No encontré el lugar para insertar 4.33")

    texto = texto.replace(marca, SECCION + marca, 1)

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("MEMORIA.md: agregada la sección 4.33")


if __name__ == "__main__":
    main()