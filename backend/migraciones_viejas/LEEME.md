MIGRACIONES VIEJAS — no se corren más
========================================

QUÉ HAY ACÁ

Ocho scripts que creaban o modificaban el ESQUEMA de la base (tablas y
columnas). El esquema ya no lo hacen estos scripts: lo hace Alembic, con
`alembic upgrade head`, que arma las 43 tablas a partir de los modelos.

POR QUÉ NO ESTÁN EN `backend/`

Cuando se adoptó Alembic (03/10/2026), estos scripts dejaron de tener trabajo.
`backend/` quedó con 49 archivos Python sueltos y solo 16 tenían función: los que
cargan DATOS (el plan de cuentas, el ejercicio, los períodos), que Alembic no
toca porque los datos iniciales cambian según el estudio.

Estos ocho son de los que NO hacen falta. Se movieron acá, no se borraron: si
algún día hay que reconstruir una base muy vieja, o se descubre que alguno
tenía algo que no se replicó, están a mano.

CÓMO SABER CUÁLES CORRER

La lista de los que sí corren está en `tests/armar_base_prueba.py`, en
`ORDEN_DATOS`. Anything que no esté ahí, no corre.

Archivo                                | Qué hacía
---------------------------------------|------------------------------------------
migrar_balance_rt54.py                  | Creaba las 4 tablas del balance RT54
migrar_balance_ejercicio.py             | anio_inicio / anio_fin / fecha de cierre
migrar_domicilio.py                     | calle + numero_calle en clientes
migrar_gasto_centro.py                  | El tipo de gasto pertenece a un centro
migrar_pagos_recibo.py                  | La tabla recibo_pagos (varias formas de pago)
migrar_vencimientos.py                  | La tabla vencimientos_impositivos
migrar_indices_moneda.py                | config_indices_moneda (solo esquema)
migrar_personas.py                      | Partió clientes en personas + clientes + proveedores

DOS DE ESTOS ESTÁN ADEMÁS ROTOS

`migrar_personas.py` y `migrar_indices_moneda.py` están en el histórico pero NO
se deben correr ni para reconstruir una base:

- `migrar_personas.py`: su primera línea es `ALTER TABLE clientes RENAME TO
  clientes_vieja`. Renombra la tabla buena y después falla al recrearla, dejando
  la base sin `clientes` y con toda la API rota.

- `migrar_indices_moneda.py`: agrega `fecha_cierre_ejercicio` a la tabla
  `clientes`, pero esa columna está en el modelo de `personas`. Deja una columna
  de más que en la base del estudio no existe. (La tabla sí la crea, pero eso ya
  lo hace Alembic.)

El motivo por el que quedaron acá está anotado en `tests/armar_base_prueba.py`,
donde se los menciona al explicar por qué no están en `ORDEN_DATOS`.

LO QUE NO SE HIZO

No se borró nada. No se cambió el nombre de los archivos. Si aparece una versión
más vieja de esta carpeta donde faltaba algo, los archivos originales siguen en
el historial de Git.

SOBRE LAS RUTAS RELATIVAS

Cinco de los ocho (balance_ejercicio, indices_moneda, pagos_recibo, personas y
vencimientos) buscan `backend/` con `dirname(__file__)`. Movidos a una subcarpeta,
esa ruta apunta a `migraciones_viejas/` en vez de `backend/` y el
`import app.database` falla.

No se corrigieron a propósito: son código muerto, y arreglar rutas de algo que no
se corre es trabajo que después hay que mantener. Si algún día hay que resucitar
alguno, el arreglo es una línea: cambiar `dirname(abspath(__file__))` por
`dirname(dirname(abspath(__file__)))`, o correrlo desde `backend/` con la ruta
completa.
