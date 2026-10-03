# Carga masiva de índices de moneda homogénea desde el Excel de FACPCE:
#   python cargar_indices_fapce.py
# Lee MES + IPC NACIONAL EMPALME IPIM y da de alta un registro por mes
# (si el mes ya existe, lo corrige). Los meses nuevos se cargan a mano
# desde Configuración.
import sys
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")

import openpyxl
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.indice import IndiceMoneda

ARCHIVO = Path(r"C:\estudio contable\files\Indice-FACPCE-Res.-JG-539-18-2026-08-1.xlsx")

db: Session = SessionLocal()
nuevos = 0
corregidos = 0
omitidos = 0

ws = openpyxl.load_workbook(ARCHIVO, data_only=True).active
for fila in ws.iter_rows(min_row=3):
    fecha_celda, valor_celda = fila[0].value, fila[1].value
    if not hasattr(fecha_celda, "year"):  # encabezados y notas varias
        continue
    if not isinstance(valor_celda, (int, float)):  # ej.: "*" = sin publicar
        omitidos += 1
        continue
    mes = date(fecha_celda.year, fecha_celda.month, 1)
    existente = (
        db.query(IndiceMoneda).filter(IndiceMoneda.fecha == mes).first()
    )
    if existente:
        # Tolerancia: la diferencia puede ser de redondeo (decimales) y no
        # significa nada para el índice.
        if abs(float(existente.indice) - float(valor_celda)) > 1e-9:
            existente.indice = valor_celda
            corregidos += 1
    else:
        db.add(IndiceMoneda(fecha=mes, indice=valor_celda))
        nuevos += 1

db.commit()
total = db.query(IndiceMoneda).count()
print(f"Cargados: {nuevos} nuevos, {corregidos} corregidos, {omitidos} sin valor")
print(f"Total de meses en la tabla: {total}")
