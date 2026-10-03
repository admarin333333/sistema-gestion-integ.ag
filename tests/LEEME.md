# Pruebas del sistema

Son scripts sueltos que se corren **contra el backend ya levantado**. No usan
pytest: cada archivo es independiente y se ejecuta con Python.

## Cómo se corren

1. Con el backend levantado en el puerto 8010 (desde `backend/`):
   ```
   python -m uvicorn app.main:app --host=127.0.0.1 --port=8010
   ```
2. En otra terminal, desde esta carpeta:
   ```
   python correr_todas.py
   ```

O una sola:
```
python -X utf8 test_vencimientos.py
```

## Cómo se leen los resultados

Cada suite imprime línea por línea y al final un resumen:

```
  OK  guarda grilla del mes
  OK  lee los vencimientos
FALLA reemplaza el mes sin duplicar -> 4

28 OK / 0 fallos
```

Si hay algún fallo, el script termina con código de salida 1 (por eso sirve
para encadenarlo).

## Qué hay que tener en cuenta

- **Tocan la base de verdad.** Los tests crean clientes, facturas y recibos de
  prueba y los borran al final. Si una corrida se corta a mitad, pueden quedar
  restos; casi todas las suites se limpian solas al arrancar.
- **No usar contra la base del estudio.** Apuntan siempre a la base de
  desarrollo.
- **Los importan de `backend` con ruta relativa**: se calculan desde la
  ubicación del archivo, así que el proyecto se puede mover de carpeta.

## Las 19 suites

| Suite | Qué prueba |
|---|---|
| `test_anticipos.py` | Anticipos y sus aplicaciones a facturas |
| `test_asientos_automaticos.py` | El asiento que sale de una factura y de un recibo |
| `test_caratula_api.py` | Los campos nuevos de la carátula RT54 |
| `test_clave_fiscal.py` | Clave fiscal de ARCA: fechas e historial |
| `test_cp_telefono.py` | Código postal → localidad, y teléfono |
| `test_cuadros_api.py` | Cuadros de notas del balance |
| `test_facturas.py` | Facturas: alta, anular, exportar, PDF |
| `test_fase2a.py` | Separación de clientes y proveedores |
| `test_informe_claves.py` | Informe de CUIT y clave fiscal |
| `test_informes.py` | Informes y exportación a Excel |
| `test_intervalo_balance.py` | Intervalos del balance RT54 |
| `test_mail.py` | Envío de mail con el comprobante adjunto |
| `test_moneda_api.py` | Moneda homogénea e índices FACPCE |
| `test_motor_contable.py` | Comprobantes, asientos, partida doble y saldos |
| `test_personas_api.py` | Personas, CUIT, DNI y validaciones |
| `test_plan_cuentas.py` | El plan de cuentas: árbol, edición y reglas |
| `test_recalculo_api.py` | Recálculo de los cuadros |
| `test_recibos.py` | Recibos y sus aplicaciones a facturas |
| `test_vencimientos.py` | Vencimientos impositivos y su calendario |