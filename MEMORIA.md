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
| **3** | **Facturas + Recibos + cuenta corriente** | ✅ **Hecha** (además: anticipos, compras, proveedores, estado de deuda) |
| **4** | **Dashboard + alertas de vencimiento** | ✅ **Hecha** (dashboard con KPIs, próximas vencimientos y alertas) |
| **5** | **PDF e impresión** (factura, recibo, estado de cuenta, informe) | 🟡 **Parcial** — hay Excel en todos los informes y botón Imprimir, pero **no hay PDF** |
| **6** | Preparación **ARCA** (sin conectar) | 🟡 **Parcial** — clave fiscal + vencimientos + informe listos; **falta lo demás** |
| **7** | Dejar **posible subir a Vercel** | ⬜ |
| **8** | **Contabilidad** (partida doble: plan de cuentas, asientos, libro diario, mayor) | ⬜ **No empezada** — es lo más grande que falta |
| **9** | **Tesorería** (caja, bancos, movimientos y conciliación) | ⬜ **No empezada** — va **después** de Contabilidad (§6) |

> **Nota de orden (02/10/2026):** Contabilidad y Tesorería son los dos módulos
> grandes que faltan. Tesorería **va después** de Contabilidad: cada movimiento
> de banco genera un asiento, así que si se carga Tesorería sin asientos quedan
> dos sistemas paralelos. Ver el detalle en §6.

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
| Módulo | **cliente** o **proveedor** (misma tabla, pantallas separadas, mismo formulario) |
| Número de cuenta | **correlativo independiente por módulo** (cliente n°1 y proveedor n°1 conviven; no se edita) |
| Condición ante el IVA | consumidor final · monotributista · responsable inscripto (obligatoria) |
| Alícuota de IVA | obligatoria solo si RI; se elige de la tabla `alicuotas_iva` (10,5 / 21 / 27 de inicio, ampliable desde el panel) |
| Nombre | obligatorio |
| Apellido / Razón social | obligatorio |
| CUIT | formato válido · **sin duplicados dentro de cada módulo** (la misma persona puede estar en ambos) |
| DNI | **solo números** (rechazar letras y símbolos) · **sin duplicados dentro de cada módulo** |
| Email | formato válido — **rechazar los que no tienen `@`** |
| **Código de área** | solo números (2 a 5 dígitos) · opcional · **está en las dos personas** |
| **Teléfono** | solo números (4 a 11 dígitos) · opcional · **está en las dos personas** |
| **Calle** | texto, hasta 30 caracteres |
| **Número** | texto, hasta 10 caracteres (admite letra, ej.: `742 B`) |
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

### 4.15 Proveedores y condición ante el IVA (añadido el 01/10/2026)

**Dos módulos separados** con el mismo formulario: **Clientes** y **Proveedores**.
Comparten la tabla `clientes` (son personas), con columna `tipo` y `nro_cuenta`
correlativo **independiente por módulo**. La misma persona puede estar en ambos,
con su cuenta en cada uno; CUIT/DNI únicos dentro de cada módulo.

**Condición ante el IVA** (obligatoria en ambos módulos): consumidor final ·
monotributista · responsable inscripto. Si es RI, se elige la **alícuota** de la
tabla propia `alicuotas_iva`, que se amplía desde el módulo **Configuración**
(alta para cualquier usuario, borrado solo admin; no se borra si está en uso).
Si en **Tipo de actividad** se elige monotributista o RI, la *Condición ante el
IVA* **se completa sola** y la alícuota solo se pide si es RI (no la pide para
monotributista).

> El módulo de **comprobantes de proveedores** queda para después, como pidió el cliente.

### 4.16 Centros de costos, tipos de gasto y compras (añadido el 01/10/2026)

**Centros de costos** (`centros_costos`): Comercialización y Administración de inicio,
ampliables desde **Configuración** (borrado solo admin).

**Tipos de gasto** (`tipos_gasto`): cada uno pertenece a **un** centro de costos
(13 en Administración; Publicidad y Combustible en Comercialización). Alta con
centro obligatorio desde **Configuración** (borrado solo admin).

**Compras** (facturas de proveedores): proveedor (solo módulo proveedor) · fecha ·
tipo/PV/número · **neto** (manual) · alícuota (catálogo) · **IVA = neto × alícuota
(calculado en backend)** · percepción (manual, 0 si no hay) · centro + tipo de gasto
(el tipo debe pertenecer al centro) · **total = neto + IVA + percepción (calculado
y validado en backend)**. Número único por proveedor. Estados pendiente/anulada
(anular y reabrir solo admin). Por ahora **no mueve cuenta corriente ni pagos**.

---

### 4.17 Informes y exportación a Excel (añadido el 01/10/2026)

- **Bloque "Informes" en el Dashboard**: campos *desde / hasta* y botones que
  descargan el Excel de **Listado de proveedores**, **Listado de compras** e
  **Informe por centro de costos**. Fechas vacías = período completo.
- **Listado de proveedores** (`/api/informes/proveedores[/export.xlsx]`): filtra
  por **fecha de alta**; también se pueden poner fechas *desde/hasta* en la
  pantalla de Clientes/Proveedores (buscador combinado con texto).
- **Listado de compras** (`/api/compras/export.xlsx?desde=&hasta=`): ya existía;
  se reutiliza desde el Dashboard.
- **Informe por centro de costos** (pantalla propia **"Informe por centro"** en
  el menú, `/api/informes/centros-costos[/export.xlsx]`): por cada centro muestra
  el **resumen por tipo de gasto** (cantidad, neto, IVA, total), el **detalle de
  cada comprobante** (fecha, tipo/PV/número, proveedor, concepto, gasto, neto,
  IVA, percepción, total) y el **total general**. Excluye compras **anuladas**.
- Todos los totales los calcula la base de datos / backend, nunca el navegador.

---

### 4.18 Informe de resultados (añadido el 01/10/2026)

Pantalla propia **"Informe de resultados"** en el menú (+ botón **Resultados**
en el bloque de informes del Dashboard) con filtros *desde/hasta*, Excel e
impresión. Estructura:

1. **Ingresos**: facturas y notas de débito del período **menos notas de
   crédito**; facturas **anuladas fuera**.
2. **Gastos (centros de costos)**: compras del período agrupadas por centro y
   tipo de gasto (anuladas fuera).
3. **NETO al pie** = total ingresos − total gastos.
4. **Tabla BIENES** (cuentas de balance, **no afectan al neto**): `1. Mercadería`
   y `2. Automóvil/Moto`, con importe pendiente — *a mejorar después* (no se
   asignan a un centro de costos).

El neto lo calcula el backend; el navegador solo muestra.

---

### 4.19 Variantes de selección y período contable (añadido el 01/10/2026)

Inspirado en las *selection variants* de SAP:

- **Período**: selector **"Mes y año"** (elige mes/año y completa `desde`/`hasta`
  solo, con el último día del mes) o **"Fechas"** (libre, como siempre).
  Disponible en: Informe de resultados, Informe por centro, Compras,
  Clientes/Proveedores y el bloque de informes del **Dashboard**.
- **Variantes**: tabla nueva `variantes` — guarda los filtros de cada pantalla
  con un nombre propio. Reglas: **privadas por defecto**, checkbox
  **Compartir** (las ve el equipo), nombre único por usuario+pantalla
  (re-guardar **sobreescribe**, como en SAP), cada uno borra las suyas
  (admin puede borrar todas). Pantallas válidas: informe-resultados,
  informe-centros, compras, clientes, proveedores, dashboard.
- Al elegir una variante se cargan los filtros y **se ejecuta la búsqueda**.

---

### 4.20 Rendimiento — auditoría Lighthouse (añadido el 01/10/2026)

Medir **siempre contra producción** (`npm run build` + `npm run preview`,
localhost:4173) — contra el dev server los puntajes son falsos (ver gotchas de
`AGENTE.md` §6.7 y §6.8).

Mejoras aplicadas:

1. **Fuentes locales**: Space Grotesk (variable, pesos 400–700) e IBM Plex Mono
   (400/500/600) bajados a `public/fonts/` con `@font-face` + `preload` y
   `font-display: swap` — **0 pedidos a Google Fonts**, nada bloquea el render.
2. **Carga diferida por rutas**: las pantallas (salvo Login y Dashboard, que
   son la entrada) se importan con `React.lazy` → JS inicial de **391 KB →
   284 KB** (90 KB gzip); el resto se descarga al navegar.
3. **Arranque sin bloquear por `auth/me`**: `AuthContext` lee el `rol` del JWT
   en el navegador y pinta de entrada; el `/auth/me` corre en **segundo
   plano**, superponiéndose a las llamadas del dashboard (antes eran dos
   vueltas secuenciales de ida y vuelta antes de pintar nada). Si el token no
   se puede leer del JWT, se comporta como antes (bloquea y espera).
4. **Esqueletos en el Dashboard**: mientras carga pinta el layout completo con
   `…` en los KPIs y bloques de tabla con altura reservada — sin pantalla en
   blanco y **sin saltos de diseño**.

Resultados (Lighthouse CLI, throttling simulado, 01/10/2026):

| Pantalla | Antes | Después |
|---|---|---|
| Login | 93 | **99** |
| Dashboard (logueado) | 98 | **99** — CLS 0,078 → **0** |

| Mobile con throttle real (panel DevTools, equipo del cliente) | Antes | Después |
|---|---|---|
| Página principal | **35** | **95** |

> Instrumento de medición: `medir-dashboard.mjs` + `limpiar-token.mjs`
> (Chrome headless por CDP + Lighthouse `--port`), en
> `AppData/Local/Temp/opencode`. Abre Chrome, hace login con admin y deja el
> dashboard listo para medirlo **logueado**.
> Con el panel de **DevTools** (throttle real) los números son más bajos —
> re-medir tras cada cambio.

---

### 4.21 Balance RT54 — estados contables (añadido el 01/10/2026, tanda 1)

Módulo propio en el menú (**Balance RT54**, `/balance-rt54`) para armar los
estados contables de un cliente conforme al **modelo RT54 de la FACPCE**
(estados con fines de lucro).

**Cómo funciona:**

1. Se elige el cliente con un **buscador con desplegable** (componente
   `BuscadorCliente.jsx`, compartido con Estado de cuenta) — búsqueda local
   con **todas las palabras** ("norte srl" encuentra a Distribuidora Norte
   SRL).
2. Aparece la **tabla de balances guardados** del cliente: nombre del
   ejercicio, fecha de inicio, fecha de cierre y botón **Modificar**
   (el abierto muestra "(ABIERTO)" y **Recargar**).
3. **Nuevo ejercicio**: nombre + fecha de inicio y **cierre manual** (no
  31/12 fijo). La **carátula se arma sola desde la ficha del cliente**
   (nombre/razón social, CUIT, domicilio, actividad) y es editable.
4. Pestañas con las **tablas del modelo** (rubros textualmente como el
   modelo, con sus Notas): **Carátula · Situación Patrimonial (ESP) ·
   Resultados (ER) · Patrimonio Neto (EEPN)** — cada una con columnas
   **Actual y Comparativo**.
5. **Todo se carga a mano** (NADA se precarga de facturas/cobros), como
   pidió el cliente. Los **totales los calcula el backend** (Decimal, nunca
   el navegador): subtotales de sección, Total del activo/pasivo, resultado
   del ER (`E9=E7-E8`, gastos con signo negativo para calzar las fórmulas
   del modelo), PN del ESP sale **del cierre del EEPN** (cross-sección) y
   el cierre del EEPN suma los saldos iniciales cargados.
6. Estados en pantalla: *CAMBIOS SIN GUARDAR* → **GUARDADO ✓**; si está
   sucio, **Emitir Excel** guarda primero y después descarga.
7. **Emitir Excel**: copia la plantilla oficial
   (`backend/plantillas/MODELO-EECC-Entes-Con-Fines-de-Lucro-RT54-publicacion_new.xlsx`,
   ver gotcha en `AGENTE.md`) y **llena celdas sin pisar las fórmulas**
   del modelo (EEP columna P recibe los totales comparativos por fila;
   `P18 = P10+SUM(P11:P17)` se auto-calcula; ER `F22` se pisa con el
   resultado comparativo). Nombre del archivo:
   `EECC-<cliente>-<ejercicio>.xlsx`.

**Datos:** tablas `bal_rt54_ejercicios` (cabecera + carátula editable) y
`bal_rt54_valores` (sección `esp|er|eepn` × clave × actual/anterior,
única por ejercicio). Migración: `migrar_balance_rt54.py`.

**Verificado 01/10/2026:** API de punta a punta (crear → guardar →
totales exactos → export con celdas cargadas y **fórmulas intactas**
chequeadas con openpyxl), flujo completo en navegador (buscar cliente →
tabla → Modificar → pestañas con totales → guardar → descargar Excel de
89 KB) y regresión de Estado de cuenta.

**Tanda 2 (hecha):** texto de las Notas — ver §4.23. Queda la **tanda 3**
(pendiente N°10): tablitas de composición de las notas, Anexos I–IX y
Flujo de efectivo.

---

### 4.22 Búsqueda multi-palabra en Clientes/Proveedores (añadida el 01/10/2026)

`_buscar()` de `cliente_service.py` ahora exige que **cada palabra** escrita
aparezca en algún campo (nombre, apellido, CUIT o DNI) en vez de buscar el
texto pegado: "Garcia Juan", "norte srl" y "PROVEE PROVEEDOR" encuentran
(antes, con dos palabras no encontraba nada). Afecta a las pantallas de
Clientes y Proveedores. Verificado en navegador (Proveedores:
"PROVEE PROVEEDOR" →1 fila).

---

### 4.23 Balance RT54 — Notas a los estados contables (añadido el 01/10/2026, tanda 2)

Alcance aprobado por el cliente: **solo el texto** de las notas (las
tablitas de composición y los Anexos quedan para la tanda 3, pendiente
N°10). Decisión tomada: la fila "Ganancia del ejercicio" del EEPN **se
sigue cargando a mano** (igual que el literal del modelo).

- **Pestaña NOTAS** en la pantalla del balance: **7 secciones plegables**
  (1 generales ·2 al ESP ·3 al ER ·4 al EEPN ·5 al flujo ·6 partes
  relacionadas ·7 impuesto a las ganancias) con **44 notas** en total.
- Cada cuadro viene **precargado con el texto del modelo**: lo que se ve es
  lo que se emite; si no tocás nada, la celda queda exactamente como en la
  plantilla.
- El **encabezado del modelo** ("2.1. Caja y bancos") se separa del cuerpo:
  no se puede editar y el export lo vuelve a poner arriba del texto del
  usuario. Si se vacía el cuerpo, la celda queda con el encabezado nomás.
- **Datos:** tabla `bal_rt54_notas` (ejercicio, clave, texto — única por
  ejercicio; migración en `migrar_balance_rt54.py`). El GET del ejercicio
  ya devuelve `notas` (guardadas o de la plantilla) y el PUT las guarda en
  el mismo giro que los importes. **Solo se escriben en el Excel las notas
  guardadas**; el resto de la celda no se toca.
- La plantilla se abre **una sola vez por proceso** (caché en
  `balance_rt54_service._celdas_plantilla_notas`), no en cada consulta.
- **Verificado01/10/2026:** API (GET44 notas → PUT3 → export con B7 = texto
  del usuario, B18 = encabezado + texto, B8 = solo encabezado, y B26/B11
  intactas = plantilla) y navegador (7 secciones,44 cuadros, editar →
  *CAMBIOS SIN GUARDAR* → GUARDADO ✓).

---

### 4.24 Balance RT54 — tanda 3: cuadros de notas + recálculo (añadido el 01/10/2026)

**Alcance aprobado:** 19 cuadros seleccionados (2.1–2.19), suites `test_cuadros_api.py` 60/0 y `test_recalculo_api.py` 14/14; fix alineación Total medido 0px; endpoint `POST /cuadros-notas` con debounce 500ms + seq guard.

**Qué incluye la tanda:**
- 19 cuadros (2.1 a 2.19 selectos; 2.20 y 2.22 excluidos → carga manual en el modelo, pendientes).
- Total en vivo: `POST /cuadros-notas` con debounce 500ms + secuencia guardada en caché.
- Coeficientes y totales **siempre en backend/SQL**, nunca en el navegador.
- Índices y coeficientes con **4 decimales** (`ROUND_HALF_UP`, constante `_CUATRO`).

**Verificado 01/10/2026:** suite `test_cuadros_api.py` 60/0, `test_recalculo_api.py` 14/14, build OK, alineación Total 0px.

---

### 4.25 Balance RT54 — Carátula (añadido el 01/10/2026, tanda 3)

**Alcance aprobado:** campos nuevos RPC/controlante/Composición del Capital + frontend completo.

**Qué incluye la carátula:**
- **Bloque RPC:** 8 campos (fecha inscripción RPC, identificación RPC, fecha de inscripción, etc.).
- **Bloque Sociedad controlante:** 6 campos (razón social, domicilio, actividad principal, porcentaje de votos, entes controlados en nota N°).
- **Dos tablas `.eecc-capital`** (1 renglón por tabla): “Acciones / Cuotas Sociales en circulación” y “Acciones / Cuotas Sociales en cartera”, cada una con 5 inputs (Cantidad / Tipo / Votos que otorga c/u / Suscrito / Integrado).
- **CSS `.eecc-capital input[type="text"]`** alineado a izquierda.
- **Suite `test_caratula_api.py`** 61/0: persistencia, Excel celda a celda, vacío=modelo intacto, restore.

**Verificado 01/10/2026:** API endpoints `PUT /balance-rt54/ejercicios/{id}` con 24 campos nuevos, schemas `CabeceraActualizar` con validador numérico (`""`→None, coma decimal), export con reemplazo de marcadores “…”/etiquetas + celdas C45/G52…; navegador: renderCaratula con bloque RPC, bloque Sociedad y dos tablas `.eecc-capital`; build OK.

---

### 4.26 Balance RT54 — Índices FACPCE + Moneda homogénea (añadido el 01/10/2026, tanda 3)

**Alcance aprobado:** 404 meses FACPCE (ene-1993 → ago-2026), modelo `IndiceMoneda`, servicio `moneda_homogenea()`, coeficiente con 4 decimales.

**Qué incluye:**
- **Modelo `IndiceMoneda`** (`config_indices_moneda`), schemas, router `/api/indices-moneda` (CRUD + DELETE admin).
- **Campo `fecha_cierre_ejercicio`** en modelo+schemas de cliente.
- **Migración `migrar_indices_moneda.py`** corrida; `cargar_indices_fapce.py` cargó 404 meses (estable, 0 correcciones).
- **Servicio `moneda_homogenea()`** + `exportar_moneda_homogenea()`: `_proxima_fecha_cierre`, `_indice_o_rechazo`, escala de filas con coeficiente a 4 decimales.
- **Endpoints** `GET …/moneda-homogenea` y `…/moneda-homogenea.xlsx` registrados en main.
- **Coeficiente con 4 decimales:** `round(indice_prox/indice_cierre, 4)` con `ROUND_HALF_UP`; índices también se quantizan a 4 antes de dividir.
- **Archivo FACPCE:** hoja única “ipc empalme ipim”, columnas MES (día1) + IPC NACIONAL EMPALME IPIM; valores hasta ~12.276,7660.
- **Suite `test_moneda_api.py`** 37/0: CRUD índices, alta/corrección sin duplicar, rechaza negativo, error “Falta el índice de …”, Excel con encabezados y tablas, coeficiente con4 dec, campo `fecha_cierre_ejercicio` en cliente.

**Verificado 01/10/2026:** backend + frontend código escrito; `npm run build` OK; suite API 37/0; Excel de moneda con A4/A5 con4 dec, B6 = coeficiente, encabezado “Saldo al 31/12/2025 / Actualizado al 31/08/2026”.

---

## CHECKPOINT A/B/C (01/10/2026)

| Checklist | Estado |
|---|---|
| **A** Tanda3: cuadros de notas + recálculo + alineación Total | ✅ 60/0 y 14/14, build OK |
| **B** CARATULA: bloques RPC/controlante + tablas capital + Excel | ✅ 61/0, build OK, navegador verificado |
| **C** Índices FACPCE + Moneda homogénea | ✅ 37/0 API, build OK, Excel + coeficiente 4 dec |

**Próxima tanda (pendientes registrados):**
- N°3 fases5-7, N°4 PDF, N°7 ids de prueba, N°10 (2.20/2.22 + bandera "presenta EECC"), Anexos I–IX + Flujo de efectivo, botón WhatsApp.
- ~~N°8 ejercicio contable~~ ✅ **hecho 01/10/2026** (MEMORIA §4.28: años de inicio/cierre + día y mes del cliente).

---

### 4.27 Separación de clientes y proveedores en tablas propias (añadido el 01/10/2026)

**Por qué:** antes todo vivía en una tabla `clientes` con un campo `tipo`, y las
búsquedas mezclaban clientes con proveedores (al buscar "PROVEEDOR" en Clientes
aparecía también el homónimo cliente). Ahora cada módulo tiene su tabla.

| Tabla | Qué guarda |
|---|---|
| `personas` | Datos comunes de toda persona (física o jurídica): nombre, CUIT/DNI, domicilio, actividad, condición de IVA, alícuota, **día y mes de cierre de ejercicio**, `presenta_eecc`. |
| `clientes` | Solo el módulo cliente: `persona_id` + `nro_cuenta`. |
| `proveedores` | Solo el módulo proveedor: `persona_id` + `nro_cuenta`. |

- **CUIT y DNI son únicos en `personas`** (no por módulo): la misma persona no
  se carga dos veces.
- **Cada módulo tiene su correlativo propio** (cliente n°1 y proveedor n°1
  conviven). Migración: `migrar_personas.py` + `reparar_cuentas.py`.
- **Servicios y sugerencias** quedan en el módulo cliente (un proveedor no
  contrata servicios del estudio: el bloque no se muestra en su ficha ni en su
  alta).
- Los modelos `Cliente` y `Proveedor` delegan en su `Persona` los datos comunes
  (`nombre_completo`, `cuit`, …) para que el resto del código siga igual.
- **Verificado 01/10/2026:** suite `test_personas_api.py` 24/0 (listas separadas,
  búsquedas que no mezclan, correlativos independientes, alta/edición/baja de
  ambos módulos, CUIT duplicado rechazado) + navegador (listados, ficha y alta de
  proveedor con los datos correctos).

---

### 4.28 Ejercicio contable del balance: años + día/mes de cierre (añadido el 01/10/2026)

**Qué hace:** al crear un balance, el usuario elige **el año de inicio y el año
de cierre**; el **día y mes de cierre** salen de la ficha del cliente (es un
cierre que se repite todos los años) y el sistema arma el intervalo.

```
Cliente cierra el 31/07   +   años 2024 → 2025
   →  ejercicio del 01/08/2024 al 31/07/2025
```

- El ejercicio va **del día siguiente al cierre del año inicial** hasta **el
  propio día/mes de cierre del año final**. Si los años son iguales, el
  ejercicio cierra ese día/mes de ese año.
- **29/02 en año no bisiesto cae al 28/02** (2025 no tiene 29/02 → 28/02/2025).
- Columnas nuevas en `bal_rt54_ejercicios`: `anio_inicio`, `anio_fin`,
  `dia_mes_cierre`, `mes_cierre` (migración `migrar_balance_ejercicio.py`).
- La pantalla avisa **antes de crear**: *"Este cliente cierra el 31/07 todos los
  años. El ejercicio va del 01/08/2024 al 31/07/2025."*
- Si el cliente **no tiene** día/mes cargado, la pantalla deja elegirlo ahí.
- **Verificado 01/10/2026:** suite `test_intervalo_balance.py` 18/0 + navegador
  (crear un balance con años 2024/2025 para un cliente que cierra 29/02 → quedó
  29/02/2024 a 28/02/2025).

---

### 4.29 Vencimientos impositivos + datos del propietario (añadido el 01/10/2026)

**Qué hace:** módulo de **vencimientos de impuestos** (ARCA) para saberle al
cliente cuándo le vence cada cosa. Son **dos partes**:

| Parte | Dónde | Qué hace |
|---|---|---|
| **Cargar** | Configuración → "Vencimientos impositivos" | Elegís mes + año y llenás una grilla de **10 dígitos × 8 impuestos** |
| **Consultar** | Menú → "Vencimientos" | El calendario del mes, **agrupado por último dígito del CUIT** |

**La regla del último dígito:** todos los clientes que terminan en el mismo
dígito del CUIT vencen el **mismo día**. Por eso la grilla es 10 filas (0 a 9).

**Los 8 impuestos** (catálogo fijo en `IMPUESTOS`, en
`models/vencimiento_impositivo.py`):

`ddjj_iva` · `sicore_cta` (SICORE - Pago a cuenta) · `ddjj_sicore` ·
`ddjj_ganancias` · `monotributo` · `convenio_multilateral` ·
`anticipo_fondo_coop` · `ddjj_fondo_coop`

**Tabla `vencimientos_impositivos`:** una fila por (año, mes, último dígito,
impuesto) → `fecha_vencimiento`. Las fechas se cargan **mes a mes** porque ARCA
las va cambiando; lo que dejes vacío en la grilla **no se guarda** y al guardar
**se reemplaza el mes entero** (no duplica).

**La pantalla de consulta** muestra, por cada dígito: los impuestos con su fecha
y **cuántos días faltan** ("vence hoy" / "mañana" / "en 9 días"), y los
**clientes** de ese dígito. Abajo, aparte, los **clientes sin CUIT** (no se
pueden agrupar) con un aviso para cargárselo en la ficha.

#### Datos del propietario

Tabla `propietario` (**una sola fila**) con los datos del estudio, tipo
plantilla de cliente: nombre/razón social, CUIT, actividad, domicilio, código
de área, teléfono y **hasta 4 correos** (`email_1`..`email_4`) + observaciones.
Se usa en los encabezados de los Excel y **para mandar los avisos de
vencimientos**. Se edita en Configuración → "Datos del propietario del
software"; los correos se validan (deben tener `@` y punto).

- **Verificado 01/10/2026:** suite `test_vencimientos.py` **23/0** + navegador
  (carga de la grilla de October 2026, pantalla de consulta con 2 grupos + los
  sin CUIT, alta/edición del propietario con 2 correos).

---

### 4.30 Clave fiscal de ARCA + informe de CUIT y clave fiscal (añadido el 02/10/2026)

**Qué hace:** guardar la **clave fiscal de ARCA** del cliente (lo que permite
trabajar en ARCA en nombre del contribuyente) y sacar un **informe** para ver a
quién ya se la cargaste y a quién le falta.

#### La clave fiscal

Va en **`personas`** (junto al CUIT, no en `clientes`) porque es un dato del
contribuyente. **Opcional**: no todos la tienen (el consumidor final, o el
cliente que entra con su propio CUIT).

**Tres columnas en `personas`:**

| Columna | Qué guarda |
|---|---|
| `clave_fiscal` | La clave (11 caracteres alfanuméricos, en mayúsculas) |
| `fecha_carga_clave_fiscal` | Cuándo se cargó **por primera vez** (no se mueve más) |
| `fecha_modif_clave_fiscal` | Cuándo se cambió por **última vez** |

**Tabla `clave_fiscal_historial`:** el cuaderno de cambios. **Una fila cada vez
que la clave cambia**, no una por persona:

```
clave_fiscal_historial
├── persona_id                -> a quién es (ON DELETE CASCADE)
├── clave_fiscal_anterior     la que tenía antes (NULL si es la primera)
├── clave_fiscal_nueva        la que se puso (NULL si la quitaron)
├── fecha_cambio              cuándo
└── usuario                   quién lo cambió
```

Si a un cliente nunca le cambiás la clave, **no tiene ninguna fila**.

- Se edita en la **ficha y en el formulario** (campo al lado del CUIT/DNI).
- La ficha muestra la clave, las dos fechas y abajo la **tabla de cambios**.
- Guardar la misma clave **no** crea historial falso. Borrarla borra las fechas.
- Endpoints: `GET /api/clientes/{id}/clave-fiscal/historial` (y de proveedores).
- **Verificado 02/10/2026:** suite `test_clave_fiscal.py` **29/0** + navegador
  (alta, cambio de clave, tabla de historial, proveedores, borrado en cascada).

#### Informe de CUIT y clave fiscal

Menú → **"Informe de claves fiscales"**. Filtros: **desde/hasta** (fecha en que
se cargó la clave) y **terminación del CUIT** (0 a 9). Trae:

- La lista de los que **tienen** clave, con CUIT, clave, fechas y email.
- Abajo, aparte, los que **no la tienen** (con aviso de cargársela).
- Botón para ver **todo junto** o **en bloques por dígito**, y para ordenar
  por cuenta, apellido y nombre, CUIT, **terminación del CUIT** o fecha de
  carga (se hace clic en el encabezado de la columna).
- **Excel** que sale con los mismos bloques y los mismos filtros.

Solo **clientes** (los proveedores no se mezclan).

- **Verificado 02/10/2026:** suite `test_informe_claves.py` **25/0** + navegador
  (filtro por terminación, cambio entre bloques y lista, Excel).

#### Bugs corregidos de paso

Todos estos salían al correr las pruebas; **ninguno lo causó el trabajo de hoy**,
pero los tests los historiales destaparon:

| Bug | Síntoma | Por qué pasaba | Arreglo |
|---|---|---|---|
| **Estado de cuenta roto** | La pantalla no cargaba nada (**404**) | El frontend pedía `/clientes/{id}/cuenta-corriente`, pero el endpoint es `/cuenta`. Además al endpoint le faltaba el `export.xlsx` | Se corrigió la ruta en `cuentaCorriente.js` y se agregó `GET /clientes/{id}/cuenta/export.xlsx` |
| `/api/clientes/{id}/cuenta` daba **500** | Al pedir la cuenta corriente de cualquier cliente | El router llamaba `cuenta_service.resumen()`, que en §4.27 quedó con el nombre `movimientos()` | Se corrigió la llamada (y de paso se aceptaron `desde`/`hasta`) |
| `/api/informes/proveedores` daba **500** | El informe de proveedores reventaba | Filtraba por `clientes.tipo`, columna que ya no existe desde §4.27 | Usa `Proveedor` + join con `Persona` (el `fecha_alta` vive en `personas`) |
| Excel de **moneda homogénea** daba **500** | No se descargaba el Excel | `PatternFill` se usaba en la línea 1434 pero se importaba recién en la 1452 | Import arriba, junto a `Font` y `Alignment` |
| **Errores sin explicación** | Mandar un dato incompleto devolvía **500** mudo | El router armaba el schema a mano con `**datos`; el error de pydantic no lo agarraba nadie | `datos_invalidos()` en `core/errors.py` → **422** con el motivo en castellano |
| Anticipo con cliente inexistente daba **500** | Reventaba con error de MySQL | No se validaba la FK antes de insertar | `Rechazo("No existe ese cliente", 404)` |
| `Propietario` mostraba `: Field required` | Al abrir Configuración | Se le pasaba la función de **guardar** donde esperaba la de **leer** | Se pasan `obtener` y `guardar` por separado |
| La hora de los cambios salía **corrida** | Decía 02/10 cuando hoy era 01/10 | El backend guarda `datetime.utcnow` (UTC) y la pantalla lo mostraba tal cual | `fechaHora()` en `formato.js` convierte a hora local |

#### Estado real de las pruebas (02/10/2026)

Las suites viven **adentro del proyecto**, en
`C:\proyecto-gestion-contable\tests\`. Para correrlas todas:
`python -X utf8 correr_todas.py` (o `--solo <palabra>` para filtrar).

**19/19 suites en verde (757 pruebas)**, corridas dos veces seguidas (limpieza
al principio y al final, así que no dejan basura):

| Suite | Resultado |
|---|---|
| `test_anticipos.py` | 70/0 |
| `test_asientos_automaticos.py` | 45/0 |
| `test_caratula_api.py` | 61/0 |
| `test_cuadros_api.py` | 60/0 |
| `test_clave_fiscal.py` | 29/0 |
| `test_cp_telefono.py` | 28/0 |
| `test_facturas.py` | 56/0 |
| `test_fase2a.py` | 56/0 |
| `test_informe_claves.py` | 25/0 |
| `test_informes.py` | 25/0 |
| `test_intervalo_balance.py` | 18/0 |
| `test_mail.py` | 18/0 |
| `test_moneda_api.py` | 37/0 |
| `test_motor_contable.py` | 69/0 |
| `test_personas_api.py` | 24/0 |
| `test_plan_cuentas.py` | 38/0 |
| `test_recalculo_api.py` | 14/0 |
| `test_recibos.py` | 56/0 |
| `test_vencimientos.py` | 28/0 |

### Bugs que aparecieron al poner las suites al día

Al arreglar las 4 suites viejas (`anticipos`, `recibos`, `fase2a`,
`cp_telefono`) y la de `mail`, salieron **bugs reales del sistema**:

| Bug | Síntoma | Por qué pasaba | Arreglo |
|---|---|---|---|
| 🔴 **Los servicios no se guardaban al dar de alta** | El cliente se creaba pero sin servicios, y la ficha los mostraba vacíos | `servicios` es relación de **Cliente**, no de Persona; el service hacía `persona.servicios = ...` y eso se perdía en el aire | `cliente.servicios = ...` en `crear` y `actualizar` |
| 🔴 **El backend no validaba nada de los datos** | Mandabas un CUIT de 5 dígitos, un DNI con letras o un email sin `@` y lo aceptaba | Las validaciones vivían **solo en el formulario** (HTML5). La API (y el futuro espejo ARCA) no chequeaba nada | Validadores en `schemas/persona.py` (CUIT 11 dígitos con prefijo válido, DNI solo números de 6 a 10, email con `@` y dominio, CP 4 dígitos, código de área 2 a 5, teléfono 4 a 11, persona física necesita apellido + DNI, jurídica necesita CUIT y no lleva DNI) + **normalización del CUIT** (`20264736742` → `20-26473674-2`) |
| 🟡 **El número de recibo/anticipo se ignoraba en silencio** | Mandabas `numero` y el sistema te creaba el registro con otro número, sin decir nada | El schema lo aceptaba pero el service siempre genera el correlativo. `_verificar_unico` quedó como código muerto | Ahora si mandás el número responde **400** con un mensaje claro: *"El número se genera solo"*. Se borró el código muerto |
| 🟡 **Anticipo o recibo con cliente inexistente** | **500** con error crudo de MySQL | No se validaba la FK antes de insertar | `Rechazo("No existe ese cliente", 404)` |

Los tests viejos también tenían expectativas que ya no correspondían (pedían
201 donde la API devuelve 200, armaban un CUIT de 9 dígitos, mandaban el
`numero` a mano) y no limpiaban sus datos: por eso quedaron 8 duplicados de
"Distribuidora Norte SRL" y 5 filas de historial de clave fiscal de prueba.
Se limpiaron con `limpiar_duplicados_prueba.py`.

---

| # | Pendiente | Bloquea |
|---|---|---|
| 1 | ~~**Fase 1**~~ | ✅ terminada |
| 2 | ~~**Fase 2B**: pantallas de Clientes~~ | ✅ terminada |
| 3 | Fases 3 a 7 (ver §1) | Publicar |
| 4 | Elegir librería de **PDF** (a consultar: `reportlab` vs `weasyprint`) | Fase 5 |
| 5 | Subir fotos de la web pública a **WebP local** (Proyecto 1) | Demo en vivo |
| 6 | Vercel-ready: **config por variables de entorno** | Fase 7 |
| 7 | **Decisión tuya:** renumerar los id de cuenta y/o limpiar los 2 clientes de prueba que quedaron (n° 7 y n° 13). Los id **ya son autoincrementales**, los huecos vienen de registros borrados en los tests. *Cliente n°7 (Juan) tiene facturas/recibos asociados, por lo que el hueco persiste; el cliente n°13 (Distribuidora Norte SRL) es el cliente real del Balance RT54 y se mantiene.* | Cosmético |
| 8 | ~~**Ejercicio contable**~~ ✅ **hecho 01/10/2026** (MEMORIA §4.28): en el Balance RT54 se elige el **año de inicio y el de cierre** y el **día/mes de cierre sale de la ficha del cliente** (se repite todos los años); el sistema arma el intervalo (01/08/2024 → 31/07/2025 si cierra 31/07). *Queda para más adelante que los otros informes (facturas, compras, resultados) filtren por ejercicio en vez de año calendario.* | Módulo contable |
| 9 | ~~**Estado de cuenta — selector de cliente** (pedido 01/10/2026): hoy el cliente se elige de un `<select>` con todos los cargados. Hace falta **búsqueda por apellido y nombre o razón social** (reusar el endpoint de sugerencias, como en los formularios)~~ ✅ **Hecho 01/10/2026**: campo con desplegable y búsqueda **local** (todas las palabras deben coincidir en apellido/nombre o razón social + CUIT/DNI); elegir carga la cuenta, escribir de nuevo limpia la selección | ✅ terminada |

### 4.54 Cuentas bancarias de los clientes (03/10/2026)

Solapa **"Cuentas bancarias"** en la ficha del cliente, después de "Cuenta corriente". Un cliente puede tener todas las cuentas que quiera. Dos tablas (``migrar_cuentas_bancarias.py``, idempotente).

**Por qué dos tablas:** el CBU **ya trae el banco adentro** — los primeros 8 dígitos son el código del BCRA. Si el banco se guardara como texto libre, quedaría "Galicia", "GALICIA", "galicia" y el sistema no reconocería que son el mismo. Con `bancos.codigo` (8 dígitos) como clave primaria, nunca se duplica y además sirve para **verificar que el CBU sea del banco que dice**.

**El catálogo arranca VACÍO a propósito:** los códigos de los ~90 bancos **no se inventan**. Se llenan solos con los CBU que se cargan (el banco se crea con un nombre provisorio tipo "Banco 28505909"), y el contador le pone el nombre una vez desde Configuración → Bancos.

- **El CBU se valida por estructura, NO por dígito verificador.** Se validan los 22 dígitos, que los primeros 8 coincidan con el banco, y que la sucursal y la cuenta escritas sean las del CBU. El **digito verificador no se chequea a propósito** (`_digito_verificador_cbu`): escribir ese algoritmo de memoria es más riesgoso que no escribirlo, porque **rechazaría CBU que sí son válidos** y el contador no podría cargar la cuenta real de un cliente. Queda como hueco consciente, para agregarlo cuando se pueda confirmar contra un CBU conocido.
- **CBU y CVU van en columnas separadas y nunca los dos a la vez.** El CBU es una cuenta de banco (tiene sucursal y cuenta); el CVU es la dirección de una billetera. Si se dejaran los dos, el contador no sabría cuál copiar.
- **El CBU no puede estar en dos cuentas** (ni en dos clientes). El CBU identifica una cuenta, no una persona: si dos lo tienen, uno está mal, y para las conciliaciones sería un problema.
- **No se borran, se dan de baja** (`activo`). Una cuenta puede estar usada en un recibo emitido; borrarla dejaría ese recibo apuntando a nada.
- `sucursal` y `numero_cuenta` son **texto**, no número: en un CBU los ceros adelante son válidos ("0001") y como número desaparecen. El `cuit_titular` se guarda **con guiones**, como el resto del sistema (`personas.cuit`).
- El **código del banco no se puede editar**: es la clave primaria y sale del CBU. Solo se escribe el nombre.
- Pegar un CBU completa solo la sucursal (dígitos 9-12), la cuenta (13-21) y el banco (1-8).
- El botón "Copiar" al portapapeles **no se pudo verificar**: el navegador de las pruebas está en modo invisible y `navigator.clipboard` no anda ahí. En la máquina del contador debería andar, pero queda sin probar.

**Bug encontrado probando:** una cuenta con **solo alias** daba **500**, porque no hay código de banco y `bancos.codigo` es la clave primaria (no admite NULL). Se resolvió con `SIN_BANCO = "00000000"`, que no se ofrece en el selector (`listar_bancos` lo filtra).

**Para conciliaciones bancarias (aún no está hecho):** si se corrige un CBU, el anterior se pierde. Cuando se implemente convendría que el CBU sea "nuevo + baja del viejo" en vez de una edición, para no perder el histórico.


## 7. Bugs / incidencias

| # | Qué | Estado |
|---|---|---|
| 1 | `uvicorn --reload` **no recargaba** los cambios del backend (se quedaba sirviendo código viejo). Solución: matar el proceso del puerto 8010 y relanzarlo. Si tocás el backend y "no pasa nada", **reiniciá la API** | ✅ rodeado |
| 2 | ~~Los tests (`test_*.py`) están en `C:\Users\admar\AppData\Local\Temp\opencode\`, fuera del proyecto~~ ✅ **Cerrado 02/10/2026**: están en `C:\proyecto-gestion-contable\tests\` (19 suites + `correr_todas.py` + `LEEME.md`) y las rutas al backend son relativas. | ✅ cerrado |
| 3 | ~~4 suites desactualizadas~~ ✅ **Arregladas el 02/10/2026** (§4.30). Las **16 suites pasan**, dos vueltas seguidas | ✅ cerrado |
| 4 | Los routers que arman el schema a mano con `**datos` necesitan `try/except ValidationError` + `datos_invalidos()`, si no devuelven **500 sin explicación** en vez de 422. Ya está en clientes y proveedores; **faltan los demás** (facturas, anticipos, recibos...). Compras ya no lo hace: usa el schema de Pydantic | 🟡 a revisar |
| 5 | El **CUIT no se valida el dígito verificador**: se chequea que tenga 11 dígitos y prefijo válido, pero no que el dígito 11 sea el correcto. Un CUIT mal tipeado con 11 dígitos pasa. *Opcional agregarlo* | 🟢 opcional |
| 6 | ~~Las compras no se podían cargar (500 siempre)~~ ✅ **Cerrado 02/10/2026** (§4.39): `Compra.proveedor_id` apuntaba a `clientes` cuando los proveedores viven en `proveedores`/`personas`, y la validación leía un `.tipo` inexistente | ✅ cerrado |
| 7 | ~~El **informe de resultados** sacaba los gastos de la tabla `compras`, así que no cuadraba con el informe por centro de costos~~ ✅ **Cerrado 02/10/2026** (§4.40): los tres lados del estado de resultado salen de los asientos contabilizados, con la misma función que usa el informe de centros | ✅ cerrado |
| 8 | ~~Siete suites borraban los asientos reales del estudio en cada corrida~~ ✅ **Cerrado 02/10/2026** (§4.42 + `AGENTE.md` §6 bis). Respaldo completo, huella digital que avisa, y `borrar_prueba.py`. Los recibos de prueba fugados (140) se borraron con OK del contador | ✅ cerrado |
| 9 | ~~El **buscador de cuentas** del editor de asientos nunca funcionó (422)~~ ✅ **Cerrado 02/10/2026** (§4.43): `plan_cuentas` se registraba antes que `asientos` en `main.py`, y `/plan-cuentas/{cuenta_id}` se comía `/plan-cuentas/buscar`. **Ojo con el orden de `include_router`**: las rutas literales van antes que las de parámetro | ✅ cerrado |
| 10 | El **desplegable del menú** se veía transparente (`var(--surface)` es blanco al 4%) y se veía el menú de abajo atravesado | ✅ cerrado 02/10/2026 (§4.44) |
| 11 | Las **suites se contaminan entre ellas**: cada una mide sobre una base que la anterior dejó sucia. Se tapaba porque `test_ejercicio.py` borraba todos los asientos de todos. Arreglado en lo más grosero (cada una limpia lo suyo con `borrar_prueba`), pero **la solución de fondo es la base de pruebas separada**, que sigue pendiente | 🔴 pendiente |
| 12 | Sacar el `max-height` de `.tabla-scroll` le quitó el scroll a **todas** las tablas de golpe, no solo a la de clientes | cerrado 02/10/2026 (§4.46) |
| 13 | Los formularios de alta quedaban **en blanco**: un `clientes.find(...)` antes del `useState` de `clientes` ( *"Cannot access 'clientes' before initialization"* ) | cerrado 02/10/2026 (§4.46) |
| 13 | ~~**Mover las pruebas adentro del proyecto**~~ ✅ **hecho 02/10/2026**: las 19 suites viven en `C:\proyecto-gestion-contable\tests\` con `LEEME.md` y `correr_todas.py` (`--solo <texto>` para filtrar). Además las rutas al backend se calculan desde el propio archivo, así que el proyecto se puede mover de carpeta. | ✅ terminada |
| 12 | **Botón de WhatsApp** (en la ficha del cliente y en los comprobantes) | Para más adelante |
| 11 | **Módulo de vencimientos — parte 3: enviar el mail** (pedido 01/10/2026): las grillas, la pantalla y los datos del propietario ya están (§4.29). Falta el **botón que manda el aviso**. Hay dos caminos: **(A)** el backend manda solo por SMTP (hace falta una cuenta de salida + **contraseña de aplicación** de Gmail: activar verificación en 2 pasos y generarla en el panel de Google; se cargaría en Configuración, nunca en el chat); **(B)** el sistema **arma el mail y lo abre** en el Outlook/Gmail del usuario (sin contraseñas, más simple). **Esperando tu decisión.** | Cierre del módulo |
| 10 | **Balance RT54 — tanda 3** (pedido 01/10/2026): ~~texto de las Notas~~ ✅ **hecho01/10/2026** (MEMORIA §4.23). Ahora faltan las **tablitas de composición** de las notas (Conceptos \| Actual \| Comparativo), los **Anexos I–IX** y el **Flujo de efectivo**. Decisión tomada: en EEPN la fila "Ganancia del ejercicio" **se sigue cargando a mano** (sin auto-rellenar desde ER). Pendientes chiquitos del balance: (b) **Eliminar** visible para todos y el backend lo rechaza salvo admin; (c) flag "presenta EECC" por cliente (hoy se elige el cliente a mano) | Siguiente tanda del balance |

---

### 4.31 Vencimientos: árbol por año/mes + catálogo editable + respaldo (02/10/2026)

El pedido fue que **para cargar vencimientos hay que elegir el año y el mes**, y
que Configuración no sea una sección larga: un **árbol año → mes → grilla**.

**Árbol (Configuración → Vencimientos)**
- Se ven **todos los meses del año** (Enero…Diciembre), no solo los cargados:
  si no se ven los vacíos, no hay forma de saber que tenés que cargarlos.
- Aparecen siempre el **año en curso y el que viene** (así se carga 2027 sin
  esperar a diciembre), más los años que ya tengan datos. Con "Ver otro año"
  se agrega cualquiera entre 2000 y 2100.
- Cada mes dice cuántos vencimientos tiene y la **fecha de última
  actualización** (y quién la hizo). Al clickear el mes se abre la grilla abajo.
- Cada año muestra un resumen: "3 de 12 meses · 24 vencimientos".

**Nada se pierde (pedido explícito del 02/10/2026)**
El guardado de un mes es borrar + insertar (para que no queden filas viejas).
Eso ya estaba dentro de una transacción (si algo falla, no queda a medias), pero
se>**agregaron dos seguidoas**:

1. `vencimientos_meses` (tabla nueva, `backend/migrar_vencimientos_meses.py`):
   un registro por mes guardado con `cantidad`, `ultimo_cambio`, `usuario` y
   **`respaldo`** (JSON del último guardado). Sirve para tres cosas: la fecha de
   última actualización del árbol, un respaldo para recuperar, y saber qué meses
   existen aunque después los vacíes.
2. **No se puede vaciar un mes por accidente**: si el mes tiene datos y llega
   la grilla vacía, el backend responde **409** y no borra nada, salvo que
   venga `vaciar=true`. La grilla pide confirmación con `window.confirm`.
3. `POST /meses/restaurar` vuelve a poner el último guardado desde el respaldo.

**Catálogo de conceptos editable**
Ya no es una lista fija en el código: es la tabla `conceptos_vencimiento`.
- Alta con botón "Agregar concepto" (el backend arma el `clave` slug y el `orden`).
- **Renombrar** (la clave no se toca, así que los vencimientos viejos siguen
  apuntando al mismo concepto).
- **Apagar** en vez de borrar: desaparece de las grillas nuevas, pero los
  vencimientos ya guardados no se tocan. Con "Encender" vuelve.
- `vencimientos_impositivos` **no tiene FK** a propósito: si se borra o apaga un
  concepto, los vencimientos viejos sobreviven y muestran la clave como nombre.
- `GET /conceptos?incluir_inactivos=true` — sin ese parámetro el backend esconde
  los apagados y en Configuración no se veían ni se podían volver a encender.
- Si intentás dar de alta un nombre que ya existe pero está **apagado**, el
  backend te avisa eso en vez de decir "ya existe" a secas.

**Aviso de CUIT (sin bloquear)**
`cuit_advertencia` ya lo armaba el backend pero faltaba exponerlo: se agregó el
campo a `ClienteListadoOut` (si no, `/api/clientes` reventaba con
`NameError: cuit_advertencia`) y se muestra en amarillo en la ficha. El dígito
verificador **avisa pero no bloquea**, según lo decidido el 02/10/2026.

**Archivos**
- Backend: `models/concepto_vencimiento.py`, `models/vencimiento_mes.py`,
  `services/vencimiento_service.py` (catálogo + `meses_cargados` +
  `_registrar_mes` + `restaurar_mes` + `detalle_del_mes`),
  `routers/vencimientos.py`, `migrar_conceptos_vencimiento.py`,
  `migrar_vencimientos_meses.py`.
- Frontend: `pages/VencimientosConfig.jsx` (árbol + catálogo),
  `pages/GrillaVencimientos.jsx` (grilla reusable), `pages/vencimientosComun.js`
  (MESES, diasPara), `pages/Vencimientos.jsx` (solo consulta),
  `api/vencimientos.js`.

**Bugs que aparecieron en el camino**
- `.scalars()` es del **Resultado** de `db.execute`, no del `select`:
  `db.execute(select(X).where(...)).scalars().first()`. Con `.scalars()` sobre el
  `select` tiraba `AttributeError` y el guardado daba 500.
- `detalle_del_mes` se había perdido al reescribir el service → 500 en
  `/detalle` y la pantalla de consulta se caía.
- Faltaba `total_vencimientos` y `cantidad_clientes` en el detalle (el frontend
  los usa).
- `listarConceptos` sin `incluir_inactivos`: los conceptos apagados no se veían.
- La grilla no tomaba las columnas nuevas hasta recargar: ahora el padre le pasa
  `conceptos` ya filtrados y se recalcula al cambiar el catálogo.

### 4.32 Plan de cuentas RT54 — estructura contable (02/10/2026)

**Pedido:** crear la estructura contable **sin tocar** las pantallas de facturas,
recibos ni asientos, y **sin** el motor de asientos todavía.

Fuente: `C:\estudio contable\plan de cuentas.xlsx`.
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
(69, actualizado a 8 códigos). Las **19 suites en verde (757 pruebas)**, y ahora
viven en `C:\proyecto-gestion-contable\tests\` con `correr_todas.py`.

**Lo que falta para que se use**: la pantalla. Hoy la generación se dispara
desde el service, no desde la pantalla de facturas ni desde la de recibos, y la
columna `cuenta_cobro_id` todavía no está en el formulario de recibo.

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

### 4.36 La venta SIEMPRE va a Documentos a cobrar, nunca a Caja (02/10/2026)

El contador corrigió un error de diseño de §4.34: ahí se había sembrado
`VENTA_*_CONTADO` con la cuenta de Debe en **Caja**.

**Una factura es una deuda del cliente, no plata recibida.** Al contado o a
cuenta corriente, la venta va a `1.1.03.02 Documentos a cobrar` con el cliente
como auxiliar. La plata entra en Caja o Banco **recién en tesorería**, cuando se
registra el cobro: ahí el Debe va al banco/caja que corresponda y el Haber a
Documentos a cobrar. Por eso `1.1.01.01 Caja` no aparece en **ningún** asiento de
factura.

> Caja y Fondo fijo son cuentas de **tesorería**, no de facturación.

#### El arreglo fue de DATOS, no de código

`config_asientos` es una tabla justamente para esto: cambiar la cuenta de una
operación no es tocar el programa. Las 4 filas de venta quedaron con
`cuenta_debe` = `1.1.03.02`.

```sql
-- backend\corregir_ventas_documentos_a_cobrar.py  (tiene --ver)
UPDATE config_asientos SET cuenta_debe = <id de 1.1.03.02>
 WHERE clave IN ('VENTA_SERVICIOS_CONTADO', 'VENTA_ARTICULOS_CONTADO');

-- y las líneas de los asientos que quedaron viejas
UPDATE asiento_detalle SET id_cuenta = <doc>, tipo_auxiliar = 'CLIENTE',
                         id_auxiliar = <cliente de la factura>
 WHERE id_asiento = <asiento> AND id_cuenta = <caja> AND debe > 0;
```

También se corrigió `migrar_asientos_automaticos.py` para que, si se corre de
nuevo, no vuelva a sembrar Caja.

**Ojo:** la distinción CONTADO / CTA_CORRIENTE en `config_asientos` **se queda**
(las dos dan a la misma cuenta). Sigue sirviendo para el resto de las
configuraciones y para cuando exista tesorería y haya que distinguirlas.

#### Verificado

En el navegador: cargué una factura al contado de $121.000 con IVA 21%. El
preview mostró Documentos a cobrar en el Debe, y el asiento guardado quedó
igual. Consulta final sobre `asiento_origen` + `asiento_detalle`: **los 5
asientos de factura de la base van a `1.1.03.02`, ninguno a `1.1.01.01`**.

#### Bugs encontrados de paso

1. Los tests de `test_asientos_automaticos.py` y `test_preview_asiento.py`
   **afirmaban que al contado va a Caja**, así que daban verde con la cuenta
   equivocada. Ahora además se verifica que Caja **no** aparezca en el asiento.
2. `asiento_service.crear_comprobante()` quiere un `date`, no un string: un test
   que le pasaba `"2026-09-10"` reventaba con `'str' object has no attribute
   'year'`.
3. `test_aviso_asientos.py` (nuevo) hacía `DELETE FROM asientos` a secas, que en
   una base con asientos reales los borra todos. Ahora **crea los suyos y borra
   solo los suyos**, y mide contra lo que había antes.

**Archivos**: `backend\corregir_ventas_documentos_a_cobrar.py`,
`backend\borrar_factura_prueba_751.py`, `migrar_asientos_automaticos.py`,
`tests\test_asientos_automaticos.py`, `tests\test_preview_asiento.py`,
`tests\test_aviso_asientos.py`.

**Pruebas**: `test_venta_no_toca_caja.py` (37, nuevo) deja la regla escrita en
un test, mirando las dos cosas: que en `config_asientos` las 4 ventas apunten a
`1.1.03.02`, y que **ningún** asiento de factura toque `1.1.01.01` ni
`1.1.01.02`. Con **25 suites en verde, 942 pruebas**.

Ojo con esto: los tests que dicen "va a X" dan verde aunque la cuenta esté mal,
si el test afirma la cuenta mala. Por eso ahora los tests
verifican **también que Caja NO aparezca**, y no solo que aparezca la otra.

### 4.37 El recibo con varias formas de pago, y la NC que compensa sola (02/10/2026)

El contador redefinió el flujo del recibo: **cliente → tildar facturas (y notas de
crédito) → ver el importe neto → elegir con qué se paga → ver el recibo y el
asiento → confirmar**. Antes el importe se cargaba a mano y las facturas se
aplicaban después, en otra pantalla.

#### Dos tablas nuevas

**`config_cuentas_forma_pago`** (`migrar_cuentas_forma_pago.py`, aplicada): qué
cuenta va por forma de pago, con la bandera `requiere_banco`.

| forma de pago | cuenta | requiere_banco |
|---|---|---|
| efectivo | `1.1.01.02` Fondo fijo | no |
| cheque | `1.1.01.10` Valores a depositar | no |
| tarjeta_credito | `1.1.01.09` Fondos en plataformas de cobro | no |
| transferencia, tarjeta_debito, otro | *(el contador elige el banco)* | **sí** |

**`recibo_pagos`** (`migrar_pagos_recibo.py`, aplicada): **un recibo con VARIAS
filas de pago**. Resuelve "el cliente paga 700.000 por un banco y 300.000 en
efectivo": antes había una sola `cuenta_cobro_id` para todo el recibo y el otro
medio se perdía.

```
recibo_pagos
  id_pago     PK
  recibo_id   FK recibos.id  (ON DELETE CASCADE, index)
  forma_pago  ENUM (los 6)
  importe     DECIMAL(14,2)
  cuenta_id   FK plan_cuentas.id_cuenta  (NULL = todavía no eligió el banco)
  detalle     VARCHAR(200) NULL
  creado      DATETIME
```

> `recibo_pagos` **no** se creó desde cero con los recibos viejos: nació vacía
> (0 filas sobre 66 recibos). `recibos.cuenta_cobro_id` se conserva como
> respaldo, así que los recibos cargados antes siguen usando el camino viejo.

#### La nota de crédito compensa sola

Decisión del contador: **una NC es plata a favor del cliente y no debe quedar
colgada**. Como la NC y la factura caen en la misma cuenta
(`1.1.03.02 Documentos a cobrar`, con el cliente como auxiliar), el crédito ya
está restado en el momento de emitirse: no hace falta que ningún recibo la
"pague".

En `factura_service`:

- `_creditos(db, factura_id)` = SUM de las NC **vinculadas** (`factura_relacionada_id`)
  y no anuladas.
- `recalcular_estado`: el saldo es `importe − créditos − cobrado`. Una factura de
  1.000 con NC de 300 tiene saldo **700** y queda `pagada` en cuanto entran 700
  (antes quedaba `parcial`, con 300 pendientes que ya nadie debía).
- Una NC **con** factura vinculada → `pagada` (la pantalla la muestra como
  "Compensada"). Una NC **suelta** → `pendiente` (es un crédito disponible).
- `saldo_pendiente(db, factura_id)`: el mismo número, en un solo lugar, para que lo
  que ve el contador y lo que se guarda no puedan diferir.
- Anular o reabrir una NC recalcula la factura de la que depende.

#### El asiento: un Debe por pago

`proyectar_cobranza()` en `asiento_automatico.py` arma el asiento **sin guardar**
y la usan los dos caminos: el preview de la pantalla y
`asiento_de_cobranza()`. Mismo criterio que `proyectar_venta` (§4.34): si cada uno
calculara por su lado, el preview mostraría una cosa y se guardaría otra.

```
DEBE  1.1.01.05  Banco Santander      500,00   (pago 1)
DEBE  1.1.01.02  Fondo fijo            200,00   (pago 2)
HABER 1.1.03.02  Documentos a cobrar   700,00   (· factura)
```

El Haber es **uno por factura aplicada**, con el cliente de auxiliar. Si el Debe
no da exactamente el Haber, el backend avisa con los números en vez de dejar que
`guardar_detalle` falle con "desbalanceado".

#### Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/recibos/formas-pago` | config + `requiere_banco` |
| GET | `/api/recibos/cuentas-ingreso` | solo cajas y bancos (10), no las 200 del plan |
| GET | `/api/recibos/a-cobrar?cliente_id=` | facturas con saldo + NC, con totales por SQL |
| POST | `/api/recibos/preview-cobro` | recibo + asiento armados, **sin guardar** |
| PUT | `/api/recibos/{id}/pagos` | reemplaza la lista de pagos (409 si ya tiene asiento) |
| POST | `/api/recibos/{id}/asiento` | genera el asiento de cobranza |
| POST | `/api/recibos/{id}/asiento/anular` | anula el asiento (el recibo sigue) |

`POST /api/recibos` ahora acepta `facturas: [ids]`: el backend reparte el importe
de la más vieja a la más nueva sin pasarse del saldo de ninguna
(`_repartir_entre_facturas`), que es **la misma función** que usa el preview.

> El importe de la pantalla **se puede tocar a mano** (el contador lo pidió: para
> adelantos). El backend avisa si los pagos no suman o si se pasa del saldo.

#### La pantalla

`ReciboForm.jsx` reescrita con los 5 pasos numerados. **No hace ninguna cuenta**:
el importe que ve mientras tilda sale de los saldos que ya trajo
`/a-cobrar`, y el reparto, los avisos y el asiento salen de `/preview-cobro`.

#### Verificado en el navegador

Con una factura de 1.000 + NC de 300 vinculada:

- Paso 2 mostró `1.000,00 − 300,00 = 700,00` y la NC como **Compensada**.
- Al tildarla, el importe saltó solo a **700,00** (columna "Total tildado").
- Paso 3: Transferencia 500 → Santander (con el aviso "esta forma no tiene cuenta
  fija: elegí el banco") y Efectivo 200 → **Fondo fijo solo**, desde la config.
- Paso 4 mostró el asiento con los dos Debes y el Haber, 700 = 700, sin avisos.
  Con solo 500 cargados, avisó "Los pagos suman 500,00 y el recibo es de 700,00".
- "Confirmar y generar el asiento": recibo **00000068**, **RC-000001**,
  `CONTABILIZADO`, y la factura quedó `pagada` y desapareció de "qué hay para cobrar".

#### Bugs encontrados de paso

1. **`Mapped[...] = None` crea una columna.** Puse `id_asiento: Mapped[int|None] = None`
   en el modelo `Recibo` creyendo que era un atributo en memoria: SQLAlchemy mapea
   la anotación y el INSERT mandaba `id_asiento` a MySQL → error 1054. Un atributo
   pelado (sin anotación) no se mapea. Salen de `asiento_origen`, como en Factura.
2. **Mezclar `Decimal` y `float` en el reparto**: `saldo` venía como float y
   `disponible` como Decimal → `TypeError: unsupported operand type(s) for -=`.
   Los dos van como Decimal.
3. **`plan_cuentas` no tiene columna `activo`** (era de `facturas`): el filtro de
   `cuentas_ingreso` reventaba con 500.
4. `proyectar_cobranza` quedó con el cuerpo viejo duplicado debajo del nuevo al
   refactorizar; el recorte automático cortó en la coincidencia equivocada.
5. Los avisos mostraban `500.0000` y `700.0` (Decimal crudo). Ahora usan
   `formato.pesos()`.

#### Limpieza de tests

`recibo_pagos` no tiene cascada a `asiento_origen.id_recibo` (es `ON DELETE
RESTRICT`), así que **un recibo con asiento no se puede borrar por la API** aunque
esté anulado. `tests\limpiar_prueba_recibo_pagos.py` borra por SQL, solo lo del
concepto `PRUEBA RECIBOS`, y `correr_todas.py` lo llama antes de las suites.

**Archivos**: `backend\app\models\recibo.py`, `schemas\recibo.py`,
`services\recibo_service.py`, `services\factura_service.py`,
`services\asiento_automatico.py`, `models\factura.py`, `routers\recibos.py`,
`frontend\src\pages\ReciboForm.jsx`, `frontend\src\api\recibos.js`.

**Pruebas**: `tests\test_recibo_pagos.py` (52, nuevo) cubre la compensación de la
NC, el pago partido con dos bancos, que **el preview y el asiento real dan las
mismas líneas**, el reparto entre varias facturas, y los tres errores que tienen
que avisar (pago sin cuenta, pagos que no cuadran, cobrar una NC). Con
**29 suites en verde, 1130 pruebas**.

### 4.38 La pantalla del recibo (02/10/2026)

El contador probó el flujo y encontró dos cosas rotas:

1. **Pantalla en blanco**: al confirmar un recibo, `ReciboForm` hacía
   `navigate('/recibos/${id}')` y **esa ruta no existía** en `App.jsx` (solo
   había `recibos`, `recibo-alta` y `recibo-editar/:id`). React Router no
   matchea nada y queda el `<main>` vacío.
2. **Botones que no se entienden**: en el listado había "Generar asiento" o
   "Anular asiento" según el estado, más "Editar" que iba a un stub que
   reenviaba a la misma ruta inexistente. Dos botones que cambian según el
   estado, más un "Editar" que no edita: tres Ways de no entender qué pasó.

**Solución: una pantalla del recibo** (`pages/Recibo.jsx`, ruta `/recibo/:id`).
Es lo que el contador pidió primero: *ver el recibo y el asiento juntos, y desde
ahí grabar si está todo ok*.

Tres bloques, siempre en el mismo orden:

| Bloque | Qué muestra |
|---|---|
| **El recibo** | cliente, fecha, importe, y **con qué se cobró** (cada forma de pago con su cuenta) |
| **A qué documentos se aplicó** | factura, importe, aplicado, botón Quitar |
| **El asiento** | el Debe/Haber con el comprobante, o el aviso de que todavía no está en los libros |

Y **un solo botón** en el bloque del asiento, según el estado:

- sin asiento → **Generar el asiento**
- con asiento vivo → **Anular el asiento**
- con asiento anulado → ninguno (y el aviso dice que el recibo sigue válido)

En el listado quedan solo la columna **Asiento** (el estado, como dato) y un botón
**Ver**. Los botones de acción viven en la pantalla del recibo, que es donde se ve
*para qué* se accionan.

#### Por qué el asiento no se graba solo

Como en las facturas: el recibo se guarda al cobrar, y el asiento es un botón
aparte. El contador puede cobrar hoy y asentar la semana que viene. La pantalla
nueva lo dice explícito en vez de dejar que se descubra: *"Es normal: el recibo
se guarda al cobrar y el asiento se genera cuando el contador decide"*.

Los pagos quedan **bloqueados** una vez que hay asiento: el asiento es documento
contable y sus líneas son la foto de esos pagos. Para cambiarlos hay que anular
el asiento primero, y la pantalla lo dice.

**Archivos**: `frontend\src\pages\Recibo.jsx` (nuevo), `App.jsx` (ruta),
`Recibos.jsx` (un botón, sin acciones), `ReciboForm.jsx` (navega a la ruta real).

### 4.39 El informe por centro de costos sale del PLAN DE CUENTAS, y la compra se asienta (02/10/2026)

El contador pidió: el informe de centros tiene que tomar los gastos del plan de
cuentas (Administración / Comercialización / Financiero), no "la serie de gastos"
que se había creado antes. Y que cada centro tenga su total.

#### El informe ya no lee compras: lee el MAYOR

`informe_centros()` ahora suma `asiento_detalle` de los asientos
**CONTABILIZADOS**, no filas de la tabla `compras`. Un `GROUP BY` y listo: el
informe dice **lo que está en los libros**, no lo que se está por cargar.

Los centros **son** las cuentas de segundo nivel de la rama `6 GASTOS`
(`RAIZ_GASTOS = "6"` en `informes_service.py`), y las líneas son sus cuentas
imputables. No hay `optgroup` hardcodeado: si el contador agrega una cuenta abajo
de `6.1`, sola aparece en el informe.

```
6.1  Gastos de administración     225.000,00
       6.1.03 luz-agua       1 mov    45.000,00
       6.1.10 personal        1 mov   180.000,00
6.2  Gastos de comercialización    32.000,00
       6.2.01 publicidad      1 mov    32.000,00
6.3  Gastos financieros            21.000,00
       6.3.01 intereses       1 mov    21.000,00
6.4  Otros gastos                   0,00
                            TOTAL     278.000,00
```

**Verificado cuenta por cuenta**: los 14 totales del informe dan **exactamente**
el mismo número que `GET /api/mayores/{cuenta}` (`saldo_final`). Misma fuente,
mismo filtro (`estado = 'CONTABILIZADO'`).

Lo que **NO** cuenta: asientos en borrador y anulados. No llegaron al libro.

`GET /api/informes/centros-cuentas` devuelve el mismo árbol **sin importes**,
para que las pantallas elijan una cuenta de gasto sin repetir la lista.

#### La compra: una sola elección y genera asiento

`compras` elige **una** cosa: la **cuenta de gasto del plan** (`6.1.03 luz-agua`).
El centro sale de esa cuenta, no se elige aparte.

El contador dijo explícitamente que **no** quería las dos listas:

> *"En la carga de la compra seleccionamos el centro de costo, tipo de gasto"*
> → *"Elegir la cuenta del plan (Recomendado)"*

Porque las dos listas ya se contradecían con el plan: *Intereses* y *Publicidad*
estaban en "Administración" cuando en el plan son `6.3` y `6.2`. Con una sola
lista no pueden discrepar.

`compras.centro_costo_id` y `tipo_gasto_id` quedan **sin uso** (nullable, con
los datos viejos). No se borraron: es información vieja y dejarla no cuesta nada.

#### El asiento de compra

```
Debe   <cuenta de gasto>      la 6.x que eligió el contador     (neto)
Debe   1.1.05.04 IVA crédito fiscal                                (iva)
Debe   1.1.05.06 Percepciones a favor                         (percepción)
                              Haber  2.1.01.01 Proveedores            (total)
```

- Las dos fijas son **deudoras del ACTIVO** (`1.1.05`), no cuentas de IVA a
  pagar: el IVA que pagás a un proveedor es un **crédito tuyo**. El contador lo
  corrigió: *"son cuentas deudoras, recordá que son cuentas de balance del
  activo"*. (Mi primer error fue buscar `%IVA%` en el plan y no encontrar
  `1.1.05.04`, que se llama **IVA crédito fiscal**.)
- **La percepción NO se resta del IVA**: son dos créditos distintos y por
  separado. (El contador primero dijo que sí y después se corrigió.)
- El **Haber de Proveedores es el `total` de la compra tal cual lo calcula la
  app** (`neto + iva + percepción`). El asiento cierra con el número que el
  contador ya ve en pantalla, sin ajuste.
- `2.1.01.01 Proveedores` con auxiliar `PROVEEDOR`, así que el mayor muestra la
  deuda por proveedor.

Las tres cuentas fijas están como constantes en `asiento_automatico.py`
(`CUENTA_IVA_COMPRA`, `CUENTA_PERCEPCION_COMPRA`, `CUENTA_PROVEEDORES`), no en
`config_asientos`: la compra tiene **una sola variante** (no hay "artículos" ni
"al contado" como en la venta), así que una fila de configuración sería
indirección sin contenido. La cuenta que SÍ cambia en cada compra la elige el
contador.

#### La NOTA DE CRÉDITO del proveedor es el mismo asiento al revés

Cuando el proveedor devuelve mercadería, la nota no es una compra: es la baja de
una compra anterior. Los tres Debes van al Haber y el de Proveedores al Debe, con
la misma cuenta de gasto. Si se armara "hacia adelante", la nota sumaría gasto
en vez de restarlo y el informe mostraría más gasto del que hubo.

Solo se invierte la familia `CREDITO`. Un `DEBITO` es un aumento de la deuda y
va como la compra.

#### Los comprobantes de compras NO se mezclan con los de ventas

El contador lo advirtió: *"los comprobantes de compras no se deben mezclar con
los comprobantes de ventas, tienen los mismos nombres"*.

- `FP` (**F**actura de **P**roveedor) con `origen = 'COMPRA'`, aparte de `FV`
  (`origen = 'FACTURA'`).
- La numeración va por `(codigo_comprobante, id_ejercicio)`: `FP-000001` y
  `FV-000001` son **series separadas**. Una compra nunca puede sacar el número de
  una venta.
- `asiento_origen` gana la columna `id_compra` (antes solo tenía `id_factura` e
  `id_recibo`) con su `UNIQUE (origen, id_compra)`: una compra, un asiento.
- El filtro por **módulo** de Asientos tiene **Compras** propio, para no meter
  los gastos adentro de "Facturas".

#### Igual que facturas y recibos: guardar NO es asentar

`POST /api/compras/{id}/asiento` es un botón aparte (solo admin).
`POST /api/compras/preview-asiento` muestra el asiento sin guardar nada, con la
**misma función** (`proyectar_compra`) que genera el real. El listado muestra un
aviso con cuántas compras están sin asentar y cuánto dinero no llegó a los libros.

Una compra **con asiento no se borra** (409): el asiento es documento contable.
Anular la compra **no** anula el asiento, ni al revés: son dos cosas distintas.

#### Bug viejo encontrado: las compras NUNCA funcionaron

`Compra.proveedor_id` apuntaba a `clientes.id` y la validación chequeaba un
`.tipo` que esa tabla no tiene → **500 siempre**. Y hay **0 compras** en la base
después de meses de uso: nunca se pudo cargar una.

Los proveedores viven en `proveedores` (que apunta a `personas`), no en
`clientes`. Corregido el relationship y la validación.

**Migración** (`backend\migrar_compra_cuenta_gasto.py`, idempotente, **no borra
nada**): `compras.cuenta_gasto_id` + FK; `centro_costo_id` y `tipo_gasto_id` a
NULL; `asiento_origen.id_compra` + índice único + FK; comprobante `FP`.

**Tests**: `test_informe_centros.py` (23) mide **diferencias** contra la línea de
base, no valores absolutos, porque la base puede tener gastos reales cargados.
`test_compra_asiento.py` (39) cubre el asiento, la NC invertida, que guardar no
mueve, que asentar sí, que anular el asiento saca el gasto, que con asiento no se
borra, y el filtro sin_asiento.

**Pendiente**: ninguno de esta parte. El informe de resultados se arregló
después (§4.40).

### 4.40 El informe de resultados también sale de los libros (02/10/2026)

El desfasaje que quedó después de §4.39: el informe por centro decía "gastos
100.000" (movimientos reales) y el de resultados decía "gastos 0" (suma de la
tabla de compras). **Dos informes del mismo estudio que no coinciden.**

#### Los DOS lados salen de los libros

No solo el gasto: también el ingreso. Antes el ingreso salía de la tabla de
`facturas` y el gasto de la de `compras`. Eso mezclaba dos fuentes — si una
factura estaba cargada pero sin asentar, el informe decía "ingreso X" y el libro
no tenía nada. **Un estado de resultado con un lado de los documentos y el otro
de los libros no tiene sentido: el neto era un número inventado.**

Ahora:

```
ingresos (rama 4 del plan) − costos (rama 5) − gastos (rama 6) = neto
```

Las **tres** ramas del resultado, leídas de los asientos contabilizados.

#### Una sola función para los dos informes

`saldos_rama(db, codigo_raiz, que, desde, hasta)` es lo que usan **los dos**:
`informe_centros` pasa `"6"` y `informe_resultados` pasa `"4"`, `"5"` y `"6"`.

Por eso **no pueden contradecirse**: el gasto del informe de resultados es
literalmente el mismo objeto que devuelve el informe por centro de costos. No es
"están calculados parecido", es que salen del mismo `GROUP BY`.

**El signo sale de la CUENTA, no de la posición**: `deudora_acreadora ==
'ACREEDORA'` → el saldo es `haber − debe` (ingresos); si no, `debe − haber`
(gastos y costos). Por eso el mismo helper sirve para las tres ramas sin
saber de antemano de qué lado está cada una.

#### Apareció la rama 5 (COSTOS), que antes ni se miraba

El informe viejo no tenía costos. El plan tiene `5.1.01 costo por venta` y
`5.2.01 costo por servicios`, y un estado de resultado sin costo de ventas está
incompleto. Ahora hay un bloque **Costos** entre Ingresos y Gastos, y el neto es
`ingresos − costos − gastos` (con `total_egresos` a la vista).

#### Verificado

`test_informe_resultados.py` (19) mide **diferencias** contra la línea de base y
comprueba, entre otras cosas, que los dos informes dan **el mismo total general y
el mismo total de CADA centro** — no solo el número grande.

Bug de test que salió al hacerlo: comparar un informe **sin filtro de fechas** contra
otro **filtrado a 2027** no dice nada si la base tiene movimientos de 2026. Las
dos suites (`test_informe_centros` y `test_informe_resultados`) ahora capturan
una línea de base **con el mismo filtro** para esa comparación. En centros
pasaba de casualidad porque las cuentas de gasto estaban en cero; el día que se
carguen de verdad fallaba.

### 4.41 Períodos contables: abrir y cerrar cada mes del ejercicio (02/10/2026)

Lo que pidió el contador: **dentro de cada ejercicio se abren y cierran los
períodos, numerados del 1 al 12**. Con el período cerrado no se puede trabajar:
ni cargar, ni anular, ni modificar. El ejemplo que dio: "si estoy en octubre y
quiero anular un recibo de septiembre, y septiembre está cerrado, no me debería
dejar".

Antes no se podía: el ejercicio tenía un solo `cerrado` y ese flag **solo se
miraba al crear un comprobante**. Anular, modificar y cargar documentos pasaban
sin ningún control.

| Decisión | Por qué |
|---|---|
| Los períodos son los **meses DEL EJERCICIO**, no los del calendario | Con el ejercicio 01/09/2026 → 31/08/2027, el período 1 es septiembre 2026 y el 12 es agosto 2027. Por eso van numerados del 1 al 12 |
| Nacen los 12 **abiertos** | Si arrancaran cerrados no se podría cargar nada el primer día. El contador trabaja y va cerrando mes a mes |
| Las fechas se **guardan en la fila** | "Esta fecha cae en un período cerrado" tiene que ser un `WHERE fecha_inicio <= ? AND fecha_fin >= ?`, que usa índice, no una cuenta de meses |
| Cerrar un mes con documentos **se puede**, avisando cuántos hay | El cierre es una **trava**, no una validación contable. Lo que no se puede es cerrar sin haber visto el aviso → el backend exige `forzar: true` en el segundo intento |
| **Cerrado no bloquea leer** | Se sigue consultando el Mayor, los informes y los listados. Cerrado es "no escribas", no "no mires" |
| Solo **admin** abre y cierra | Es la decisión que frena la contabilidad |
| Los dos rechazos van **409** | "No se puede trabajar en esta fecha" — esté cerrado el ejercicio, el mes, o la fecha caiga fuera — es la misma cosa para la pantalla. Antes el de ejercicio era 400 y el de período 409, y obligaba a tratar dos casos idénticos |

**Dónde frena** (`periodo_service.verificar_abierto`): crear, anular, reabrir,
borrar, modificar y asentar de facturas, recibos, compras, asientos manuales,
comprobantes internos, cambiar líneas y contabilizar.

**Dónde NO frena, a propósito**: *aplicar* un recibo a una factura. Cobrar en
octubre una factura de septiembre es lo normal; el período que manda es el de la
fecha del recibo, y aplicar no cambia importe sino a qué factura se imputa.

El error dice el número, el nombre, las fechas, y **cómo reabrirlo**. Sin eso el
contador insiste con la misma operación.

`test_periodos.py` (38) trabaja contra el **período 12** (agosto 2027), que está
vacío, así que no toca los meses que el contador ya usó, y limpia lo suyo por
SQL al terminar.

### 4.42 Nunca más tests que borren datos reales (02/10/2026) — ver `AGENTE.md` §6 bis

El día que se corrieron todas las suites quedaron **0 asientos y 0 comprobantes
internos** en la base: siete suites tenían `DELETE FROM asientos` a secas, y
corrían contra la base del estudio. No había respaldo de asientos.

Dos cosas que no se ven en un test:

1. Las suites miden **diferencias contra una línea de base**, y la línea de base
   se tomaba **después** de borrar. Por eso los 1219 tests dieron verde con la
   base vacía: el defecto era invisible para un test que solo mira sus números.
2. La numeración correlativa de los comprobantes hace que un resto de una
   corrida anterior rompa la suite siguiente de forma **no determinista**:
   `test_motor_contable` checks "el número arranca en 1" y veía `OP-000015`.

Lo que se hizo:

| Herramienta | Qué hace |
|---|---|
| `tests/borrar_prueba.py` | Un solo lugar que sabe qué es dato de prueba (punto de venta reservado, "PRUEBA" en el concepto, CUIT/DNI de lista) y cuál no. `limpiar_todo`, `limpiar_asientos`, `limpiar_comprobantes`, y `huella` + `comparar` |
| `tests/respaldar_todo.py` | Respaldo de **todas** las tablas en `.sql`. La primera versión tenía la lista escrita a mano y se olvidaba de 24 tablas — `bal_rt54_notas` (88), `bal_rt54_valores` (238), `config_indices_moneda` (404). Ahora toma todas menos `usuarios.password_hash` |
| `tests/probar_respaldo.py` | Restaura el `.sql` en una base vacía y compara **fila por fila**. "Un respaldo que nunca se restauró no es un respaldo" |
| **Huella digital** en `correr_todas.py` | Cuenta las filas reales por clave primaria **antes y después**. Si alguna bajó, la corrida termina en `FALLO` diciendo qué tabla y cuáles. Esta es la prueba que faltaba |
| `tests/test_huella.py` (7) | Verifica que la huella **avisa cuando tiene que avisar y se calla cuando no** |

140 recibos de prueba que habían fugado de las corridas (el mismo importe en las
mismas fechas, del mismo cliente) se borraron **con autorización del contador**
el 02/10/2026, con respaldo previo.

Pendiente: la solución de fondo es una **base de pruebas separada**
(`GESTION_DB_NAME=gestion_contable_test`), donde los tests puedan borrar lo que
quieran. Mientras no exista, la regla de `AGENTE.md` §6 bis es la que sostiene.

### 4.43 Asientos especiales (02/10/2026)

Los tres que pidió el contador: **impuesto nacional y provincial**, **ajuste
mensual** y **ajuste de balance**.

No son automáticos como el de una factura —el sistema no sabe qué cuentas van ni
qué importe— así que **no hay pantalla aparte**: es el mismo editor de líneas, con
un selector que pone el nombre y la guía. Agregar tres pantallas sería el mismo
formulario tres veces.

Lo que ya estaba y se corrigió:

- **De = Haber para guardar.** El botón Guardar ya se bloqueaba, pero solo miraba
  la diferencia. Con todo en cero daba "Cierra: Debe = Haber": 0 − 0 da cero, y
  lo que se había escrito era nada. Ahora además exige que haya al menos una
  línea con importe **y** cuenta elegida, con un mensaje distinto para cada caso
  (escribir "6.1.10" en el buscador no elige la cuenta: hay que apretar la
  sugerencia, y si no se avisa el contador no entiende por qué no se guarda).

**Bug viejo encontrado de paso**: el buscador de cuentas del editor de asientos
**nunca funcionó**. `plan_cuentas` se registraba antes que `asientos` en
`main.py`, así que `/api/plan-cuentas/buscar` caía en
`/api/plan-cuentas/{cuenta_id}` y devolvía **422** ("cuenta_id: Input should be a
valid integer"). FastAPI busca las rutas en el orden de registro. Se_reordered
en `main.py` y ahora devuelve las cuentas.

### 4.44 Listado de clientes: scroll, orden y total (02/10/2026)

- `.tabla-envoltura` → **`.tabla-scroll`**: con muchos clientes la tabla crecía
  sin límite y había que llegar al final con el scroll del mouse. Ahora la altura
  es fija, el encabezado queda fijo y el total siempre a la vista.
- **Ordenar por columna** (apellido, razón social, fecha de alta, cuenta, CUIT,
  localidad). El `ORDER BY` va en **SQL** (`cliente_service.ORDENES`), no en el
  navegador: con 5.000 clientes el frontend tendría que traerlos todos para
  recién ahí compararlos, y el listado del Excel —que sale del backend— no
  coincidiría con la pantalla. Un orden desconocido no es error: cae al de
  siempre.
- El total va **dentro** del `tbody` como última fila, no debajo de la tabla: si
  no, con muchas filas se iba al final de la página.
- **Bug del menú**: el desplegable usaba `var(--surface)`, que es blanco al 4%.
  Se veía el menú de abajo atravesado. Un desplegable tiene que ser opaco.

### 4.45 Vencimiento a 7 días y deuda vencida (02/10/2026)

- Una factura sin `fecha_vencimiento` **sale a los 7 días de su fecha** (`DIAS_PLAZO`).
  Sin esto, todas las facturas viejas salían "al día" y el informe de deuda no
  servía para nada. **`DIAS_PLAZO = 7` vive en UN solo lugar**: el backend
  (`informes_service`), y la pantalla lo recibe en la respuesta. Si se duplica el
  número en el frontend, un día los dos cambian distinto.
- El vencimiento se calcula en el **frontend** y **solo si el campo está vacío**
  (no pisa una fecha que escribió el usuario), y **no al editar** (al abrir una
  factura vieja no le cambia la fecha de vencimiento por detrás).
- El estado de deuda ahora trae `dias_vencida`, `vencido`, `cantidad_vencida` y
  `total_vencido`, con el filtro `solo_vencidas`.

### 4.46 El buscador de cliente escribible, en 7 pantallas (02/10/2026)

- El `<select>` de clientes era una **lista desplegada con TODOS los clientes**:
  con muchos había que buscarlos scrolleando adentro del desplegable. Ahora es un
  campo donde se **escribe** (`BuscadorCliente.jsx`), en: estado de deuda, recibos,
  facturas, anticipos, anticipos pendientes y los dos formularios de alta.
- **Busca por nombre, CUIT o DNI**, y **perdone las tildes**: escribir "Perez"
  encuentra a "Pérez" (`normalizar` con `NFD`), y también el CUIT con o sin
  guiones.
- `BuscadorCliente` acepta `disabled`, para los casos donde el cliente ya no se
  puede cambiar (editar un anticipo: el `<select>` viejo lo tenía así).
- **Bug encontrado al probar**: `const clienteElegido = clientes.find(...)` antes
  de `const [clientes, setClientes] = useState([])` → *"Cannot access 'clientes'
  before initialization"* y la pantalla **en blanco**. Los cálculos derivados van
  **después** de los `useState`.
- **Restore del scroll**: saqué el `max-height` de `.tabla-scroll` para probar otra
  cosa y le saqué el scroll a **todas** las pantallas de golpe (recibos, compras,
  informes…), no solo a clientes. **El `max-height: 62vh` es lo que hace esta
  clase**; no sacarlo. Con la caja, el `position: sticky` del encabezado va en
  `top: 0` (el scroll es el de la caja, no el de la página).

### 4.47 Informe de cuenta corriente (02/10/2026)

Nuevo informe: **las partidas abiertas sumadas por cliente**, con teléfono. Es el
informe del día para ir a cobrar; **NO** reemplaza al estado de deuda (que sigue
siendo el detalle de un cliente, comprobante por comprobante).

- `informe_cuenta_corriente(db, desde, hasta, solo_vencidos)` agrupa por
  `cliente_id` y separa **vencido / no vencido**. Son dos cobranças distintas: lo
  vencido hay que ir a buscarlo hoy, lo que tiene plazo se cobra solo. Un total
  único esconde las dos.
- Los **totales van en el backend** (regla del proyecto): si los sumara el
  navegador, el número de la pantalla y el del Excel no coincidirían.
- **El orden NO es alfabético**: es por importe vencido de mayor a menor, y a igual
  monto por días de atraso. Al que va a llamar le interesa el que más debe; el
  orden alfabético deja al peor deudor al final, que es justo el que hay que ver
  primero. Por eso no se puede cambiar desde la pantalla.
- El **teléfono** se arma con el código de área (`(3571) 452525`): el teléfono solo
  no se puede marcar. Los teléfonos se traen en **una sola consulta** con `IN (...)`,
  no cliente por cliente (si no, N consultas para armar una tabla). La pantalla
  avisa cuántos clientes están sin teléfono cargado.
- Para poder agrupar hizo falta **`cliente_id` en los items del estado de deuda**,
  que no lo traía (no se mostraba, pero sin él no se sabe a qué cliente pertenece
  una partida: dos clientes pueden llamarse igual).
- `GET /api/informes/cuenta-corriente`, `.../export.xlsx`, pantalla
  `InformeCuentaCorriente.jsx`, ruta `/informe-cuenta-corriente`, y es el **primero
  del grupo Informes** del menú (es el informe del día; los otros son de cierre).
- El botón "Detalle" manda a `/estado-deuda?cliente=N`: `EstadoDeudaTotal` ahora
  lee ese parámetro con `useSearchParams`, si no el contador llegaba desde la lista
  y tenía que volver a buscar el cliente a mano.

### 4.48 Gráfico de ingresos y egresos mes a mes (03/10/2026)

En el dashboard, en el lugar del antiguo "Estado del proyecto" (que era andamiaje de desarrollo y no le hacía falta a nadie).

- **Chart.js** (`npm install chart.js`), con **`import` selectivo**: se registran solo `BarController`, `BarElement`, `CategoryScale`, `LinearScale`, `Tooltip` y `Legend`. Con `chart.js/auto` se registraban **todos** los tipos de gráfico (líneas, tortas, radar, geográfico) y el bundle subía 210 KB; así baja a 154 KB. **No usar `chart.js/auto`** salvo que de verdad se dibuje otro tipo de gráfico.
- **Los 12 meses DEL EJERCICIO** (septiembre → agosto), no los del año calendario: el contador compara septiembre con septiembre. Vienen de `periodo_service.listar()`, así que ya existían.
- `resultado_por_periodo()` hace **UNA sola consulta** `GROUP BY cuenta + año + mes` para los 12 meses. Llamar a `saldos_rama` por mes serían 24 consultas para pintar un gráfico.
- **Usa las TRES ramas (4, 5 y 6), no dos.** Los costos (rama 5) van al mismo cubo que los gastos: los dos son egresos, y en el gráfico son una sola barra. La etiqueta dice **"Egresos"**, no "Gastos".
  - **Si se hubiera dejado afuera la rama 5, el neto del gráfico y el del informe de resultados no darían lo mismo** (el del informe es `ingresos − costos − gastos`). Con 45.000 de costo por venta: el gráfico daba 370.000 de neto y el informe 325.000. Es la contradicción que el proyecto prohíbe.
- Los importes salen **de SQL**, nunca de sumar filas en el navegador (regla del proyecto). Verificado comparando el `neto` del gráfico contra el de `/informes/resultados`.
- Si los 12 meses están en cero sale un mensaje (*"Todavía no hay ingresos ni gastos registrados"*), **no una caja vacía**: una rejilla en cero parece una pantalla rota y además Chart.js no escala bien un rango todo cero.
- `chart.destroy()` en el `useEffect` de limpieza: sin eso se apila un gráfico sobre el anterior y el canvas queda borroso.
- **La ruta del dashboard es `/`, NO `/dashboard`.** `/dashboard` no matchea ninguna ruta y el `<Outlet/>` queda vacío: pantalla en blanco sin error en consola. Es la causa de un falso "está roto".
- Sin asientos **contabilizados** el gráfico no muestra nada: lee `asiento_detalle` de asientos contabilizados, no las facturas. Es la regla "guardar no es asentar".
- **Tests**: no hay suite propia. La prueba fue crear asientos de prueba, **medir los píxeles del canvas** (contar los verdes de ingresos y los rojos de egresos: si hay miles, las barras están pintadas) y después borrar por id de asiento.

### 4.49 Tests que dejan datos si se caen a mitad de camino (03/10/2026)

Un script de prueba creó 3 asientos y **se cayó en la línea siguiente**, al imprimir: los 3 quedaron en la base. Se detectaron porque el borrado posterior dejó 3 asientos donde se esperaba 0.

**No es un problema del script, es del orden**: si el script crea y después falla, no tiene cómo limpiar.

**Cómo se hace**: `try/finally` con el borrado en el `finally`, o borrar por **id de asiento** y **verificar el contador al final**. Nunca `DELETE FROM tabla` sin `WHERE`. La huella de `correr_todas.py` no lo detecta, porque solo compara contra el respaldo que se tomó al empezar la corrida: si los datos se crean **después** del respaldo, no los ve.

### 4.50 Libro de IVA Ventas (03/10/2026)

Una línea por **comprobante emitido**, en orden correlativo **por día**, con el total de cada columna al pie. En Informes, después de la cuenta corriente.

- **Sale de `facturas`, NO de los asientos** — al revés que todos los otros informes, y a propósito. El libro de IVA registra los **documentos emitidos**: una factura guardada y todavía sin contabilizar igual emitió comprobante y ese IVA hay que pagarlo. Si saliera del libro contable, escondería justo las facturas que faltan pagar.
- **El signo lo da `tipo_comprobante`, no el importe.** Las tres familias (factura / NC / ND) se guardan con importes **positivos**: una nota de crédito suma hacia abajo, una de débito hacia arriba. Buscar el signo en el número contaría dos veces.
- **La correlativa se reinicia cada día**, que es como la pide el libro. Por eso el "Nº" vuelve a 1 cada vez que cambia la fecha: se arma en dos pasos (SQL trae las filas ordenadas, el acumulado en Python reparte los números dentro de cada fecha).
- Las **anuladas no entran** salvo que se pidan: el filtro va en el `WHERE`, no después de traerlas.
- `Cliente.nombre_completo` es un **método de Python** (arma el nombre desde `persona`), no una columna: SQL no lo puede traer. Por eso la consulta pide el `cliente_id` y los nombres se resuelven después, en una sola consulta con `joinedload(persona)` (sin eso sería una consulta por línea).
- `percepcion` y `no_gravado` se agregaron a `facturas` (`migrar_iva_ventas.py`, idempotente). **No suman al `importe`**: son columnas informativas. Si sumaran, el neto del libro dejaría de cuadrar con la factura.
- La migración solo completa las facturas con `neto` en blanco (les pone 21%). Las que ya lo tienen no se tocan: si el contador lo cargó a mano, es intencional.
- Redondeo: `neto = importe / (1 + alícuota)` con **2 decimales**, e `iva = importe - neto`. A 2, porque es lo que ya usa el resto del sistema (la factura 00000024 tiene 14876.03 / 3123.97 sobre 18000).

**Tres bugs que salieron al probar:**

1. Los campos nuevos se agregaron a la base y al modelo pero **no al schema de creación** (`FacturaBase`) ni al de salida (`FacturaOut`): el sistema los aceptaba y los tiraba. Y si no están en `FacturaOut`, al editar una factura los campos salen vacíos y al guardar se pisan en 0.
2. Al declararlos `float = 0` (no opcionales), las facturas **anteriores a la migración** —que tienen `NULL` ahí— hacían que `GET /api/facturas?cliente_id=N` devolviera **500**. Son `float | None`: el `NULL` además significa algo distinto de cero ("nunca se cargó").
3. `_desglosar_en_factura` los tiene que copiar **a mano** (`getattr(datos, "percepcion", 0) or 0`), porque el preview del asiento no los trae.

### 4.51 El listado de clientes ahora filtra al escribir (03/10/2026)

**Bug reportado por el contador**: escribió "dist" en el buscador de clientes y la tabla no cambió nada. Parecía que la búsqueda estaba rota.

**No estaba rota: la búsqueda en el backend funciona perfecto** (probado: `dist`, `DIST`, `distr`, `ibuidora` y el CUIT con y sin guiones devuelven todos Distribuidora Norte). Lo que pasaba es que **`Clientes.jsx` solo buscaba al apretar "Buscar"** (o Enter). Se escribía el nombre y la lista seguía igual, que es justo lo que hace pensar que algo falló.

**El arreglo**: `escribir()` + un `useEffect` con **300 ms de espera** sobre `filtros.q`. Se escribe y filtra.

- Los 300 ms son para no ir a la base con cada tecla: "distribuidora" son 11 pedidos donde alcanza con uno.
- Un `useRef` (`desdeElCampo`) distingue lo que escribió la persona de lo que saltó solo (cargar una variante guardada, el botón Limpiar): en esos casos la búsqueda la pide quien la pidió y el efecto haría una segunda al pedo.
- El botón "Buscar" **se queda**: sirve para aplicar los filtros de período y fecha de una sola vez.
- Ojo: **esto quedó distinto del resto**. Las otras pantallas ya filtraban al escribir (el buscador de cliente escribible, §4.46), y el listado de clientes era el único que no. Dos comportamientos distintos en el mismo programa.
- Probado en el navegador: `dist` → 1 cliente, `PEREZ` sin tilde → Pérez, `tol` → 2, `20-26473675-8` → 1, `noexiste` → "No hay nadie que coincida".

### 4.52 El lanzador del escritorio (`iniciar.bat`) (03/10/2026)

Acceso directo en el escritorio ("Gestion Estudio Contable") que apunta a `iniciar.bat`. Doble clic y arranca todo.

- **Un `.bat`, no un programa instalado**: no hay que instalar nada, no necesita internet y se copia a otra máquina tal cual. Si se rompe, se arregla el `.bat` y el ícono del escritorio sigue sirviendo.
- Levanta el backend (uvicorn, 8010) y **la versión compilada** (`npm run preview`, 4173), y abre el navegador solo. Se usa el `preview` y no el `dev` porque sirve `dist`: carga más rápido. El `dev` (5173) es para probar cambios con recarga automática.
- **Si el puerto ya está ocupado, no arranca una segunda copia**: si el usuario abre el acceso dos veces, se usa el que ya está corriendo.
- **La ventana queda abierta** con un cartel de "presioná una tecla para cerrar". Es a propósito: si se cerrara sola, los servidores seguirían corriendo en segundo plano sin forma de saberlo ni de apagarlos. Al apretar una tecla se apagan los dos, buscándolos **por puerto** (`netstat` + `taskkill /PID /T`) y no por nombre de proceso.
- **OJO**: sirve `dist`, o sea la versión **compilada**. Si se tocó código hay que recompilar con `build_frontend.bat` antes de volver a usar el ícono. Si no, se ven los cambios viejos y parece que el programa "no agarró" lo que se hizo.
- **Bug del arranque**: con `cmd /c "cd /d "ruta" && ..."` Windows mezcla las comillas y el comando queda partido. El backend **no arrancaba nunca** y el ícono abría el navegador sin datos — seemed andando igual. Se arregla con el `/D` del `start`, que cambia de carpeta sin comillas anidadas. **Se detectó probando** (apagar todo y arrancar de cero), no leyendo el archivo: el `.bat` estaba bien escrito.
- Falta un `/health` real para esperar: el endpoint es `/health`, **no** `/api/health`.

### 4.53 Qué NO debe subirse a GitHub, y el acceso directo que se creó (03/10/2026)

Antes del commit se revisó todo lo que estaba sin versionar, porque **`.gitignore` no cubría los respaldos** y se Columbaban 23 archivos `.sql` con volcados completos de la base.

- **`.gitignore` ahora tiene `*.sql` y `backend/respaldos/`**, con el porqué escrito adentro. Los `.sql` son respaldos: CUITs, DNIs, nombres, teléfonos, emails, importes y hashes de contraseñas. Se generan solos en cada corrida de pruebas (`tests/` accumulates uno por vez), así que sin la regla se cuelan en cada commit.
- **`backend/app/config.py` SÍ se versiona** y tiene `jwt_secret = "clave-temporal"` y `db_password = ""`. Vacíos no filtran nada en local, pero **`clave-temporal` con cualquiera que tenga el repo puede fabricar un token**. Si el repo llega a ser público, cambiarlo primero.
- `.env` sí estaba cubierto desde el principio (y verificado: ignorado, nunca staged). Contiene la clave de MySQL, el secreto de JWT y la contraseña de Gmail.
- El commit `8f5369a` lo hizo el contador a mano con `git add -A`, así que entraron también 38 scripts de diagnóstico. No es problema (son texto, sin datos), pero conviene saber que están.

| 12 | Sacar el `max-height` de `.tabla-scroll` le quitó el scroll a **todas** las tablas de golpe, no solo a la de clientes | cerrado 03/10/2026 (§4.46) |
| 13 | Los formularios de alta quedaban **en blanco**: un `clientes.find(...)` antes del `useState` de `clientes` ( *"Cannot access 'clientes' before initialization"* ) | cerrado 03/10/2026 (§4.46) |
| 14 | El **listado de clientes no filtraba al escribir**: solo al apretar "Buscar". No era un bug del backend (la búsqueda funciona), sino de la pantalla. Se veía como búsqueda rota | cerrado 03/10/2026 (§4.51) |
| 15 | El **lanzador del escritorio no arrancaba la base de datos** por comillas anidadas de Windows. Abría el navegador sin datos y parecía andando | cerrado 03/10/2026 (§4.52) |
| 16 | Los campos del Libro de IVA (`percepcion`, `no_gravado`) se agregaron a la base y al modelo pero **no a los schemas**: el sistema los aceptaba y los tiraba. Y al declararlos `float = 0` rompía el listado de facturas con **500** (las viejas tienen `NULL`) | cerrado 03/10/2026 (§4.50) |
| 17 | Una cuenta bancaria con **solo alias** daba **500**: no hay código de banco y `bancos.codigo` es la clave primaria, que no admite NULL | cerrado 03/10/2026 (§4.54) |

---

## 8. Restricciones del proyecto

- **No agregar código de más.**
- Dejar **posible el backend con base de datos** para guardar usuarios en el futuro.
- Que sea **posible subir a Vercel**.
- **Consultar siempre** cualquier cambio antes de hacerlo.
