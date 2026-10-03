"""Agrega la sección 4.31 al final del bloque 4.30 de MEMORIA.md.

Se usa un script (y no el editor) porque el archivo tiene acentos y
PowerShell los mangla al escribir.
"""

import io
import os

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MEMORIA.md")

SECCION = """
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
"""


def main():
    ruta = os.path.normpath(RUTA)
    with io.open(ruta, "r", encoding="utf-8") as f:
        texto = f.read()

    if "### 4.31" in texto:
        print("La sección 4.31 ya está: no se toca nada")
        return

    # Se inserta antes de "## 7. Bugs / incidencias".
    marca = "\n## 7. Bugs / incidencias"
    if marca not in texto:
        raise SystemExit("No encontré el lugar para insertar 4.31")

    texto = texto.replace(marca, SECCION + marca, 1)

    with io.open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)

    print("MEMORIA.md: agregada la sección 4.31")


if __name__ == "__main__":
    main()