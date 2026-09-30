# MEMORIA.md — Proyecto 2: Sistema de gestión estudio contable

Estado, alcance y decisiones. **Leer al empezar cada sesión.**

> **Última actualización:** 30/09/2026
> **Fuente del alcance:** especificación escrita por el cliente el 30/09/2026
> **Producto relacionado:** web pública en `fiverr/portfolio/contable/` (Proyecto 1)

---

## 1. Estado actual

### Fases de construcción

| Fase | Qué incluye | Estado |
|---|---|---|
| **0** | Carpeta + `AGENTE.md` + `MEMORIA.md` | ✅ Hecha |
| **1** | Estructura + MySQL + modelo de datos + **login + 2 usuarios con rol** | ✅ **Hecha** (backend + frontend, 10/10 pruebas) |
| **2** | **Clientes**: CRUD + validaciones + servicios contratados + observaciones + sugerencias | ✅ **Hecha** (backend 56/56 · frontend probado en navegador) |
| **3** | **Facturas + Recibos + cuenta corriente** | ⬜ |
| **4** | **Dashboard + alertas de vencimiento** | ⬜ |
| **5** | **PDF e impresión** (factura, recibo, estado de cuenta, informe) | ⬜ |
| **6** | Preparación **ARCA** (sin conectar) | ⬜ |
| **7** | Dejar **posible subir a Vercel** | ⬜ |

### Infraestructura verificada (30/09/2026)

| Cosa | Estado |
|---|---|
| Carpeta `C:\proyecto-gestion-contable` | ✅ creada |
| Python 3.12.5 + pip 24.2 | ✅ |
| Node v20.17.0 + npm 10.8.2 | ✅ |
| **MySQL Server 8.0.43** (`C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe`) | ✅ **puerto 3307**, servicio `MySQL_Server` — el 3306 es **otra instancia (`Mysql80`), no tocar** |
| XAMPP `mysql.exe` | ❌ **falla** contra MySQL 8 (le falta `caching_sha2_password.dll`) |
| Git 2.45.2 | ✅ |
| MySQL en el PATH de PowerShell | ❌ usar ruta completa + `-proot` (nunca `-p` solo, se cuelga) |
| **Base `gestion_contable`** | ✅ (utf8mb4) con **5 tablas**: `usuarios` · `clientes` · `servicios` · `cliente_servicio` · `sugerencias` |
| **API FastAPI** | 🟡 `http://127.0.0.1:8010` — **el 8000 estaba ocupado** por un proceso de OpenCode (PID 37384, no tocar) |

### Usuarios de prueba

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | Admin — todo |
| `operador` | `operador123` | Operador — carga, no borra ni anula |

---

## 2. Resumen del producto

Sistema para un **estudio contable**, con:

- **Web pública** (ya hecha) + **área administrativa**
- Login con **2 usuarios** y **rol** (Admin / Operador)
- Carga y consulta de **clientes** (individual y por lote)
- **Facturación** y **recibos**
- **Cuenta corriente** con saldo e impresión
- **Dashboard** con KPIs y alertas de vencimiento
- Arquitectura preparada para **ARCA** (esta versión no conecta)

---

## 3. Decisiones

| Tema | Decisión | Fecha |
|---|---|---|
| Carpeta del proyecto | `C:\proyecto-gestion-contable` | 30/09/2026 |
| Dónde corre | **Todo local** — BD y sistema en la PC del cliente | 30/09/2026 |
| Roles | **Admin + Operador** | 30/09/2026 |
| Vercel | Que **sea posible** subirlo a futuro; hoy **no** se sube | 30/09/2026 |
| Web pública | Reutilizar `fiverr/portfolio/contable/`, **no rehacer** | 30/09/2026 |
| ARCA | Preparar la arquitectura, **sin conectar** | 30/09/2026 |
| Avance | **Una fase por vez**, aprobada por el cliente | 30/09/2026 |

### Roles definidos

| Rol | Puede | No puede |
|---|---|---|
| **Admin** | Todo: crear, editar, borrar, anular, ver informes y dashboard | — |
| **Operador** | Cargar y editar clientes, facturas y recibos | Borrar, anular, ver informes |

---

## 4. Alcance — especificación completa

### 4.1 Pantalla principal
- Ingresar con **usuario y contraseña**.
- Mostrar **la fecha de hoy**.
- Menú para cargar, consultar y listar clientes.

### 4.2 Clientes — campos

| Campo | Regla |
|---|---|
| Número de cuenta | **autoincremental** |
| Nombre | obligatorio |
| Apellido / Razón social | obligatorio |
| CUIT | formato válido · **sin duplicados** |
| DNI | **solo números** (rechazar letras y símbolos) · **sin duplicados** |
| Email | formato válido — **rechazar los que no tienen `@`** |
| **Código de área** | solo números (2 a 5 dígitos) · opcional · **está en las dos personas** |
| **Teléfono** | solo números (4 a 11 dígitos) · opcional · **está en las dos personas** |
| Domicilio | |
| Localidad | se **completa sola** al cargar el código postal (§4.14) · siempre editable |
| **Código postal** | 4 dígitos · opcional · al completarlo rellena localidad y provincia |
| Provincia | |
| Fecha de alta al sistema | automática |
| **Tipo de persona** | física · jurídica |
| **Actividad económica** | profesional · comercio · industria · cabañas · inmobiliaria · servicios |
| **Tipo de actividad** | monotributista · responsable inscripto · autónomo · cooperativas · asociaciones civiles |
| **Observaciones** | pestaña con la descripción del servicio que solicita el cliente |

- Los **campos obligatorios** deben verse **claramente identificados** en la UI.
- Consulta de **un cliente** o de **lote de clientes**.

### 4.3 Servicios contratados
Un cliente puede tener **varios a la vez** (agregar más de uno):

`Monotributo` · `IVA` · `Ganancias` · `Autónomos` · `Facturación` · `Sueldos` · `Contabilidad` · `Auditoría` · `Liquidaciones` · `Otros`

### 4.4 Facturas

| Campo | Detalle |
|---|---|
| ID | |
| Cliente | |
| Fecha | |
| Tipo de comprobante | |
| Punto de venta | |
| Número | |
| Concepto | |
| Importe | |
| Fecha de vencimiento | |
| **Condición de venta** | Contado · Cta. corriente **15 días** · Cta. corriente **30 días** |
| **Estado** | pendiente · parcialmente pagada · pagada · anulada |
| CAE | |
| Vencimiento del CAE | |

> **Esta versión NO conecta con ARCA.**
> Primero: que el sistema **registre bien las facturas**.
> Después: integración con ARCA (autenticación y autorización).
>
> Arquitectura prevista:
> ```
> Tu sistema → Backend → Servicio de facturación ARCA → CAE → Factura → Cuenta corriente del cliente
> ```

### 4.5 Recibos

| ID | Número de recibo | Cliente | Fecha | Importe | Forma de pago |
|---|---|---|---|---|---|

**Formas de pago:** Transferencia · Efectivo · Tarjeta de crédito · Tarjeta de débito · Cheque · Otro

### 4.6 Cuenta corriente
Historial de facturas + pagos, con **aplicación de cada recibo a la factura** que abona,
y **saldo pendiente a cancelar**. Imprimible y descargable en **PDF**.

```
FECHA       CONCEPTO          DEBE       HABER      SALDO
---------------------------------------------------------
01/09       Factura 0001      $50.000                $50.000
10/09       Recibo 0001                  $30.000     $20.000
20/09       Factura 0002      $40.000                $60.000
```

### 4.7 Ficha del cliente
Al entrar a `Cliente → Juan Pérez`, **pestañas**:

`DATOS` · `SERVICIOS` · `FACTURAS` · `RECIBOS` · `CUENTA CORRIENTE` · `OBSERVACIONES` · `SUGERENCIAS` · `INFORMES`

Arriba, cabecera con el cálculo automático:

```
Saldo pendiente:      $125.000
Facturas pendientes:  3
Último pago:          15/09/2026   ← último recibo
Total facturado:      $850.000
Total abonado:        $725.000
```
*(cifras de ejemplo)*

### 4.8 Dashboard del administrador

```
CLIENTES ACTIVOS       125
FACTURADO ESTE MES   $8.500.000
COBRADO ESTE MES     $6.700.000
PENDIENTE            $1.800.000
FACTURAS VENCIDAS         14
```
*(cifras de ejemplo)*

**Alertas de vencimiento:**
- 🔴 Factura vencida (ej.: hace 15 días)
- 🟡 Vence en 3 días
- 🟢 Pagada

### 4.9 PDF e impresión — botones

| Documento | 🖨 Imprimir | 📄 Descargar PDF |
|---|---|---|
| Factura | ✅ | ✅ |
| Recibo | ✅ | ✅ |
| Estado de cuenta | ✅ | ✅ |
| Informe del cliente | — | ✅ |

### 4.10 Clientes — operaciones (añadido por el cliente el 30/09/2026)

| Operación | Permitida | Condición |
|---|---|---|
| **Crear** | ✅ | con todas las validaciones de §5 |
| **Modificar** | ✅ | siempre |
| **Eliminar** | ⚠️ **condicional** | **SOLO si no tuvo movimientos** |

> 🔴 **Regla de negocio:** un cliente **no se puede borrar** si tiene
> **facturas o recibos**. En ese caso el sistema debe **bloquear la acción**
> y avisar con un mensaje claro (ej.: *"Este cliente tiene 3 facturas;
> no se puede eliminar"*).
> Si no tiene ningún movimiento → se elimina sin problema.

### 4.11 Totales — funciones de suma (añadido por el cliente el 30/09/2026)

Todo lo que muestre un listado debe **cerrar con el importe total al final**:

| Dónde | Qué suma |
|---|---|
| **Estado de cuenta** del cliente | **TOTAL DEBE · TOTAL HABER · SALDO FINAL** al pie de la tabla |
| **Facturación del mes** | **Importe total** facturado en el período |
| **Dashboard** | Facturado / Cobrado / Pendiente del mes (ya estaba en §4.8) |
| **Informe individual** | Totales facturado y abonado (ya estaban en §4.7) |

> El **saldo** es siempre `suma(DEBE) − suma(HABER)`.
> Los totales se calculan **en el backend** (SQL `SUM`), no en el navegador,
> para que no haya diferencias de redondeo.

### 4.12 Estética del panel administrativo (pedido 30/09/2026 · ✅ HECHA y aprobada)

**NO** usar el tono viejo (blanco + grafito + rojo, tipo suizo).

| Característica | Qué pidió | Cómo quedó |
|---|---|---|
| Fondo | **Degradé con azules** | `#070b14` + 3 halos radiales (azul, violeta, cian) |
| Formas | **Estilos geométricos** | grilla de 44px + esquinas cortadas `--cut: 14px` + barras con chaflán |
| Tono general | **Futurista** | Space Grotesk · glass blur · glow neón · chips de estado |

**Referencia:** el cliente eligió el tono de su web **`diseno-premium`** (`fiverr/…` →
`diseno-premium/css/styles.css`) y pidió *"estilo más lindo visualmente"*.
La paleta base es la misma, con acentos extra:

```
--bg:      #070b14      fondo marino
--accent:  #4f8cff      azul    (6.1:1)
--accent-2:#7c5cff      violeta (4.5:1)
--accent-3:#22d3ee      cian, para destacados
--grad:    #2f5fe0 → #5a3fe6   botones (blanco 5.5:1)
texto      #e9eefb      (17:1)   apagado #96a6c4 (8.0:1)
```

> 📌 **Tipografías:** Space Grotesk (interfaz) + IBM Plex Mono (datos, fechas, etiquetas).

> 📌 **Ojo:** esto aplica **solo al panel administrativo**.
> La **web pública** (`fiverr/portfolio/contable/`) **queda como está** en Blanco + Grafito
> — ese diseño ya fue aprobado por el cliente.
> Es decir: **dos identidades distintas** en el mismo proyecto, y eso es a propósito.

### 4.13 Pestaña SUGERENCIAS (añadida por el cliente el 30/09/2026)

Nueva pestaña dentro de la **ficha del cliente** (§4.7), junto a `OBSERVACIONES`.

**Qué guarda:** sugerencias que el estudio le aporta al cliente, con su fecha.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | INT autoincremental | clave principal |
| `cliente_id` | INT | **FK → `clientes.id`** |
| `fecha` | DATE | fecha de la sugerencia |
| `descripcion` | VARCHAR(500) | texto libre |
| `creado` | DATETIME | automático |

> 🗄️ **Va en una tabla propia: `sugerencias`** (no dentro de `clientes`).
> Relación **1 → N**: un cliente tiene muchas sugerencias.
> Se crea en la **Fase 2**, junto con `clientes`.

**📍 Dónde vive en la PANTALLA (importante):**

```
Menú → CLIENTES → buscar cliente (o lote) → clic en el cliente
                                                  ↓
                                    ┌──────────────────────────────┐
                                    │  FICHA DEL CLIENTE           │
                                    │  Juan Pérez                  │
                                    │  Saldo: $125.000             │
                                    ├──────────────────────────────┤
                                    │ DATOS · SERVICIOS · FACTURAS │
                                    │ RECIBOS · CUENTA CORRIENTE   │
                                    │ OBSERVACIONES · SUGERENCIAS  │  ← acá
                                    │ INFORMES                     │
                                    └──────────────────────────────┘
```

> ⚠️ **NO es un menú aparte.** La pestaña `SUGERENCIAS` **solo aparece adentro de la ficha**,
> después de que buscás y abrís un cliente.
> **Base de datos** = tabla aparte · **Pantalla** = pestaña dentro de Clientes.

**Ejemplos de sugerencias:**
- Buscar asesor legal
- Hacer plan de pagos
- Ponerse al día con las obligaciones impositivas ejecutadas

**✅ Dos decisiones resueltas el 30/09/2026** (apliqué el defecto; si querés otro, se cambia):

| # | Pregunta | Resolución aplicada |
|---|---|---|
| 1 | ¿Lleva **estado** (Pendiente / Atendida)? | **Sí** — campo `estado` con esas dos opciones, arranca en `pendiente` |
| 2 | ¿Las sugerencias **bloquean** la baja del cliente? | **No** — solo facturas/recibos bloquean (son los "movimientos") |

> 📌 **Otras dos respuestas del cliente (30/09/2026):**
> - **Observaciones** = **un solo texto** largo (se sobreescribe al editar, no es historial).
> - **DNI y CUIT conviven**: la persona física pide DNI (y CUIT opcional);
>   la jurídica pide CUIT (y no acepta DNI). **Los dos campos son únicos** y
>   **se busca por cualquiera de los dos**.

### 4.14 Código postal → localidad (añadido el 30/09/2026)

**Qué hace:** al escribir los **4 dígitos** del código postal en el alta o en la
edición del cliente, el sistema completa solo **Localidad** y **Provincia**.

**Cómo está hecho:**

| Pieza | Detalle |
|---|---|
| Tabla | `localidades` → `id` · `codigo_postal` (índice) · `nombre` · `provincia` |
| Endpoint | `GET /api/localidades?codigo_postal=5854` (requiere login) → lista con ese CP |
| Sin CP cargado | devuelve **lista vacía** y la localidad **se escribe a mano** |
| Seed | `python seed.py` → carga **81 localidades principales de Córdoba** (idempotente) |
| Campos nuevos en `clientes` | `cod_area` · `telefono` · `codigo_postal` |

> **El sistema nunca inventa la localidad**: si el CP no está en la tabla, deja los
> campos como estaban y el usuario completa a mano. `localidad` sigue siendo
> un campo libre y editable en cualquier caso.

**Fuentes de los códigos postales** (todas consultadas el **30/09/2026**):

| Fuente | Para qué se usó |
|---|---|
| `codigo-postal.co` (datos de Correo Argentino) | localidades puntuales: Río Ceballos `5111` · Anisacate `5189` · La Calera `5151` |
| `worldpostalcode.com/argentina/cordoba` | listado general a nivel de localidad de la provincia |
| Gist `lucsh/localidades.csv` (24.743 filas · `idProvincia=5` = Córdoba) | cruce de datos y detección de duplicados |
| Wikipedia (español) | Almafuerte `X5854` · La Falda `X5172` · Villa Gral. Belgrano `X5194` · Laboulaye `X6120` |

> ⚠️ **Dos correcciones contra fuentes oficiales** (las bases de datos traían errores):
> - **Laboulaye**: decían `5120` → es **`6120`** (Wikipedia + codigo-postal.co).
> - **La Calera**: traía 4 CP posibles → la del pueblo es **`5151`**.
>
> 📌 Si encontrás una localidad mal cargada, se corrige en `backend/seed.py` y se
> vuelve a correr `python seed.py` (solo agrega lo que falte, no duplica).

---

## 5. Reglas de validación (obligatorias)

1. **CUIT** con formato válido.
2. **DNI** solamente números.
3. **Email** con formato válido.
4. **Evitar CUIT duplicados.**
5. **Evitar DNI duplicados** cuando corresponda.
6. **Campos obligatorios claramente identificados.**
7. **Código postal** = 4 dígitos (solo números).
8. **Código de área** = 2 a 5 dígitos · **Teléfono** = 4 a 11 dígitos (solo números).

---

## 6. Pendientes

| # | Pendiente | Bloquea |
|---|---|---|
| 1 | ~~**Fase 1**~~ | ✅ terminada |
| 2 | ~~**Fase 2B**: pantallas de Clientes~~ | ✅ terminada |
| 3 | Fases 3 a 7 (ver §1) | Publicar |
| 4 | Elegir librería de **PDF** (a consultar: `reportlab` vs `weasyprint`) | Fase 5 |
| 5 | Subir fotos de la web pública a **WebP local** (Proyecto 1) | Demo en vivo |
| 6 | Vercel-ready: **config por variables de entorno** | Fase 7 |
| 7 | **Decisión tuya:** renumerar los id de cuenta y/o limpiar los 2 clientes de prueba que quedaron (n° 7 y n° 13). Los id **ya son autoincrementales**, los huecos vienen de registros borrados en los tests | Cosmético |

---

## 7. Bugs / incidencias

| # | Qué | Estado |
|---|---|---|
| 1 | `uvicorn --reload` **no recargaba** los cambios del backend (se quedaba sirviendo código viejo). Solución: matar el proceso del puerto 8010 y relanzarlo. Si tocás el backend y "no pasa nada", **reiniciá la API** | ✅ rodeado |
| — | sin bugs del sistema registrados todavía | |

---

## 8. Restricciones del proyecto

- **No agregar código de más.**
- Dejar **posible el backend con base de datos** para guardar usuarios en el futuro.
- Que sea **posible subir a Vercel**.
- **Consultar siempre** cualquier cambio antes de hacerlo.
