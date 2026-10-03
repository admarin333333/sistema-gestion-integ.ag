"""Balance RT54 — estados contables anuales de entes con fines de lucro.

Los rubros son los del modelo oficial
MODELO-EECC-Entes-Con-Fines-de-Lucro-RT54 (CPCE Córdoba). Los importes
se cargan a mano por cliente y ejercicio; TODOS los totales se calculan
acá, en el backend — el navegador solo muestra.

El export copia la plantilla (backend/plantillas/) y escribe los valores
en las mismas celdas del modelo, sin pisar ninguna fórmula.
"""

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.balance_rt54 import (
    BalanceEjercicio,
    BalanceNota,
    BalanceNotaCelda,
    BalanceValor,
)
from app.models.cliente import Cliente
from app.schemas.balance_rt54 import BalanceGuardar, CeldaNotaIn, EjercicioCrear
from app.services import indice_service

PLANTILLA = (
    Path(__file__).resolve().parents[2]
    / "plantillas"
    / "MODELO-EECC-Entes-Con-Fines-de-Lucro-RT54-publicacion_new.xlsx"
)

CERO = Decimal("0.00")
_DOS = Decimal("0.01")
_CUATRO = Decimal("0.0001")  # índices y coeficiente:4 decimales, como el modelo

# ---------------------------------------------------------------------------
# Estructura de los estados (tal cual el modelo)
# ---------------------------------------------------------------------------

# ESP: (clave del bloque, título, ((clave, etiqueta, nota), ...))
_ESP_ACTIVO = (
    (
        "activo_corriente",
        "Activo corriente",
        (
            ("ac_caja", "Caja y Bancos", "Nota 2.1"),
            ("ac_inv_fin", "Inversiones Financieras", "Nota 2.2"),
            ("ac_cxc_mon", "Cuentas por cobrar a clientes en moneda", "Nota 2.3"),
            ("ac_cxc_esp", "Cuentas por cobrar a clientes en especie", "Nota 2.4"),
            ("ac_cred_fis", "Créditos impositivos", "Nota 2.5"),
            ("ac_cred_rel", "Créditos con partes relacionadas", "Nota 2.6"),
            ("ac_otras_cxc_mon", "Otras cuentas por cobrar en moneda", "Nota 2.7"),
            ("ac_otras_cxc_esp", "Otras cuentas por cobrar en especie", "Nota 2.8"),
            ("ac_bienes_cambio", "Bienes de cambio", "Nota 2.9"),
            ("ac_otras_inv", "Otras Inversiones", "Nota 2.12"),
            ("ac_otros", "Otros activos", "Nota 2.14"),
        ),
    ),
    (
        "activo_no_corriente",
        "Activo no corriente",
        (
            ("anc_inv_fin", "Inversiones Financieras", "Nota 2.2"),
            ("anc_cxc_mon", "Cuentas por cobrar a clientes en moneda", "Nota 2.3"),
            ("anc_cxc_esp", "Cuentas por cobrar a clientes en especie", "Nota 2.4"),
            ("anc_cred_fis", "Créditos impositivos", "Nota 2.5"),
            ("anc_cred_rel", "Créditos con partes relacionadas en Moneda", "Nota 2.6"),
            ("anc_otras_cxc_mon", "Otras cuentas por cobrar en moneda", "Nota 2.7"),
            ("anc_otras_cxc_esp", "Otras cuentas por cobrar en especie", "Nota 2.8"),
            ("anc_bienes_cambio", "Bienes de cambio", "Nota 2.9"),
            ("anc_bienes_uso", "Bienes de uso", "Nota 2.10 (Anexo III)"),
            ("anc_prop_inv", "Propiedades de inversión", "Nota 2.11 (Anexo III)"),
            ("anc_otras_inv", "Otras inversiones", "Nota 2.12"),
            ("anc_intangibles", "Activos intangibles", "Nota 2.13 (Anexo V)"),
            ("anc_otros", "Otros activos", "Nota 2.14"),
        ),
    ),
)

_ESP_PASIVO = (
    (
        "pasivo_corriente",
        "Pasivo corriente",
        (
            ("pc_deudas_prov", "Deudas con Proveedores de Bienes y Servicios", "Nota 2.15"),
            ("pc_prestamos", "Préstamos y Otros Pasivos Financieros", "Nota 2.16"),
            ("pc_deudas_fis", "Deudas fiscales", "Nota 2.17"),
            ("pc_deudas_lab", "Deudas Laborales y Previsionales", "Nota 2.18"),
            ("pc_deudas_esp", "Deudas en Especie", "Nota 2.19"),
            ("pc_deudas_rel", "Deudas con Partes Relacionadas", "Nota 2.20"),
            ("pc_otras_deudas", "Otras deudas", "Nota 2.21"),
            ("pc_subsidios", "Subsidios y otras Ayudas Gubernamentales", "Nota 2.22"),
            ("pc_previsiones", "Previsiones", "Nota 2.23 (Anexo VI)"),
        ),
    ),
    (
        "pasivo_no_corriente",
        "Pasivo no corriente",
        (
            ("pnc_deudas_prov", "Deudas con Proveedores de Bienes y Servicios", "Nota 2.15"),
            ("pnc_prestamos", "Préstamos y Otros Pasivos Financieros", "Nota 2.16"),
            ("pnc_deudas_fis", "Deudas fiscales", "Nota 2.17"),
            ("pnc_deudas_lab", "Deudas Laborales y Previsionales", "Nota 2.18"),
            ("pnc_deudas_esp", "Deudas en Especie", "Nota 2.19"),
            ("pnc_deudas_rel", "Deudas con Partes Relacionadas en Moneda", "Nota 2.20"),
            ("pnc_otras_deudas", "Otras deudas", "Nota 2.21"),
            ("pnc_subsidios", "Subsidios y otras Ayudas Gubernamentales", "Nota 2.22"),
            ("pnc_imp_diferido", "Pasivo Neto por Impuesto Diferido", "Nota 7"),
            ("pnc_previsiones", "Previsiones", "Nota 2.23 (Anexo VI)"),
        ),
    ),
)

# ER: (clave, etiqueta, nota, tipo) — tipo "dato" se carga a mano; el resto
# se calcula con las mismas fórmulas del modelo (E9=E7-E8, etc.).
_ER = (
    ("ingresos", "Ingresos netos por la Venta de bienes y prestación de servicios", "Nota 3.1", "dato"),
    ("costo", "Costo de bienes vendidos y servicios prestados", "Nota 3.3 (Anexo VII)", "dato"),
    ("bruta", "Ganancia (Pérdida) bruta", None, "bruta"),
    ("gastos_adm", "Gastos de administración", "Anexo VIII", "dato"),
    ("gastos_com", "Gastos de comercialización", "Anexo VIII", "dato"),
    ("otros_gastos", "Otros gastos operativos", "Anexo VIII", "dato"),
    ("cambios_vr", "Cambios en el valor razonable de propiedades de inversión", "Anexo IV", "dato"),
    ("desval", "Pérdidas por desvalorización (Reversión Pérdidas por desvalorización)", "Nota 3.6", "dato"),
    ("otras_gan", "Otros Resultados Financieros y por Tenencia (incluyendo el RECPAM)", "Nota 3.5", "dato"),
    ("otros_ing", "Otros Ingresos", "Nota 3.4", "dato"),
    ("otros_egr", "Otros Egresos", "Nota 3.4", "dato"),
    ("antes_imp", "Ganancia (Pérdida) antes del impuesto a las ganancias de operaciones que continúan", None, "antes_imp"),
    ("impuesto", "Impuesto a las ganancias", "Nota 7", "dato"),
    ("continuan", "Ganancia (Pérdida) de las operaciones que continúan", None, "continuan"),
    ("discontinuadas", "Resultados por actividades u operaciones discontinuadas (o en discontinuación)", "Nota 3.7", "dato"),
    ("resultado", "GANANCIA (PÉRDIDA) DEL EJERCICIO", None, "resultado"),
)

_ER_OTROS = (
    "gastos_adm", "gastos_com", "otros_gastos", "cambios_vr",
    "desval", "otras_gan", "otros_ing", "otros_egr",
)

# EEPN: columnas (clave, etiqueta, es_cálculo, grupo de encabezado)
_EEPN_COLS = (
    ("capital", "Capital Social", False, "aportes"),
    ("ajustes", "Ajustes del Capital", False, "aportes"),
    ("aportes", "Aportes Irrevocables", False, "aportes"),
    ("primas", "Primas de Emisión", False, "aportes"),
    ("tot_aportes", "Total", True, "aportes"),
    ("res_legal", "Reserva Legal", False, "resultados"),
    ("otras_res", "Otras Reservas", False, "resultados"),
    ("tot_res", "Total", True, "resultados"),
    ("rna", "Resultados No Asignados", False, "resultados"),
    ("rd", "Resultados Diferidos", False, "resultados"),
    ("tot_resul", "Total", True, "resultados"),
    ("total", "TOTAL", True, "totales"),
)

_EEPN_FILAS = (
    ("inicio", "Saldos al inicio del ejercicio", "dato"),
    ("modif", "Modificación de saldos al inicio del ejercicio", "dato"),
    ("inicio_modif", "Saldos al inicio del ejercicio modificados", "calc"),
    ("suscripcion", "Suscripción de capital", "dato"),
    ("distribucion", "Distribución de resultados no asignados:", "titulo"),
    ("dist_res_legal", "> Reserva legal / Otras Reservas", "dato"),
    ("dist_div_efectivo", "> Dividendos en efectivo (o especie)", "dato"),
    ("dist_div_acciones", "> Dividendos en acciones", "dato"),
    ("ganancia", "Ganancia (Pérdida) del ejercicio", "dato"),
    ("otro", "Otras modificaciones", "dato"),
    ("cierre", "Saldos al cierre del ejercicio", "calc"),
)

_EEPN_COLS_DATO = tuple(c for c, _, calc, _ in _EEPN_COLS if not calc)
_EEPN_MOVIMIENTOS = (
    "suscripcion", "dist_res_legal", "dist_div_efectivo",
    "dist_div_acciones", "ganancia", "otro",
)

# Claves que se pueden guardar (para validar lo que manda la pantalla).
_CLAVES = (
    {
        ("esp", clave)
        for bloques in (_ESP_ACTIVO, _ESP_PASIVO)
        for _, _, rubros in bloques
        for clave, _, _ in rubros
    }
    | {("er", clave) for clave, _, _, tipo in _ER if tipo == "dato"}
    | {
        ("eepn", f"{fila}:{col}")
        for fila, _, tipo in _EEPN_FILAS
        if tipo == "dato"
        for col in _EEPN_COLS_DATO
    }
)

# ---------------------------------------------------------------------------
# Notas a los estados contables (hoja "Notas" del modelo)
# ---------------------------------------------------------------------------
#
# Cada nota apunta a la celda de texto de la plantilla. Si la celda empieza
# con el número de la nota ("2.1. Caja y bancos"), esa primera línea es el
# encabezado del modelo: no se muestra para editar y el export la vuelve a
# poner arriba del texto del usuario.

_NOTAS_SECCIONES = (
    ("1", "1. Notas generales", (
        ("1.1", "Bases de preparación de los estados contables", "B7"),
        ("1.2", "Clasificación de la entidad", "B8"),
        ("1.3", "Unidad de medida", "B9"),
        ("1.4", "Uso de estimaciones en la preparación de los estados contables", "B11"),
        ("1.5", "Circunstancias que afectan la comparabilidad", "B12"),
        ("1.6", "Modificación a la información de ejercicios anteriores", "B13"),
        ("1.7", "Empresa en marcha", "B15"),
    )),
    ("2", "2. Notas al Estado de Situación Patrimonial", (
        ("2.1", "Caja y bancos", "B18"),
        ("2.2", "Inversiones financieras", "B26"),
        ("2.3", "Cuentas por cobrar a clientes en moneda", "B41"),
        ("2.4", "Cuentas por cobrar a clientes en especie", "B54"),
        ("2.5", "Créditos impositivos", "B63"),
        ("2.6", "Créditos con partes relacionadas", "B75"),
        ("2.7", "Otras cuentas por cobrar en moneda", "B77"),
        ("2.8", "Otras cuentas por cobrar en especie", "B87"),
        ("2.9", "Bienes de cambio", "B98"),
        ("2.10", "Bienes de uso", "B112"),
        ("2.11", "Propiedades de inversión", "B114"),
        ("2.12", "Otras inversiones", "B116"),
        ("2.13", "Activos intangibles", "B127"),
        ("2.14", "Otros activos", "B129"),
        ("2.15", "Deudas con proveedores de bienes y servicios", "B140"),
        ("2.16", "Préstamos y otros pasivos financieros", "B148"),
        ("2.17", "Deudas fiscales", "B158"),
        ("2.18", "Deudas laborales y previsionales", "B170"),
        ("2.19", "Deudas en especie", "B178"),
        ("2.20", "Deudas con partes relacionadas", "B185"),
        ("2.21", "Otras deudas", "B193"),
        ("2.22", "Subsidios y otras ayudas gubernamentales", "B200"),
        ("2.23", "Previsiones y otros pasivos contingentes", "B206"),
        ("2.24", "Arrendamientos", "B211"),
        ("2.25", "Bienes de disponibilidad restringida", "B246"),
        ("2.26", "Gravámenes sobre Activos", "B250"),
    )),
    ("3", "3. Notas al Estado de Resultados", (
        ("3.1", "Ingresos netos por ventas de bienes y prestación de servicios", "B256"),
        ("3.2", "Subsidios y otras ayudas gubernamentales, reconocidos en resultados", "B264"),
        ("3.3", "Costo de los bienes vendidos y servicios prestados", "B266"),
        ("3.4", "Otros ingresos y egresos", "B274"),
        ("3.5", "Otros resultados financieros y por tenencia (incluyendo el RECPAM)", "B281"),
        ("3.6", "Pérdidas por desvalorización y reversión de pérdidas por desvalorización", "B302"),
        ("3.7", "Información sobre operaciones discontinuadas (o en discontinuación)", "B314"),
    )),
    ("4", "4. Notas al Estado de Evolución del Patrimonio Neto", (
        ("4", "Notas al EEPN", "B326"),
    )),
    ("5", "5. Notas al Estado de Flujos de Efectivo", (
        ("5", "Notas al flujo de efectivo", "B329"),
    )),
    ("6", "6. Información sobre partes relacionadas", (
        ("6", "Partes relacionadas", "B351"),
    )),
    ("7", "7. Información sobre el impuesto a las ganancias", (
        ("7", "Impuesto a las ganancias", "B358"),
    )),
)

_NOTAS_CELDAS = {
    clave: celda
    for _, _, notas in _NOTAS_SECCIONES
    for clave, _, celda in notas
}
_NOTAS_CLAVES = set(_NOTAS_CELDAS)

# ---------------------------------------------------------------------------
# Cuadros de composición de las notas (cargados a mano, importes)
#
# Cada cuadro se describe por sus columnas y sus renglones con la fila del
# Excel de la plantilla. Los rótulos (columna B) no se escriben acá: se leen
# de la plantilla para no desincronizarse del modelo. Tipos de renglón:
#   dato       -> importe a mano
#   prevision  -> importe a mano (entra en el Total, no en el Subtotal)
#   subtotal   -> sumatoria de los datos, la calcula el backend
#   total      -> la calcula el backend (Subtotal + previsiones, o la suma
#                 de los datos si no hay Subtotal)
# En la plantilla esos renglones están en blanco: nunca se copian fórmulas.

_COLS_2 = (
    ("C", None, "Actual"),
    ("D", None, "Comparativo"),
)
_COLS_4 = (
    ("C", "Corriente", "Actual"),
    ("D", "Corriente", "Comparativo"),
    ("E", "No corriente", "Actual"),
    ("F", "No corriente", "Comparativo"),
)

_NOTAS_CUADROS: dict[str, tuple] = {
    "2.1": (_COLS_2, (
        (20, "dato"), (21, "dato"), (22, "dato"), (23, "dato"),
        (24, "total"),
    )),
    "2.2": (_COLS_4, (
        (29, "dato"), (30, "dato"), (31, "dato"), (32, "dato"),
        (33, "dato"), (34, "dato"), (35, "dato"), (36, "dato"),
        (37, "subtotal"), (38, "prevision"), (39, "total"),
    )),
    "2.3": (_COLS_4, (
        (44, "dato"), (45, "dato"), (46, "dato"), (47, "dato"), (48, "dato"),
        (49, "subtotal"), (50, "prevision"), (51, "total"),
    )),
    "2.4": (_COLS_4, (
        (57, "dato"), (58, "dato"),
        (59, "subtotal"), (60, "prevision"), (61, "total"),
    )),
    "2.5": (_COLS_4, (
        (66, "dato"), (67, "dato"), (68, "dato"), (69, "dato"),
        (70, "dato"), (71, "dato"),
        (72, "prevision"), (73, "total"),
    )),
    "2.7": (_COLS_4, (
        (80, "dato"), (81, "dato"), (82, "dato"),
        (83, "subtotal"), (84, "prevision"), (85, "total"),
    )),
    "2.8": (_COLS_4, (
        (90, "dato"), (91, "dato"), (92, "dato"), (93, "dato"),
        (94, "subtotal"), (95, "prevision"), (96, "total"),
    )),
    "2.9": (_COLS_4, (
        (101, "dato"), (102, "dato"), (103, "dato"), (104, "dato"),
        (105, "dato"), (106, "dato"), (107, "dato"),
        (108, "subtotal"), (109, "prevision"), (110, "total"),
    )),
    "2.12": (_COLS_4, (
        (120, "dato"), (121, "dato"), (122, "dato"),
        (123, "subtotal"), (124, "prevision"), (125, "total"),
    )),
    "2.14": (_COLS_4, (
        (132, "dato"), (133, "dato"), (134, "dato"), (135, "dato"),
        (136, "subtotal"), (137, "prevision"), (138, "total"),
    )),
    "2.15": (_COLS_4, (
        (143, "dato"), (144, "dato"), (145, "total"),
    )),
    "2.16": (_COLS_4, (
        (151, "dato"), (152, "dato"), (153, "dato"), (154, "dato"),
        (155, "total"),
    )),
    "2.17": (_COLS_4, (
        (161, "dato"), (162, "dato"), (163, "dato"), (164, "dato"),
        (165, "dato"), (166, "dato"), (167, "total"),
    )),
    "2.18": (_COLS_4, (
        (173, "dato"), (174, "dato"), (175, "dato"), (176, "total"),
    )),
    "2.19": (_COLS_4, (
        (181, "dato"), (182, "dato"), (183, "total"),
    )),
    "2.21": (_COLS_4, (
        (196, "dato"), (197, "dato"), (198, "total"),
    )),
    "3.1": (_COLS_2, (
        (258, "dato"), (259, "dato"), (260, "dato"), (261, "dato"),
        (262, "total"),
    )),
    "3.3": (_COLS_2, (
        (268, "dato"), (269, "dato"), (270, "dato"), (271, "dato"),
        (272, "total"),
    )),
    "3.4": (_COLS_2, (
        (276, "dato"), (277, "total"), (278, "dato"), (279, "total"),
    )),
}

# Rótulos de los renglones (columna B de la plantilla), leídos una sola vez.
_rotulos_cache: dict[int, str] | None = None


def _rotulos_plantilla() -> dict[int, str]:
    global _rotulos_cache
    if _rotulos_cache is None:
        if not PLANTILLA.exists():
            raise Rechazo("Falta la plantilla de EECC en el servidor (backend/plantillas)", 500)
        filas = {fila for _, filas in _NOTAS_CUADROS.values() for fila, _ in filas}
        ws = load_workbook(PLANTILLA, read_only=True)["Notas"]
        _rotulos_cache = {}
        for (celda,) in ws.iter_rows(
            min_row=min(filas), max_row=max(filas), min_col=2, max_col=2
        ):
            if celda.row in filas:
                # En el modelo hay saltos de línea y espacios duros: para
                # mostrar en pantalla los pasamos a espacio común.
                _rotulos_cache[celda.row] = (
                    str(celda.value or "").replace("\n", " ").replace("\xa0", " ")
                )
    return _rotulos_cache


def _es_celda_cargable(clave: str) -> bool:
    """¿La clave "2.3:44:C" apunta a un renglón de importe de un cuadro?"""
    partes = clave.split(":")
    if len(partes) != 3 or not partes[1].isdigit():
        return False
    nota, fila, letra = partes[0], int(partes[1]), partes[2]
    spec = _NOTAS_CUADROS.get(nota)
    if spec is None:
        return False
    columnas, filas = spec
    if letra not in {c[0] for c in columnas}:
        return False
    return any(f == fila and tipo in ("dato", "prevision") for f, tipo in filas)


def _armar_cuadro(nota: str, valores: dict) -> dict | None:
    """El cuadro de la nota con las sumatorias ya calculadas.

    `valores` tiene los importes cargados a mano con clave (nota, fila, letra).
    Los Subtotal y Total los calcula el backend en Decimal (el modelo los deja
    en blanco); las celdas sin cargar viajan como null.
    """
    spec = _NOTAS_CUADROS.get(nota)
    if spec is None:
        return None
    columnas, filas = spec
    rotulos = _rotulos_plantilla()
    letras = [letra for letra, _, _ in columnas]
    acum = {l: CERO for l in letras}   # datos desde el último cálculo
    prev = {l: CERO for l in letras}   # previsiones desde el último Total
    subtotal = None
    salida = []
    for fila, tipo in filas:
        celdas = {}
        for letra in letras:
            if tipo == "subtotal":
                celdas[letra] = {"valor": _money(acum[letra]), "calc": True}
            elif tipo == "total":
                base = subtotal[letra] if subtotal is not None else acum[letra]
                celdas[letra] = {"valor": _money(base + prev[letra]), "calc": True}
            else:
                guardado = valores.get((nota, fila, letra))
                celdas[letra] = {
                    "valor": _money(guardado) if guardado is not None else None,
                    "calc": False,
                }
        if tipo == "dato":
            for letra in letras:
                v = celdas[letra]["valor"]
                acum[letra] += v if v is not None else CERO
        elif tipo == "prevision":
            for letra in letras:
                v = celdas[letra]["valor"]
                prev[letra] += v if v is not None else CERO
        elif tipo == "subtotal":
            subtotal = {l: celdas[l]["valor"] for l in letras}
            acum = {l: CERO for l in letras}
        else:  # total: cierra y reinicia para el próximo bloque
            subtotal = None
            prev = {l: CERO for l in letras}
            acum = {l: CERO for l in letras}
        salida.append(
            {
                "fila": fila,
                "rotulo": rotulos.get(fila, ""),
                "tipo": tipo,
                "celdas": celdas,
            }
        )
    return {
        "columnas": [
            {"letra": letra, "grupo": grupo, "etiqueta": etiqueta}
            for letra, grupo, etiqueta in columnas
        ],
        "filas": salida,
    }

# Texto original de cada celda, leído de la plantilla una sola vez.
_plantilla_notas_cache: dict[str, str] | None = None


def _celdas_plantilla_notas() -> dict[str, str]:
    global _plantilla_notas_cache
    if _plantilla_notas_cache is None:
        if not PLANTILLA.exists():
            raise Rechazo("Falta la plantilla de EECC en el servidor (backend/plantillas)", 500)
        ws = load_workbook(PLANTILLA, read_only=True)["Notas"]
        _plantilla_notas_cache = {
            clave: str(ws[celda].value or "")
            for clave, celda in _NOTAS_CELDAS.items()
        }
    return _plantilla_notas_cache


def _partir_nota(clave: str, texto_plantilla: str) -> tuple[str | None, str]:
    """Separa el encabezado del modelo ("2.1. Caja y bancos") del cuerpo."""
    lineas = texto_plantilla.split("\n")
    if lineas and (
        lineas[0].startswith(f"{clave}.")
        or lineas[0].startswith(f"{clave} ")
        or lineas[0].startswith(f"{clave}\t")
    ):
        return lineas[0], "\n".join(lineas[1:])
    return None, texto_plantilla


def _notas_de(db: Session, ejercicio_id: int) -> list[dict]:
    """Las notas del ejercicio: lo guardado, o el texto de la plantilla."""
    guardadas = {
        n.clave: n.texto
        for n in db.query(BalanceNota).filter(BalanceNota.ejercicio_id == ejercicio_id)
    }
    valores_celda: dict = {}
    for c in db.query(BalanceNotaCelda).filter(
        BalanceNotaCelda.ejercicio_id == ejercicio_id
    ):
        partes = c.clave.split(":")
        if len(partes) == 3 and partes[1].isdigit():
            valores_celda[(partes[0], int(partes[1]), partes[2])] = c.valor
    plantilla = _celdas_plantilla_notas()
    salida = []
    for seccion, titulo_seccion, notas in _NOTAS_SECCIONES:
        for clave, titulo, _ in notas:
            encabezado, cuerpo = _partir_nota(clave, plantilla[clave])
            if clave in guardadas:
                cuerpo = guardadas[clave]
            salida.append(
                {
                    "seccion": seccion,
                    "seccion_titulo": titulo_seccion,
                    "clave": clave,
                    "titulo": titulo,
                    "encabezado": encabezado,
                    "texto": cuerpo,
                    "cuadro": _armar_cuadro(clave, valores_celda),
                }
            )
    return salida


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _money(valor) -> Decimal:
    try:
        d = Decimal(str(valor if valor is not None else 0))
    except Exception:
        d = CERO
    if not d.is_finite():
        d = CERO
    return d.quantize(_DOS, rounding=ROUND_HALF_UP)


def _num(valores, seccion: str, clave: str, campo: str) -> Decimal:
    fila = valores.get((seccion, clave))
    return _money(getattr(fila, campo) if fila else 0)


def _a_json(obj):
    """Los importes viajan como Decimal y llegan a JSON como float."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _a_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_a_json(v) for v in obj]
    return obj


def _cabecera(ej: BalanceEjercicio) -> dict:
    def _num(valor):
        return float(valor) if valor is not None else None

    return {
        "id": ej.id,
        "cliente_id": ej.cliente_id,
        "nombre": ej.nombre,
        "fecha_inicio": ej.fecha_inicio.isoformat(),
        "fecha_fin": ej.fecha_fin.isoformat(),
        # Ejercicio contable elegido (años + día/mes de cierre del cliente).
        "anio_inicio": ej.anio_inicio,
        "anio_fin": ej.anio_fin,
        "dia_mes_cierre": ej.dia_mes_cierre,
        "mes_cierre": ej.mes_cierre,
        "entidad": ej.entidad,
        "cuit": ej.cuit,
        "domicilio": ej.domicilio,
        "actividad": ej.actividad,
        "actividad_secundaria": ej.actividad_secundaria,
        # Registro Público de Comercio / sociedad controlante.
        "fecha_inscripcion_rpc": ej.fecha_inscripcion_rpc,
        "fecha_estatuto": ej.fecha_estatuto,
        "fecha_modificacion_estatuto": ej.fecha_modificacion_estatuto,
        "fecha_vencimiento_entidad": ej.fecha_vencimiento_entidad,
        "matricula_rpc": ej.matricula_rpc,
        "identificacion_rpc": ej.identificacion_rpc,
        "duracion_entidad": ej.duracion_entidad,
        "unidad_medida": ej.unidad_medida,
        "controlante_denominacion": ej.controlante_denominacion,
        "controlante_domicilio": ej.controlante_domicilio,
        "controlante_actividad": ej.controlante_actividad,
        "controlante_participacion": ej.controlante_participacion,
        "controlante_votos": ej.controlante_votos,
        "entes_nota": ej.entes_nota,
        # Composición del capital.
        "cap_circ_cantidad": ej.cap_circ_cantidad,
        "cap_circ_tipo": ej.cap_circ_tipo,
        "cap_circ_votos": ej.cap_circ_votos,
        "cap_circ_suscripto": _num(ej.cap_circ_suscripto),
        "cap_circ_integrado": _num(ej.cap_circ_integrado),
        "cap_cart_cantidad": ej.cap_cart_cantidad,
        "cap_cart_tipo": ej.cap_cart_tipo,
        "cap_cart_votos": ej.cap_cart_votos,
        "cap_cart_suscripto": _num(ej.cap_cart_suscripto),
        "cap_cart_integrado": _num(ej.cap_cart_integrado),
        "actualizado": ej.actualizado.isoformat() if ej.actualizado else None,
    }


def _buscar_ejercicio(db: Session, ejercicio_id: int) -> BalanceEjercicio:
    ejercicio = db.get(BalanceEjercicio, ejercicio_id)
    if ejercicio is None:
        raise Rechazo("No existe ese ejercicio de balance", 404)
    return ejercicio


def _domicilio_de(cliente: Cliente) -> str | None:
    partes = [p for p in (cliente.calle, cliente.numero_calle) if p]
    if cliente.localidad:
        partes.append(cliente.localidad)
    return " ".join(partes) or None


def _validar_fechas(inicio: date, fin: date) -> None:
    if fin < inicio:
        raise Rechazo("La fecha de cierre no puede ser anterior al inicio del ejercicio", 400)


# ---------------------------------------------------------------------------
# Armado de los estados (los totales se calculan acá)
# ---------------------------------------------------------------------------

def _completar_fila(celdas: dict) -> None:
    """Llena las columnas calculadas y el total de una fila del EEPN."""
    for campo in ("actual", "anterior"):
        tot_aportes = sum(
            (celdas[c][campo] for c in ("capital", "ajustes", "aportes", "primas")), CERO
        )
        tot_res = celdas["res_legal"][campo] + celdas["otras_res"][campo]
        tot_resul = tot_res + celdas["rna"][campo] + celdas["rd"][campo]
        calculadas = (
            ("tot_aportes", tot_aportes),
            ("tot_res", tot_res),
            ("tot_resul", tot_resul),
            ("total", tot_aportes + tot_resul),
        )
        for col, valor in calculadas:
            celdas.setdefault(col, {"actual": CERO, "anterior": CERO})[campo] = _money(valor)


def _sumar_filas(a: dict, b: dict) -> dict:
    res = {}
    for col in _EEPN_COLS_DATO:
        res[col] = {
            "actual": a[col]["actual"] + b[col]["actual"],
            "anterior": a[col]["anterior"] + b[col]["anterior"],
        }
    _completar_fila(res)
    return res


def _armar_eepn(valores) -> dict:
    celdas = {}
    for fila, _, tipo in _EEPN_FILAS:
        if tipo != "dato":
            continue
        celdas[fila] = {
            col: {
                "actual": _num(valores, "eepn", f"{fila}:{col}", "valor_actual"),
                "anterior": _num(valores, "eepn", f"{fila}:{col}", "valor_anterior"),
            }
            for col in _EEPN_COLS_DATO
        }
        _completar_fila(celdas[fila])

    celdas["inicio_modif"] = _sumar_filas(celdas["inicio"], celdas["modif"])
    cierre = celdas["inicio_modif"]
    for movimiento in _EEPN_MOVIMIENTOS:
        cierre = _sumar_filas(cierre, celdas[movimiento])
    celdas["cierre"] = cierre

    filas = []
    for fila, etiqueta, tipo in _EEPN_FILAS:
        if tipo == "titulo":
            filas.append({"tipo": tipo, "clave": fila, "etiqueta": etiqueta})
            continue
        c = celdas[fila]
        filas.append(
            {
                "tipo": tipo,
                "clave": fila,
                "etiqueta": etiqueta,
                "celdas": {col: c[col] for col, _, _, _ in _EEPN_COLS},
                "actual": c["total"]["actual"],
                "anterior": c["total"]["anterior"],
            }
        )

    return {
        "columnas": [
            {"clave": clave, "etiqueta": etiqueta, "calc": calc, "grupo": grupo}
            for clave, etiqueta, calc, grupo in _EEPN_COLS
        ],
        "filas": filas,
    }


def _armar_esp(valores, pn_actual: Decimal, pn_anterior: Decimal) -> dict:
    def armar_lado(bloques):
        filas = []
        totales = {}
        for clave_bloque, titulo, rubros in bloques:
            filas.append({"tipo": "titulo", "clave": clave_bloque, "etiqueta": titulo})
            suma_a = suma_p = CERO
            for clave, etiqueta, nota in rubros:
                a = _num(valores, "esp", clave, "valor_actual")
                p = _num(valores, "esp", clave, "valor_anterior")
                suma_a += a
                suma_p += p
                filas.append(
                    {
                        "tipo": "rubro",
                        "clave": clave,
                        "etiqueta": etiqueta,
                        "nota": nota,
                        "actual": a,
                        "anterior": p,
                    }
                )
            filas.append(
                {
                    "tipo": "total",
                    "clave": f"t_{clave_bloque}",
                    "etiqueta": f"Total del {titulo.lower()}",
                    "actual": _money(suma_a),
                    "anterior": _money(suma_p),
                }
            )
            totales[clave_bloque] = (suma_a, suma_p)
        return filas, totales

    activo, t_act = armar_lado(_ESP_ACTIVO)
    t_ac, t_anc = t_act["activo_corriente"], t_act["activo_no_corriente"]
    activo.append(
        {
            "tipo": "total",
            "clave": "t_activo",
            "etiqueta": "TOTAL DEL ACTIVO",
            "actual": _money(t_ac[0] + t_anc[0]),
            "anterior": _money(t_ac[1] + t_anc[1]),
        }
    )

    pasivo, t_pas = armar_lado(_ESP_PASIVO)
    t_pc, t_pnc = t_pas["pasivo_corriente"], t_pas["pasivo_no_corriente"]
    total_pasivo = (t_pc[0] + t_pnc[0], t_pc[1] + t_pnc[1])
    pasivo.append(
        {
            "tipo": "total",
            "clave": "t_pasivo",
            "etiqueta": "TOTAL DEL PASIVO",
            "actual": _money(total_pasivo[0]),
            "anterior": _money(total_pasivo[1]),
        }
    )
    pasivo.append(
        {
            "tipo": "total",
            "clave": "t_pn",
            "etiqueta": "PATRIMONIO NETO (según el estado correspondiente)",
            "actual": _money(pn_actual),
            "anterior": _money(pn_anterior),
        }
    )
    pasivo.append(
        {
            "tipo": "total",
            "clave": "t_pasivo_pn",
            "etiqueta": "TOTAL DEL PASIVO Y PATRIM. NETO",
            "actual": _money(total_pasivo[0] + pn_actual),
            "anterior": _money(total_pasivo[1] + pn_anterior),
        }
    )
    return {"activo": activo, "pasivo": pasivo}


def _armar_er(valores) -> dict:
    dato = {}
    for clave, _, _, tipo in _ER:
        if tipo == "dato":
            dato[clave] = (
                _num(valores, "er", clave, "valor_actual"),
                _num(valores, "er", clave, "valor_anterior"),
            )

    bruta = (dato["ingresos"][0] - dato["costo"][0], dato["ingresos"][1] - dato["costo"][1])
    otros = tuple(
        sum((dato[k][i] for k in _ER_OTROS), CERO) for i in (0, 1)
    )
    antes = (bruta[0] + otros[0], bruta[1] + otros[1])
    continuan = (antes[0] - dato["impuesto"][0], antes[1] - dato["impuesto"][1])
    resultado = (
        continuan[0] + dato["discontinuadas"][0],
        continuan[1] + dato["discontinuadas"][1],
    )
    calculados = {"bruta": bruta, "antes_imp": antes, "continuan": continuan, "resultado": resultado}

    filas = []
    for clave, etiqueta, nota, tipo in _ER:
        if tipo == "dato":
            valores_fila = dato[clave]
        else:
            valores_fila = calculados[tipo]
        filas.append(
            {
                "tipo": "rubro" if tipo == "dato" else "calc",
                "clave": clave,
                "etiqueta": etiqueta,
                "nota": nota,
                "actual": _money(valores_fila[0]),
                "anterior": _money(valores_fila[1]),
            }
        )
    return filas


# ---------------------------------------------------------------------------
# Ejercicio contable: el usuario elige los años y el día/mes viene del cliente
# ---------------------------------------------------------------------------

def dias_del_mes(anio: int, mes: int) -> int:
    """Cuántos días tiene ese mes en ese año (28/29 en febrero)."""
    if mes == 12:
        return 31
    return (date(anio + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1)).day


def dia_cierre_valido(anio: int, mes: int, dia: int) -> int:
    """Corrige el día si ese mes no lo tiene (ej.: 29/02 en año no bisiesto → 28)."""
    return min(dia, dias_del_mes(anio, mes))


def intervalo_desde_anos(anio_inicio: int, anio_fin: int, dia: int, mes: int):
    """Arma el intervalo contable a partir de los años y el día/mes de cierre.

    El ejercicio va del día siguiente al cierre del año elegido como inicio,
    hasta el propio día/mes de cierre del año elegido como fin.
    Ej.: cierre 31/07, de 2024 a 2025 → 01/08/2024 a 31/07/2025.
    """
    if anio_fin < anio_inicio:
        raise Rechazo("El año de cierre no puede ser anterior al de inicio", 400)
    fin = date(anio_fin, mes, dia_cierre_valido(anio_fin, mes, dia))
    inicio = fin.replace(year=anio_inicio) + timedelta(days=1) if anio_inicio < anio_fin else fin
    if anio_inicio == anio_fin:
        # Mismo año: el ejercicio cierra el día/mes elegido de ese año.
        inicio = fin
    if inicio > fin:
        raise Rechazo("El intervalo del ejercicio no es válido", 400)
    return inicio, fin


def _cierre_del_cliente(cliente) -> tuple[int, int] | None:
    """Día y mes de cierre del cliente (de `fecha_cierre_ejercicio`)."""
    f = getattr(cliente, "fecha_cierre_ejercicio", None)
    if f is None:
        return None
    return f.day, f.month


# ---------------------------------------------------------------------------
# Servicios (lo que usa el router)
# ---------------------------------------------------------------------------

def listar_ejercicios(db: Session, cliente_id: int) -> list[dict]:
    if db.get(Cliente, cliente_id) is None:
        raise Rechazo("No existe ese cliente", 404)
    ejercicios = (
        db.query(BalanceEjercicio)
        .filter(BalanceEjercicio.cliente_id == cliente_id)
        .order_by(BalanceEjercicio.fecha_fin.desc(), BalanceEjercicio.id.desc())
        .all()
    )
    return [_cabecera(e) for e in ejercicios]


def crear(db: Session, datos: EjercicioCrear) -> dict:
    cliente = db.get(Cliente, datos.cliente_id)
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)

    # El día/mes de cierre: primero lo que viene en el pedido; si no, el del
    # cliente (de `fecha_cierre_ejercicio`, que se repite todos los años).
    dia = datos.dia_mes_cierre
    mes = datos.mes_cierre
    if dia is None or mes is None:
        del_cliente = _cierre_del_cliente(cliente)
        if del_cliente:
            dia, mes = del_cliente

    fecha_inicio, fecha_fin = datos.fecha_inicio, datos.fecha_fin
    if datos.anio_inicio and datos.anio_fin and dia and mes:
        fecha_inicio, fecha_fin = intervalo_desde_anos(
            datos.anio_inicio, datos.anio_fin, dia, mes
        )
    if fecha_inicio is None or fecha_fin is None:
        raise Rechazo(
            "Elegí el año de inicio y el de cierre del ejercicio "
            "(o mandá las fechas)", 400
        )

    _validar_fechas(fecha_inicio, fecha_fin)
    repetido = (
        db.query(BalanceEjercicio)
        .filter(
            BalanceEjercicio.cliente_id == datos.cliente_id,
            BalanceEjercicio.nombre == datos.nombre,
        )
        .first()
    )
    if repetido:
        raise Rechazo("Ese cliente ya tiene un ejercicio con ese nombre", 409)

    ejercicio = BalanceEjercicio(
        cliente_id=datos.cliente_id,
        nombre=datos.nombre,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        anio_inicio=datos.anio_inicio,
        anio_fin=datos.anio_fin,
        dia_mes_cierre=dia,
        mes_cierre=mes,
        # Carátula: se copia de la ficha del cliente y se puede corregir a mano.
        entidad=datos.entidad if datos.entidad is not None else cliente.nombre_completo,
        cuit=datos.cuit if datos.cuit is not None else cliente.cuit,
        domicilio=datos.domicilio if datos.domicilio is not None else _domicilio_de(cliente),
        actividad=(
            datos.actividad
            if datos.actividad is not None
            else (cliente.actividad_economica.capitalize() if cliente.actividad_economica else None)
        ),
        actividad_secundaria=datos.actividad_secundaria,
    )
    db.add(ejercicio)
    db.commit()
    db.refresh(ejercicio)
    return obtener(db, ejercicio.id)


def recalcular_cuadros(celdas: list[CeldaNotaIn]) -> dict:
    """Los cuadros de las notas con estos importes, sin tocar la base.

    Para mostrar los Subtotal/Total apenas el usuario deja de escribir:
    la suma la hace igual el backend, nunca el navegador.
    """
    valores: dict = {}
    for celda in celdas:
        if not _es_celda_cargable(celda.clave):
            raise Rechazo(f"Celda de nota no válida: {celda.clave}", 400)
        partes = celda.clave.split(":")
        valores[(partes[0], int(partes[1]), partes[2])] = _money(celda.valor)
    return _a_json({nota: _armar_cuadro(nota, valores) for nota in _NOTAS_CUADROS})


def obtener(db: Session, ejercicio_id: int) -> dict:
    ejercicio = _buscar_ejercicio(db, ejercicio_id)
    valores = {
        (v.seccion, v.clave): v
        for v in db.query(BalanceValor).filter(BalanceValor.ejercicio_id == ejercicio_id)
    }
    eepn = _armar_eepn(valores)
    cierre = next(f for f in eepn["filas"] if f["clave"] == "cierre")
    esp = _armar_esp(valores, Decimal(str(cierre["actual"])), Decimal(str(cierre["anterior"])))
    er = _armar_er(valores)
    notas = _notas_de(db, ejercicio_id)
    return _a_json(
        {
            "cabecera": _cabecera(ejercicio),
            "esp": esp,
            "er": er,
            "eepn": eepn,
            "notas": notas,
        }
    )


def guardar(db: Session, ejercicio_id: int, datos: BalanceGuardar) -> dict:
    ejercicio = _buscar_ejercicio(db, ejercicio_id)
    _validar_fechas(datos.cabecera.fecha_inicio, datos.cabecera.fecha_fin)
    repetido = (
        db.query(BalanceEjercicio)
        .filter(
            BalanceEjercicio.cliente_id == ejercicio.cliente_id,
            BalanceEjercicio.nombre == datos.cabecera.nombre,
            BalanceEjercicio.id != ejercicio_id,
        )
        .first()
    )
    if repetido:
        raise Rechazo("Ya existe otro ejercicio con ese nombre para ese cliente", 409)

    for campo, valor in datos.cabecera.model_dump().items():
        setattr(ejercicio, campo, valor)
    ejercicio.actualizado = datetime.utcnow()

    existentes = {
        (v.seccion, v.clave): v
        for v in db.query(BalanceValor).filter(BalanceValor.ejercicio_id == ejercicio_id)
    }
    for valor in datos.valores:
        clave = (valor.seccion, valor.clave)
        if clave not in _CLAVES:
            raise Rechazo(f"Rubro no válido: {valor.clave}", 400)
        actual = _money(valor.valor_actual)
        anterior = _money(valor.valor_anterior)
        fila = existentes.get(clave)
        if fila:
            fila.valor_actual = actual
            fila.valor_anterior = anterior
        else:
            db.add(
                BalanceValor(
                    ejercicio_id=ejercicio_id,
                    seccion=valor.seccion,
                    clave=valor.clave,
                    valor_actual=actual,
                    valor_anterior=anterior,
                )
            )

    if datos.notas is not None:
        notas_existentes = {
            n.clave: n
            for n in db.query(BalanceNota).filter(BalanceNota.ejercicio_id == ejercicio_id)
        }
        for nota in datos.notas:
            if nota.clave not in _NOTAS_CLAVES:
                raise Rechazo(f"Nota no válida: {nota.clave}", 400)
            fila_nota = notas_existentes.get(nota.clave)
            if fila_nota:
                fila_nota.texto = nota.texto
            else:
                db.add(
                    BalanceNota(
                        ejercicio_id=ejercicio_id, clave=nota.clave, texto=nota.texto
                    )
                )

    if datos.celdas_nota is not None:
        # Se guardan solo las celdas con importe: una celda vacía significa
        # "no cargada" y se borra. Primero se valida todo, después se reemplaza.
        por_clave = {c.clave: c.valor for c in datos.celdas_nota}
        for clave in por_clave:
            if not _es_celda_cargable(clave):
                raise Rechazo(f"Celda de nota no válida: {clave}", 400)
        db.query(BalanceNotaCelda).filter(
            BalanceNotaCelda.ejercicio_id == ejercicio_id
        ).delete(synchronize_session=False)
        for clave, valor in por_clave.items():
            db.add(
                BalanceNotaCelda(
                    ejercicio_id=ejercicio_id, clave=clave, valor=_money(valor)
                )
            )
    db.commit()
    return obtener(db, ejercicio_id)


def eliminar(db: Session, ejercicio_id: int) -> None:
    ejercicio = _buscar_ejercicio(db, ejercicio_id)
    db.query(BalanceValor).filter(
        BalanceValor.ejercicio_id == ejercicio_id
    ).delete(synchronize_session=False)
    db.query(BalanceNota).filter(
        BalanceNota.ejercicio_id == ejercicio_id
    ).delete(synchronize_session=False)
    db.query(BalanceNotaCelda).filter(
        BalanceNotaCelda.ejercicio_id == ejercicio_id
    ).delete(synchronize_session=False)
    db.delete(ejercicio)
    db.commit()


# ---------------------------------------------------------------------------
# Export: llena la plantilla del modelo y devuelve el .xlsx
# ---------------------------------------------------------------------------

_FILAS_EEPN = {
    "inicio": 8,
    "modif": 9,
    "suscripcion": 11,
    "dist_res_legal": 13,
    "dist_div_efectivo": 14,
    "dist_div_acciones": 15,
    "ganancia": 16,
    "otro": 17,
}
_COLS_EEPN = {"capital": 4, "ajustes": 5, "aportes": 6, "primas": 7,
              "res_legal": 9, "otras_res": 10, "rna": 12, "rd": 13}
_FILAS_ER = {"ingresos": 7, "costo": 8, "gastos_adm": 10, "gastos_com": 11,
             "otros_gastos": 12, "cambios_vr": 13, "desval": 14, "otras_gan": 15,
             "otros_ing": 16, "otros_egr": 17, "impuesto": 19, "discontinuadas": 21}


def _f(iso: str) -> str:
    """'2025-12-31' -> '31/12/2025'."""
    return "/".join(reversed(iso.split("-")))


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-")[:40] or "cliente"


def exportar_excel(db: Session, ejercicio_id: int) -> tuple[str, bytes]:
    if not PLANTILLA.exists():
        raise Rechazo("Falta la plantilla de EECC en el servidor (backend/plantillas)", 500)
    data = obtener(db, ejercicio_id)
    cab = data["cabecera"]
    fecha_fin = _f(cab["fecha_fin"])
    fecha_comp = _f(
        (date.fromisoformat(cab["fecha_inicio"]) - timedelta(days=1)).isoformat()
    )

    wb = load_workbook(PLANTILLA)

    # Carátula ------------------------------------------------------------
    ws = wb["CARATULA"]
    ws["C3"] = cab["entidad"] or ws["C3"].value
    ws["C6"] = (
        f"INICIADO EL {cab['fecha_inicio'][8:10]}/{cab['fecha_inicio'][5:7]}/{cab['fecha_inicio'][:4]}"
        f" Y FINALIZADO EL {fecha_fin}"
    )
    if cab["cuit"]:
        ws["C11"] = f"CUIT: {cab['cuit']}"
    if cab["domicilio"]:
        ws["C13"] = f"Domicilio Legal: {cab['domicilio']}"
    if cab["actividad"]:
        ws["C15"] = f"Actividad Principal: {cab['actividad']}"
    if cab["actividad_secundaria"]:
        ws["C17"] = f"Actividad/es Secundaria/s: {cab['actividad_secundaria']}"

    # Registro Público de Comercio y sociedad controlante. El modelo trae
    # marcadores "…": con valor se reemplazan, sin valor la celda queda
    # exactamente como está.
    def _fecha_barras(valor: str) -> str:
        if len(valor) == 10 and valor[4] == "-":
            return f"{valor[8:10]}/{valor[5:7]}/{valor[:4]}"
        return valor

    for celda, valor, es_fecha in (
        ("C20", cab["fecha_inscripcion_rpc"], True),
        ("C22", cab["fecha_estatuto"], True),
        ("G22", cab["matricula_rpc"], False),
        ("C23", cab["fecha_modificacion_estatuto"], True),
        ("C24", cab["identificacion_rpc"], False),
        ("G26", cab["duracion_entidad"], False),
        ("G27", cab["fecha_vencimiento_entidad"], True),
    ):
        if valor is None or valor == "":
            continue
        marca = _fecha_barras(str(valor)) if es_fecha else str(valor)
        texto = str(ws[celda].value or "")
        ws[celda] = texto.replace("…/…/…", marca).replace("…", marca)

    # Estos vienen sin marcador: se agrega la etiqueta del modelo y el valor.
    for celda, valor in (
        ("C28", cab["unidad_medida"]),
        ("C29", cab["controlante_denominacion"]),
        ("C30", cab["controlante_domicilio"]),
        ("C31", cab["controlante_actividad"]),
        ("C32", cab["controlante_participacion"]),
        ("C33", cab["controlante_votos"]),
        ("C35", cab["entes_nota"]),
    ):
        if not valor:
            continue
        etiqueta = str(ws[celda].value or "").rstrip()
        if not etiqueta.endswith(":"):
            etiqueta += ":"
        ws[celda] = f"{etiqueta} {valor}"

    # Composición del capital: un renglón por tabla (45 = en circulación,
    # 52 = en cartera). Cada campo se escribe solamente si tiene valor.
    for fila, prefijo in ((45, "cap_circ"), (52, "cap_cart")):
        if cab[f"{prefijo}_cantidad"] is not None:
            ws[f"C{fila}"] = int(cab[f"{prefijo}_cantidad"])
        if cab[f"{prefijo}_tipo"]:
            ws[f"D{fila}"] = cab[f"{prefijo}_tipo"]
        if cab[f"{prefijo}_votos"] is not None:
            ws[f"E{fila}"] = int(cab[f"{prefijo}_votos"])
        if cab[f"{prefijo}_suscripto"] is not None:
            ws[f"G{fila}"] = float(cab[f"{prefijo}_suscripto"])
        if cab[f"{prefijo}_integrado"] is not None:
            ws[f"H{fila}"] = float(cab[f"{prefijo}_integrado"])

    # Estado de Situación Patrimonial -------------------------------------
    ws = wb["ESP"]
    ws["B2"] = cab["entidad"] or ws["B2"].value
    ws["F4"] = fecha_fin
    ws["G4"] = fecha_comp
    filas_activo = [f for f in data["esp"]["activo"] if f["tipo"] == "rubro"]
    filas_pasivo = [f for f in data["esp"]["pasivo"] if f["tipo"] == "rubro"]
    for i, f in enumerate(filas_activo[:11]):  # corriente: filas 7 a 17
        ws.cell(row=7 + i, column=6, value=f["actual"])
        ws.cell(row=7 + i, column=7, value=f["anterior"])
    for i, f in enumerate(filas_activo[11:]):  # no corriente: filas 20 a 32
        ws.cell(row=20 + i, column=6, value=f["actual"])
        ws.cell(row=20 + i, column=7, value=f["anterior"])
    for i, f in enumerate(filas_pasivo[:9]):
        ws.cell(row=7 + i, column=12, value=f["actual"])
        ws.cell(row=7 + i, column=13, value=f["anterior"])
    for i, f in enumerate(filas_pasivo[9:]):
        ws.cell(row=20 + i, column=12, value=f["actual"])
        ws.cell(row=20 + i, column=13, value=f["anterior"])

    # Estado de Resultados -------------------------------------------------
    ws = wb["E.R."]
    ws["B2"] = cab["entidad"] or ws["B2"].value
    ws["E5"] = fecha_fin
    ws["F5"] = fecha_comp
    for f in data["er"]:
        fila = _FILAS_ER.get(f["clave"])
        if not fila:
            continue
        ws.cell(row=fila, column=5, value=f["actual"])   # columna E
        ws.cell(row=fila, column=6, value=f["anterior"])  # columna F
    # F22 es el único literal del comparativo (en el modelo es 0)
    resultado = next(f for f in data["er"] if f["clave"] == "resultado")
    ws["F22"] = resultado["anterior"]

    # Evolución del Patrimonio Neto ----------------------------------------
    ws = wb["EEPN"]
    ws["B2"] = cab["entidad"] or ws["B2"].value
    ws["O6"] = fecha_fin
    ws["P6"] = fecha_comp
    for fila in data["eepn"]["filas"]:
        if fila["tipo"] != "dato":
            continue
        fila_excel = _FILAS_EEPN[fila["clave"]]
        for col, col_excel in _COLS_EEPN.items():
            ws.cell(row=fila_excel, column=col_excel, value=fila["celdas"][col]["actual"])
        # Columna P: total de la fila del ejercicio anterior (P18 suma solo,
        # no se pisa ninguna fórmula).
        ws.cell(row=fila_excel, column=16, value=fila["anterior"])

    # Notas a los estados contables ----------------------------------------
    # Solo las que se guardaron: si nadie tocó una nota, la celda de la
    # plantilla queda exactamente como está.
    plantilla_notas = _celdas_plantilla_notas()
    ws = wb["Notas"]
    notas_guardadas = (
        db.query(BalanceNota).filter(BalanceNota.ejercicio_id == ejercicio_id).all()
    )
    for nota in notas_guardadas:
        encabezado, _ = _partir_nota(nota.clave, plantilla_notas[nota.clave])
        if encabezado and nota.texto:
            final = f"{encabezado}\n{nota.texto}"
        else:
            final = encabezado or nota.texto
        ws[_NOTAS_CELDAS[nota.clave]] = final or None

    # Cuadros de composición: solo los que tienen importes cargados. Se
    # escriben los importes a mano y los Subtotal/Total calculados acá (en la
    # plantilla están en blanco); el resto de la hoja queda intacto.
    celdas_guardadas = (
        db.query(BalanceNotaCelda).filter(BalanceNotaCelda.ejercicio_id == ejercicio_id).all()
    )
    if celdas_guardadas:
        valores_nota: dict = {}
        notas_con_celdas: set[str] = set()
        for c in celdas_guardadas:
            notas_con_celdas.add(c.clave.split(":")[0])
            partes = c.clave.split(":")
            if len(partes) == 3 and partes[1].isdigit():
                valores_nota[(partes[0], int(partes[1]), partes[2])] = c.valor
        for nota_clave in notas_con_celdas:
            cuadro = _armar_cuadro(nota_clave, valores_nota)
            if cuadro is None:
                continue
            for fila in cuadro["filas"]:
                for letra, celda in fila["celdas"].items():
                    cargada = (nota_clave, fila["fila"], letra) in valores_nota
                    if celda["calc"] or cargada:
                        ws[f"{letra}{fila['fila']}"] = float(celda["valor"])

    salida = BytesIO()
    wb.save(salida)
    nombre = f"EECC-{_slug(cab['entidad'])}-{_slug(cab['nombre'])}.xlsx"
    return nombre, salida.getvalue()


# ---------------------------------------------------------------------------
# Moneda homogénea (FACPCE): actualización del balance por índice
# ---------------------------------------------------------------------------

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _proxima_fecha_cierre(actual: date, cliente: Cliente | None) -> date:
    """Próximo cierre de ejercicio posterior a `actual`.

    Usa el día y el mes del campo "fecha de cierre de ejercicio" de la ficha
    del cliente (el año del campo no importa: es un cierre que se repite).
    Si no está cargado, un año después del cierre actual (29/2 ajusta a
    28/2 en años sin ese día).
    """
    ancla = cliente.fecha_cierre_ejercicio if cliente else None
    if ancla:
        for anio in range(actual.year, actual.year + 4):
            try:
                candidata = date(anio, ancla.month, ancla.day)
            except ValueError:  # 29 de febrero en año bisiesto sin ese día
                candidata = date(anio, ancla.month, 28)
            if candidata > actual:
                return candidata
    try:
        return actual.replace(year=actual.year + 1)
    except ValueError:
        return actual.replace(year=actual.year + 1, day=28)


def _indice_o_rechazo(db: Session, fecha: date, periodo: str) -> Decimal:
    fila = indice_service.del_mes(db, fecha)
    if fila is None:
        raise Rechazo(
            f"Falta el índice de {MESES[fecha.month - 1]} de {fecha.year} "
            f"({periodo}). Cargalo en Configuración.",
            400,
        )
    # Se usa con4 decimales, igual que se muestra (ej.: 12.276,7660).
    indice = Decimal(fila.indice).quantize(_CUATRO, ROUND_HALF_UP)
    if indice <= 0:
        raise Rechazo(
            f"El índice de {MESES[fecha.month - 1]} de {fecha.year} no puede ser cero",
            400,
        )
    return indice


def moneda_homogenea(db: Session, ejercicio_id: int) -> dict:
    """Datos del balance al cierre, actualizados con el índice FACPCE.

    Coeficiente = índice de la próxima fecha de cierre ÷ índice del cierre
    del balance. El resultado multiplica Saldo al cierre (Situación
    Patrimonial y Resultados); las sumatorias también se calculan acá.
    """
    ejercicio = _buscar_ejercicio(db, ejercicio_id)
    cliente = db.get(Cliente, ejercicio.cliente_id)
    cierre = ejercicio.fecha_fin
    proximo = _proxima_fecha_cierre(cierre, cliente)

    ind_anterior = _indice_o_rechazo(db, cierre, "fecha de cierre del balance")
    ind_nuevo = _indice_o_rechazo(db, proximo, "próxima fecha de cierre")
    # El coeficiente se calcula y se usa con4 decimales (redondeo normal).
    coeficiente = (ind_nuevo / ind_anterior).quantize(_CUATRO, ROUND_HALF_UP)

    data = obtener(db, ejercicio_id)

    def escala(filas: list[dict]) -> list[dict]:
        salida = []
        for f in filas:
            fila = dict(f)
            if f.get("actual") is not None and f["tipo"] in ("rubro", "total", "calc"):
                fila["actualizado"] = _money(Decimal(str(f["actual"])) * coeficiente)
            salida.append(fila)
        return salida

    return _a_json(
        {
            "cliente": cliente.nombre_completo if cliente else "",
            "ejercicio": ejercicio.nombre,
            "fecha_inicio": ejercicio.fecha_inicio.isoformat(),
            "fecha_fin": cierre.isoformat(),
            "proxima_fecha_cierre": proximo.isoformat(),
            "indice_anterior": {"fecha": cierre.isoformat(), "valor": float(ind_anterior)},
            "indice_nuevo": {"fecha": proximo.isoformat(), "valor": float(ind_nuevo)},
            "coeficiente": float(coeficiente),
            "esp": {
                "activo": escala(data["esp"]["activo"]),
                "pasivo": escala(data["esp"]["pasivo"]),
            },
            "er": escala(data["er"]),
        }
    )


def exportar_moneda_homogenea(db: Session, ejercicio_id: int) -> tuple[str, bytes]:
    """Excel aparte con el balance actualizado por moneda homogénea."""

    def _miles4(valor) -> str:
        """Número con4 decimales y miles con punto: 12.276,7660."""
        texto = f"{float(valor):,.4f}"
        return texto.replace(",", "@").replace(".", ",").replace("@", ".")

    d = moneda_homogenea(db, ejercicio_id)
    negrita = Font(bold=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Moneda homogénea"

    ws["A1"] = "ACTUALIZACIÓN POR MONEDA HOMOGÉNEA — FACPCE (Res. Técnica N° 6)"
    ws["A1"].font = negrita
    ws["A2"] = f"{d['cliente']} — Ejercicio {d['ejercicio']}"
    ws["A3"] = f"Inicio: {_f(d['fecha_inicio'])}   Cierre: {_f(d['fecha_fin'])}"
    ws["A4"] = (
        f"Índice fecha de cierre anterior {_f(d['indice_anterior']['fecha'])}: "
        f"{_miles4(d['indice_anterior']['valor'])}"
    )
    ws["A5"] = (
        f"Índice fecha de cierre nuevo {_f(d['indice_nuevo']['fecha'])}: "
        f"{_miles4(d['indice_nuevo']['valor'])}"
    )
    ws["A6"] = "Coeficiente (nuevo ÷ anterior),4 decimales:"
    ws["A6"].font = negrita
    ws["B6"] = d["coeficiente"]
    ws["B6"].number_format = "#,##0.0000"
    # Coloreamos la celda del coeficiente de gris claro para distinguirla
    ws["B6"].fill = PatternFill("solid", fgColor="E8E8E8")

    # --- NUEVA SECCIÓN: tabla resumen de tres columnas ---
    # Encabezados en la fila 8
    ws["A8"] = "Fecha"
    ws["B8"] = "Índice"
    ws["C8"] = "Coeficiente"
    for c in (8, 9, 10):
        celda = ws.cell(row=c, column=1)
        celda.font = negrita
        celda.alignment = Alignment(horizontal="left")
        celda = ws.cell(row=c, column=2)
        celda.font = negrita
        celda.alignment = Alignment(horizontal="right")
        celda = ws.cell(row=c, column=3)
        celda.font = negrita
        celda.alignment = Alignment(horizontal="right")
    # Datos en la fila 9
    desde = 9
    # Fila anterior (cierre)
    ws.cell(row=desde, column=1, value=_f(d['fecha_fin']))
    ws.cell(row=desde, column=2, value=_miles4(d['indice_anterior']['valor']))
    ws.cell(row=desde, column=3, value=d["coeficiente"])
    ws.cell(row=desde, column=3).number_format = "#,##0.0000"
    ws.cell(row=desde, column=3).fill = PatternFill("solid", fgColor="E8E8E8")  # gris claro
    desde += 1
    # Fila nueva (próximo cierre)
    ws.cell(row=desde, column=1, value=_f(d['proxima_fecha_cierre']))
    ws.cell(row=desde, column=2, value=_miles4(d['indice_nuevo']['valor']))
    ws.cell(row=desde, column=3, value=d["coeficiente"])
    ws.cell(row=desde, column=3).number_format = "#,##0.0000"
    ws.cell(row=desde, column=3).fill = PatternFill("solid", fgColor="E8E8E8")  # gris claro
    desde += 1
    # --- fin nueva sección ---

    encabezado = (
        "Rubro",
        f"Saldo al {_f(d['fecha_fin'])}",
        f"Actualizado al {_f(d['proxima_fecha_cierre'])}",
    )

    def pintar_tabla(titulo: str, filas: list[dict], desde: int) -> int:
        ws.cell(desde, 1, titulo).font = negrita
        desde += 1
        for col, texto in enumerate(encabezado, start=1):
            celda = ws.cell(desde, col, texto)
            celda.font = negrita
            celda.alignment = Alignment(horizontal="right" if col > 1 else "left")
        desde += 1
        for f_ in filas:
            if f_["tipo"] == "titulo":
                ws.cell(desde, 1, f_["etiqueta"]).font = negrita
            else:
                destacada = f_["tipo"] in ("total", "calc")
                celda = ws.cell(desde, 1, f_["etiqueta"])
                if destacada:
                    celda.font = negrita
                ws.cell(desde, 2, float(f_["actual"]))
                ws.cell(desde, 3, float(f_["actualizado"]))
            desde += 1
        return desde + 1

    fila = 8
    fila = pintar_tabla("ESTADO DE SITUACIÓN PATRIMONIAL — ACTIVO", d["esp"]["activo"], fila)
    fila = pintar_tabla("ESTADO DE SITUACIÓN PATRIMONIAL — PASIVO", d["esp"]["pasivo"], fila)
    fila = pintar_tabla("ESTADO DE RESULTADOS", d["er"], fila)

    ws.column_dimensions["A"].width = 78
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 26

    salida = BytesIO()
    wb.save(salida)
    nombre = f"moneda-homogenea-{_slug(d['ejercicio'])}-{_slug(d['cliente'])}.xlsx"
    return nombre, salida.getvalue()
