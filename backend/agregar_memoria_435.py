import io
import os

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MEMORIA.md")
)

SECCION = """
### 4.35 Ejercicio del estudio, cuenta de cobro fija y mayores (02/10/2026)

Cierra el círculo de la contabilidad: el ejercicio que define hasta cuándo se
puede asentar, la cuenta donde entra la plata de los recibos, y los dos libros
para mirar lo ya asentado.

#### El ejercicio del ESTUDIO (tabla `ejercicios`)

Para esta empresa: **2026/2027, del 01/09/2026 al 31/08/2027**, abierto y
habilitado.

OJO, que esto se confunde con el ejercicio de cada cliente:

| | dónde | de quién |
|---|---|---|
| `ejercicios` | tabla nueva | del **estudio** (nosotros) |
| `bal_rt54_ejercicios` | la que ya existía | de **cada cliente** |

No tienen por qué coincidir. Verificado en la base: los clientes cierran el
29/02/2020, el 31/12/2025 y el 31/12/2026; el estudio, el 31/08/2027.

**Lo que arregla:** los documentos internos numeraban por AÑO CALENDARIO, así
que con un ejercicio de agosto a agosto el correlativo se partía al 1 de enero
(el 31/7/2027 sería FV-000200 y al día siguiente volvería a FV-000001). Ahora la
clave única es `(codigo_comprobante, id_ejercicio, numero)` y el número corre
corrido dentro del ejercicio.

```sql
CREATE TABLE ejercicios (
    id_ejercicio INT AUTO_INCREMENT PRIMARY KEY,
    nombre       VARCHAR(40) NOT NULL UNIQUE,   -- "2026/2027"
    fecha_inicio DATE         NOT NULL,
    fecha_fin    DATE         NOT NULL,
    cerrado      BOOLEAN      NOT NULL DEFAULT FALSE,
    creado       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado  DATETIME     NULL
) ENGINE=InnoDB;

ALTER TABLE comprobantes_internos ADD COLUMN id_ejercicio INT NULL AFTER anio;
ALTER TABLE comprobantes_internos DROP INDEX uq_comprobante;
ALTER TABLE comprobantes_internos
  ADD CONSTRAINT uq_comprobante UNIQUE (codigo_comprobante, id_ejercicio, numero);
```

La columna `anio` **se queda** (es el año de la fecha, para filtrar) pero ya no
participa de la numeración.

Si la fecha de una factura cae fuera de todo ejercicio abierto, **no se crea
el comprobante** y avisa cuál es el período habilitado. Un comprobante guardado
en el ejercicio equivocado después no se puede arreglar sin romper la
numeración.

Cerrar un ejercicio no exige que esté conciliado: es una trava para que nadie
meta movimientos abajo de una fecha cerrada sin darse cuenta.

#### La cuenta de cobro fija (tabla `config_sistema`)

El contador dijo que es fondo fijo. Entonces se configura **una vez** en
Configuración y el recibo no lo pregunta. Semilla: `1.1.01.03 Banco Nación –
Cuenta corriente`.

```sql
CREATE TABLE config_sistema (
    clave       VARCHAR(40) NOT NULL PRIMARY KEY,
    valor       VARCHAR(200) NOT NULL,
    descripcion VARCHAR(200) NULL,
    actualizado DATETIME NULL
) ENGINE=InnoDB;

-- La FK que faltaba (ver "bugs" abajo):
ALTER TABLE recibos
  ADD CONSTRAINT fk_recibo_cuenta_cobro
  FOREIGN KEY (cuenta_cobro_id) REFERENCES plan_cuentas (id_cuenta)
  ON DELETE RESTRICT ON UPDATE CASCADE;
```

Cada recibo **igual guarda la cuenta que usó**, así que cambiar la fija después
no reescribe los recibos viejos. Si algún día hay más de una, el recibo puede
traer la suya y gana esa.

#### Los mayores generales (`GET /mayores/{id_cuenta}`)

El libro de UNA cuenta: sus movimientos con el saldo acumulado línea por línea.
Es la diferencia contra `/saldos`, que da un número por cuenta.

El saldo sale con el signo de la naturaleza, y hay que recordarlo porque
sorprende: **Documentos a cobrar es DEUDORA** (es del Activo), no acreedora.
Después de vender 121.000 y cobrar 25.000 muestra **+96.000**. IVA a pagar, que
sí es acreedora, con 21.000 muestra **+21.000** "a favor".

El acumulado se arma en el backend recorriendo las líneas, y no con
`SUM() OVER` porque MySQL no tiene funciones de ventana. Los debe/haber de cada
línea y el total salen de SQL; el acumulado es irrestando sobre datos que ya
vienen de la base. El `saldo_final` se calcula por fórmula aparte, así también
sirve de control: el backend devuelve `cierra: true/false`.

#### Bugs que aparecieron

1. **Borrar una factura con asiento daba 500.** `asiento_origen` la referencia
   con `RESTRICT` y reventaba con un error de integridad sin explanation.
   Ahora avisa: *"La factura tiene el asiento FV-000003, que ya está
   contabilizado. Un asiento no se borra: anulalo desde la factura."*
2. **El backend entero daba 500 al agregar la relación `Recibo.cuenta_cobro`**
   sin FK: `Could not determine join condition... there are no foreign keys
   linking these tables`. Por eso el paso de agregar la FK.
3. **`PUT /ejercicios/cuenta-cobro-fija` daba 422**: FastAPI evalúa las rutas
   EN ORDEN, y `/{ejercicio_id}` estaba definida antes, así que
   "cuenta-cobro-fija" entraba por el parámetro y Pydantic lo leía como número.
   Las rutas fijas van **antes** de las que llevan `{parametro}`.
4. **Los tests dejaban clientes y asientos de prueba colgados**, y la corrida
   siguiente fallaba con "Ya existe Factura B 0001-00000042" o "El recibo ya
   tenía asiento". Ahora `correr_todas.py` llama al limpiador antes de correr.

#### Decisiones del usuario (02/10/2026)

1. El asiento se genera **automáticamente al dar de alta la factura**.
2. **Anular la factura NO anula el asiento**: son cosas separadas, con botones
   separados (Generar / Modificar / Anular asiento).
3. Desglose del IVA: se carga el **total + la alícuota** y el **backend** saca
   el neto y el IVA (nunca el navegador).
4. **El número se reinicia por ejercicio**, no por año calendario.
5. Ejercicio: **01/09/2026 → 31/08/2027**.
6. La cuenta de cobro es **fondo fijo**, configurada en Configuración.

**Archivos**: `migrar_ejercicios.py`, `app/models/ejercicio.py`,
`app/services/ejercicio_service.py`, `app/routers/ejercicios.py`,
`migrar_cuenta_cobro_fija.py`, `limpiar_clientes_prueba.py`,
`frontend/src/pages/EjercicioConfig.jsx`, `frontend/src/pages/Mayores.jsx`.

**Pruebas**: `test_ejercicio.py` (27), `test_mayor_cuenta_cobro.py` (30),
`test_asientos_automaticos.py` (43, actualizado). Las **22 suites en verde
(854 pruebas)**.

**Lo que falta**: los estilos de las pantallas de Asientos y Mayores están
hechos, pero falta probarlos en el navegador. Y la pantalla de Asientos no
muestra todavía el ejercicio vigente en el título.
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if "### 4.35" in texto:
        print("La sección 4.35 ya está: no se toca nada")
        return

    marca = "\n## 7. Bugs / incidencias"
    if marca not in texto:
        raise SystemExit("No encontré el lugar para insertar 4.35")

    texto = texto.replace(marca, SECCION + marca, 1)
    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)
    print("MEMORIA.md: agregada la sección 4.35")


if __name__ == "__main__":
    main()