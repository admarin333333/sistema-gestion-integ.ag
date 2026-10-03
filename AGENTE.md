# AGENTE.md — Proyecto 2: Sistema de gestión estudio contable

Guía de trabajo para cualquier agente (humano o IA) que toque este proyecto.

> **Última actualización:** 01/10/2026

---

## 1. Qué es este proyecto

**Sistema de gestión para un estudio contable** — web administrativa para cargar
clientes, facturar, cobrar y ver el estado de cuenta, con login y roles.

- **Carpeta:** `C:\proyecto-gestion-contable`
- **Dónde corre:** **todo local** — la base de datos y el sistema están en la PC
- **Cliente:** principiante, español rioplatense (voseo)
- **Web pública:** ya existe en el Proyecto 1 (`fiverr/portfolio/contable/`) → **se reutiliza, no se rehace**

> ⚠️ **No confundir con el Proyecto 1** (`fiverr/`, el negocio de venta de webs en Fiverr)
> ni con el proyecto Webflow (Adriana Marín). Son tres cosas distintas.

---

## 2. Reglas del cliente (NO romper)

| # | Regla |
|---|---|
| 1 | **Consultar siempre** antes de hacer cualquier cambio. |
| 2 | **No agregar código de más.** Nada que no se pidió. |
| 3 | Responder en **español rioplatense (voseo)**. |
| 4 | Principiante: **pasos cortos, un tema por vez**, cerrar con checkpoint A/B/C/D. |
| 5 | Lo técnico se explica **en criollo** antes de dar pasos. |
| 6 | Todo dato externo se **cita con fuente y fecha**. |

---

## 3. Stack (lo definió el cliente, no cambiar sin consultar)

| Capa | Tecnología |
|---|---|
| Frontend | **React** |
| Backend | **Python + FastAPI** |
| Base de datos | **MySQL** |
| ORM | **SQLAlchemy** |
| Validaciones | **Pydantic** |
| Autenticación | **JWT** |
| PDF | una librería de Python |
| API | REST (FastAPI) |
| Futuro | Preparado para integración con **ARCA** (esta versión **no conecta**) |

### Entorno verificado el 30/09/2026

| Tool | Estado |
|---|---|
| Python | ✅ **3.12.5** |
| pip | ✅ 24.2 |
| Node | ✅ **v20.17.0** |
| npm | ✅ 10.8.2 |
| Git | ✅ 2.45.2 |
| MySQL (CLI en PATH) | ❌ no encontrado |
| **XAMPP** | ✅ `C:\xampp` → `C:\xampp\mysql\bin\mysql.exe` |
| Puerto 3306 | ✅ **escuchando** (MySQL activo) |

> Para llamar a MySQL desde PowerShell hay que usar la ruta completa:
> `C:\xampp\mysql\bin\mysql.exe -u root`

---

## 4. Decisiones tomadas

| Tema | Decisión | Fecha |
|---|---|---|
| Carpeta | `C:\proyecto-gestion-contable` | 30/09/2026 |
| Dónde corre | **Todo local**: BD en la PC + sistema en la PC | 30/09/2026 |
| Roles | **Admin + Operador** | 30/09/2026 |
| Vercel | Que **sea posible** subirlo a futuro; hoy **no** se sube | 30/09/2026 |
| Web pública | Reutilizar `fiverr/portfolio/contable/` | 30/09/2026 |
| ARCA | Arquitectura preparada, **sin conectar** | 30/09/2026 |
| Fases | Se avanza **una fase por vez**, aprobada por el cliente | 30/09/2026 |
| Navegación frontend | **React Router** (URLs reales, `<Outlet />`, `useNavigate`/`useParams`; un solo `BrowserRouter` en `main.jsx`) | 01/10/2026 |
| Personas | **Una tabla, dos módulos**: Clientes y Proveedores comparten tabla y formulario, con `tipo` + `nro_cuenta` independiente por módulo; misma persona puede estar en ambos | 01/10/2026 |
| IVA | **Tabla propia `alicuotas_iva`** (ampliable desde el módulo **Configuración**); condición obligatoria; alícuota obligatoria solo si RI | 01/10/2026 |
| Compras | **Centros de costos** + **tipos de gasto** (cada tipo, un centro; ampliables en Configuración); factura de proveedor con **IVA y total calculados en backend**; sin pagos ni cuenta corriente por ahora | 01/10/2026 |
| Informes | Bloque en el **Dashboard** con *desde/hasta* y Excel de proveedores, compras y centros de costos; pantalla propia **"Informe por centro"** (resumen por gasto + detalle, excluye anuladas) | 01/10/2026 |
| Informe de resultados | **Ingresos** (facturas + ND − NC, sin anuladas) − **gastos** por centro = **neto al pie**; tabla **Bienes** (Mercadería · Automóvil/Moto) como cuenta de balance que **no toca el neto** (a mejorar) | 01/10/2026 |
| Variantes y período | **Variantes de selección** estilo SAP (tabla `variantes`, privadas + compartir, sobrescriben con el mismo nombre) y selector **Mes y año** en las 5 pantallas con filtros. **Pendiente:** ejercicio contable real (inicio/fin y cierre) cuando se haga lo contable | 01/10/2026 |
| Rendimiento | Fuentes **locales** (sin Google Fonts), pantallas con **carga diferida** (`React.lazy`: JS inicial 391 → 284 KB) y arranque **sin bloquear** por `auth/me` (rol provisorio del JWT, validación en segundo plano); Dashboard con esqueletos (CLS 0). **Medir solo contra producción** — ver gotchas §6.7/§6.8. Detalle en `MEMORIA.md` §4.20 | 01/10/2026 |
| Estado de cuenta | El `<select>` de clientes pasó a **campo de búsqueda con desplegable**: filtro local por apellido/nombre o razón social (+ CUIT/DNI) donde **todas las palabras** deben coincidir; elegir carga la cuenta y escribir de nuevo limpia la selección | 01/10/2026 |
| Balance RT54 | Módulo propio (**/balance-rt54**): por cliente, con buscador `BuscadorCliente.jsx` compartido; carátula desde la ficha del cliente; fechas de inicio/cierre manuales; tablas ESP/ER/EEPN **cargadas a mano** (sin precargar facturas); **totales en backend** (Decimal); tabla de balances guardados por cliente; export = copiar plantilla oficial y llenar celdas **sin pisar fórmulas**. Tablas `bal_rt54_ejercicios` + `bal_rt54_valores` + `bal_rt54_notas`. **Tanda2:** pestaña **Notas** —44 notas de la hoja del modelo en7 secciones, texto precargado con la plantilla (encabezado del modelo aparte, no editable) y solo se emite lo guardado. Tanda 3 (tablitas de notas, Anexos, Flujo) = pendiente N°10 de `MEMORIA.md` §6. Búsqueda de clientes/proveedores ahora **multi-palabra** en backend (`_buscar`) | 01/10/2026 |

### 4.1 Reglas de negocio — NO olvidarlas (añadidas el 30/09/2026)

| # | Regla |
|---|---|
| 1 | 🔢 **Todo listado cierra con el importe total al final.** Estado de cuenta → `TOTAL DEBE` · `TOTAL HABER` · `SALDO FINAL`. Facturación del mes → **importe total**. El saldo es siempre `SUM(DEBE) − SUM(HABER)`. |
| 2 | ✏️ **Los clientes se pueden modificar siempre.** |
| 3 | 🔴 **Eliminar un cliente SOLO si NO tiene movimientos.** Si tiene facturas o recibos → **bloquear la baja** y avisar con un mensaje claro. |
| 4 | 🎨 **Estética del panel:** degradé **azul** + formas **geométricas** + look **futurista**. ✅ **HECHA el 30/09/2026 y aprobada por el cliente.** Paleta copiada de `diseno-premium`. Detalle en `MEMORIA.md` §4.12. |
| 5 | 💡 **Pestaña SUGERENCIAS** en la ficha del cliente: tabla propia `sugerencias` (fecha + descripción + estado), relación 1→N. Ver `MEMORIA.md` §4.13. |
| 6 | 🪪 **DNI y CUIT conviven.** Persona física → **DNI obligatorio** (CUIT opcional). Persona jurídica → **CUIT obligatorio** y **no acepta DNI**. Los dos campos **son únicos** y **se busca por cualquiera**. |
| 7 | 📝 **OBSERVACIONES = un solo texto** largo. Se sobreescribe al editar — **no** es un historial con fechas. |
| 8 | 📞 **Teléfono = código de área + número** (dos campos, **en las dos personas**), **domicilio = calle (30) + número (10)** y **código postal** que **autocompleta localidad y provincia**. 81 localidades de Córdoba cargadas (fuentes y fecha en `MEMORIA.md` §4.14). Si el CP no está cargado, **se escribe a mano**. |

> 📌 Detalle completo en `MEMORIA.md` §4.10 a §4.13.
> 📌 Los totales se calculan **en el backend con `SUM` (SQL)**, nunca en el navegador,
> para evitar diferencias de redondeo.

---

## 5. Cómo trabajar acá

### Al empezar una sesión
1. Leer `MEMORIA.md` §1 (estado) y §5 (pendientes).
2. Preguntar al cliente **qué fase sigue**.
3. **Nunca** ejecutar cambios sin consultar.

### Al terminar
Actualizar `MEMORIA.md`:
- Marcar lo hecho en §1 y §5.
- Agregar decisiones nuevas en §4.
- Registrar bugs en §6.

### Formato de las respuestas
- Cortas, con tablas.
- Un solo tema por mensaje.
- Cerrar con **checkpoint A/B/C/D**.

---

## 6 bis. ⛔ NUNCA BORRAR DATOS REALES DESDE UNA SUITE DE PRUEBA

> **Regla dura.** Los tests corren contra **la base de datos del estudio**, la
> misma que usa el contador. No hay base de pruebas separada. Por eso una suite
> **jamás** puede borrar nada que no sea suyo.

### El accidente que motivó esta regla (02/10/2026)

Siete suites tenían esto al principio y al final de la corrida:

```python
db.execute(text("DELETE FROM asiento_origen"))
db.execute(text("DELETE FROM asientos"))
db.execute(text("DELETE FROM comprobantes_internos"))
```

Eso no borra "lo de la prueba": **borra todos los asientos del contador**, y en
cada corrida. Cuando se corrió `correr_todas.py` quedaron **0 asientos y 0
comprobantes internos** en la base. Los recibos, las facturas y las compras
sobrevivieron; los asientos, no. No había respaldo: el único `.sql` que el
proyecto genera es el de clientes de prueba.

**Y los 1219 tests dieron verde.** Ese es el detalle que importa: el defecto era
invisible justamente porque las suites miden *diferencias contra una línea de
base*, y la línea de base se tomaba **después** de borrar. Un test que solo mira
sus propios números nunca se da cuenta de que se comió lo ajeno.

### Cómo se hace, entonces

| Regla | Por qué |
|---|---|
| **Nunca** `DELETE FROM <tabla>` sin `WHERE`. | `DELETE FROM asientos` a secas es el error. SIEMPRE con filtro. |
| Borrar solo lo que la suite **sabe que creó**, y por una marca: punto de venta reservado (`9900`, `9955`, …), concepto con "PRUEBA" adentro, o los ids que la suite guardó en una lista. | Es lo único que distingue "de prueba" de "del contador". |
| Para lo dudoso: **los asientos que nacen de un documento tienen `asiento_origen`** (factura, recibo o compra). Un asiento manual no lo tiene. Es el mejor discriminador que hay. | Permite borrar "asientos sueltos" sin pisar los del contador. |
| Usar el helper de `tests/borrar_prueba.py` en vez de escribir el `DELETE` a mano. | Está en un solo lugar y ya está corregido. |
| Si la suite crea una **tabla** (o una columna), que su limpieza la borre **por id**, nunca por tabla. | `DELETE FROM periodos` borraría los períodos del contador. |

### Antes de tocar cualquier suite: la pregunta

> *"¿Este `DELETE` puede tocar una fila que el contador cargó?"*
> Si la respuesta es "no sé", no lo ejecutes todavía.

### Las dos redes de seguridad (02/10/2026)

Ya no alcanza con la regla: hay que poder **darse cuenta**. Por eso
`correr_todas.py` ahora hace dos cosas **antes y después** de correr todo:

1. **Respaldo** — `python -X utf8 respaldar_todo.py` (en `tests/`) escribe los
   `INSERT` de contabilidad, asientos, comprobantes, facturas, recibos, compras,
   clientes, personas y plan de cuentas en un `.sql`. Sale automático al correr
   `correr_todas.py`. Es lo mismo que hace `limpiar_clientes_prueba.py`, pero
   de **todo**.
2. **Huella digital** — cuenta las filas de cada tabla real antes y después. Si
   alguna **bajó**, la corrida termina con `FALLO` y dice qué tabla y cuántas
   filas. Ahí se ve al culpable.

**Antes de correr los tests contra la base del estudio, siempre hay que haber un
`.sql` de respaldo del día.** Si no, no se corre.

### Lo que falta (pendiente, no hecho)

La solución de verdad es una **base de datos de pruebas separada**
(`GESTION_DB_NAME=gestion_contable_test`), donde los tests puedan borrar lo que
quieran. Es el punto N° del backlog. Mientras no exista, la regla de arriba es
la que sostiene todo.

---

## 6. Gotchas conocidas

1. **Vercel no tiene MySQL.** Si algún día se sube, la BD tiene que ir a otro
   servicio (TiDB Serverless, Aiven, etc.) y el backend pasa a *funciones
   serverless*. Para que eso sea posible sin reescribir nada:
   → **configuración por variables de entorno, nunca rutas duras.**
2. **`mysqlclient` no compila en Vercel** → si hace falta, usar `PyMySQL` (puro Python).
3. **`http.server` se cae** si se reinicia la PC. El Proyecto 1 usa
   `python -m http.server 8124` (workspace) y `8123` (`diseno-premium`).
   No es bug del código.
4. **Servidor de desarrollo de React** usa el puerto 5173 por defecto — ojo con choques.
5. **Las fechas de ejemplo** del cliente están en 2026 (hoy 30/09/2026).
6. **No cambiar el stack** sin consultar. El cliente lo eligió a propósito.
7. **Caché de Vite en desarrollo — el cliente NUNCA la ve.** El dev server
   (`npm run dev`,5173) transforma los archivos al vuelo y a veces cacheó
   versiones viejas mientras se editaba (bug de desarrollo, vivido el01/10/2026
   con `App.jsx` y `Compras.jsx`). **Producción es inmune**: `npm run build`
   genera `dist/` desde cero, minificado, con **hash en el nombre**
   (`index-BwjXbQ_9.js`) — el navegador solo cachea ese bytes exacto.
   ✅ **Checklist de despliegue:** (1) siempre `npm run build` fresco antes de
   subir `dist`, nunca subir un `dist` viejo; (2) servir `index.html` con
   `no-cache` y `/assets/*` con `immutable` (Vercel lo hace por defecto);
   (3) backend: cambio de código = reinicio/redeploy (sin `--reload` en prod).
8. **Medir el rendimiento SOLO contra producción.** Lighthouse sobre el dev
   server da puntajes falsos bajos (22–25; se ve en la consola
   `react-dom_client.js`). Medir con `npm run build` + `npm run preview`
   (localhost:4173) — tras optimizar (01/10/2026): **login 99 / dashboard 99**
   con throttling simulado (antes 93/98). Con el panel de DevTools en mobile
   (throttle real): **95** (antes 35) — medido por el cliente. Ojo con el
   preset **Desktop**: da ~100 y no significa nada; usar siempre **mobile**.
9. **La plantilla del Excel RT54 vive en `backend/plantillas/`**
   (`MODELO-EECC-Entes-Con-Fines-de-Lucro-RT54-publicacion_new.xlsx`). El
   export la **copia y llena celdas** — si se mueve o renombra, "Emitir
   Excel" revienta con **Rechazo500**. El original del cliente está en
   `C:\estudio contable\files\` (no tocar; la copia de trabajo es la del
   backend). Las fórmulas del modelo se dejan **intactas** a propósito
   (el Excel calcula al abrir).

---

## 7. Backlog

Ver `MEMORIA.md` §5 — es la **fuente única** de pendientes.

> 💬 **Botón WhatsApp** en la ficha del cliente: **no abre** — queda para después (registrado el 01/10/2026).
