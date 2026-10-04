SCRIPTS DE UN SOLO USO — revisar antes de correr
================================================

QUÉ HAY ACÁ

Siete scripts del 01/10/2026 (hace tres días), cuando se estaba armando el
sistema. Todos están acá porque modifican la base de datos, y en la raíz del
proyecto queda más a mano la tentación de correrlos sin leer.

Los siete tienen un docstring arriba que dice qué tocan y contra qué base.
**Leelo antes de correr nada.**

  borrar_cliente7.py           BORRA el cliente 7 (Juan) por API
  limpiar_balances_prueba.py   BORRA los balances que empiezan con "prueba-"
  ver_y_limpiar_proveedores.py BORRA los proveedores con "PRUEBA" en el nombre
  limpiar_prueba.py            PONE en NULL el email de las personas "PROVEEDOR"
  limpiar_meses_prueba.py      VACÍA los vencimientos de los años 1999, 2050 y 2099
  add_presenta_eecc.py         Agregaba una columna (ya no hace falta: la tiene el modelo)
  rellenar_balance.py          Rellenaba los años de los balances que estaban en NULL

POR QUÉ NO ESTÁN EN `backend/`

Los que arman el esquema y los datos van en `backend/` (ver `seed.py` y los
`migrar_*.py`). Los que se ejecutan a mano, una vez, para un problema puntual,
no van juntos con el arranque del sistema: están acá, con la advertencia a la vista.

CONTRA QUÉ BASE APUNTAN

- Los que van por HTTP (`borrar_cliente7`, `limpiar_balances_prueba`,
  `ver_y_limpiar_proveedores`, `limpiar_meses_prueba`): al puerto **8010**, que
  es el programa real y su base `gestion_contable`. Para que sean inofensivos hay
  que cambiar el puerto a **8011** (la base de pruebas).

- Los que van por SQL (`limpiar_prueba`, `add_presenta_eecc`, `rellenar_balance`):
  leen `DB_NAME` del entorno. Sin esa variable usan la base real. Con
  `$env:DB_NAME = "gestion_contable_test"` van a la de pruebas.

LO QUE PROTECJE HOY, QUE NO EXISTÍA EN ESOS MOMENTOS

Las 40 suites de `tests/` **no borran datos reales**. `tests/correr_todas.py`
toma una "huella digital" de la base antes de correr y compara al terminar: si
desapareció una fila que el contador cargó, la corrida falla y dice cuál. Esa
protección se agregó el 02/10/2026 (ver `AGENTE.md` §6 bis), un día después de
que estos scripts se escribieran. Estos seis no tienen nada de eso: son de la
época anterior.

BORRADOS DE VERDAD

Ninguno se usa en el proyecto. Todo lo que hacen ya está hecho. Se pueden borrar
sin consecuencia: Git conserva el historial.
