# AGENTE.md — Proyecto 2: Sistema de gestión estudio contable

Guía de trabajo para cualquier agente (humano o IA) que toque este proyecto.

> **Última actualización:** 30/09/2026

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
| 8 | 📞 **Teléfono = código de área + número** (dos campos, **en las dos personas**) y **código postal** que **autocompleta localidad y provincia**. 81 localidades de Córdoba cargadas (fuentes y fecha en `MEMORIA.md` §4.14). Si el CP no está cargado, **se escribe a mano**. |

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

---

## 7. Backlog

Ver `MEMORIA.md` §5 — es la **fuente única** de pendientes.
