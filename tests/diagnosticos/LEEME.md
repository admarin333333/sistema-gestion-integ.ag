DIAGNÓSTICOS — mirar, no arreglar
================================

QUÉ HAY ACÁ

Veinticinco scripts del 01/10/2026. Son consultas de una vez, escritas para
mirar algo concreto mientras se/armaba el sistema: "mostrame los clientes", "cambió
la estructura de la tabla?", "por qué el login da 422?", "qué balances hay".

Se movieron acá desde la raíz del proyecto el 04/10/2026. No se borró nada.

SON DE LEER, NO DE CORRER EN SERIO

Casi todos solo hacen `SELECT`. Son inofensivos.

Ojo con dos:

  ver_y_limpiar_proveedores.py  BORRA. Está en `scripts/`, no acá, justamente
                                 por eso: si buscabas algo que limpia, no lo
                                 encontrás en la carpeta de diagnóstico.
  auditar_tablas.py             Muestra la estructura de las tablas. Inofensivo,
                                 pero sirve: si algo no anda, empezá por acá.

LOS `test_debug*.py`

Diez archivos que van por HTTP contra la API con el puerto fijo 8010. Son de
cazar un error puntual, no tests de verdad: no los recoge ningún runner.

  test_check.py   test_ficha.py    test_route.py    test_search.py
  test_debug.py   test_frontend.py test_route2.py
  test_debug2.py  test_debug3.py   test_debug4.py

Cinco tienen una suite que los reemplaza, en la carpeta de al lado:

  test_check.py    → test_plan_cuentas.py
  test_ficha.py    → test_cliente_ficha.py
  test_route.py    → test_facturas.py
  test_route2.py   → test_facturas.py
  test_search.py   → test_clientes_api.py

Los otros cinco (`test_debug*`) no tienen equivalente: eran para un error
concreto que ya se resolvió.

SI QUERÉS QUE ESTOS PRUEBAS CORRAN DE VERDAD

Un runner que recorra esta carpeta y ejecute los que tienen `check`/`test` en el
nombre, saltando los `debug`. Es un script corto. Pero **no se agregó**: la idea
es no crear más cosas, y estos archivos ya cumpieron su función. Si en algún
momento hacen falta pruebas de API que no se están corriendo, se escribe una sola
suite en `tests/` y listo.

LOS DEMÁS

  auditar_tablas.py         Estructura de las tablas
  check_cols.py             Columnas de una tabla
  check_excel.py            Descarga un Excel de la API
  check_totales.py          Totales de un balance
  diagnosticar.py           Un ejercicio concreto
  diagnostico_huerfanos.py  Personas sin cliente ni proveedor
  list_clientes.py          Lista clientes
  list_proveedores.py       Prueba la búsqueda de proveedores
  ver_balance.py            Un balance
  ver_balance_datos.py      Datos de un balance
  ver_cuits.py              CUITs de la base
  ver_estructura.py         Estructura de la base
  ver_final.py              Verificación final
  ver_huerfanas.py          Filas huérfanas
  verify_login.py           Que el login funcione

NADA DE ESTO LO USA EL SISTEMA

Ni `backend/`, ni `frontend/`, ni `tests/`, ni los `.bat`. Son de ejecución
manual. Se pueden borrar sin consecuencia: Git conserva el historial.
