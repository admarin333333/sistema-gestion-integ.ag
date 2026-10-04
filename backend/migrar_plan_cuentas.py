"""Crea la tabla `plan_cuentas` y carga el plan de cuentas RT54 del Excel.

Fuente: Hoja2 de "plan de cuentas.xlsx" (la que dice
"PLAN DE CUENTAS - ESTRUCTURA RT 54"). La Hoja1 es un borrador viejo con
otros códigos y no se usa.

Estructura: UNA sola tabla jerárquica. No hay tablas separadas para rubros,
subrubros y cuentas: el nivel se deduce de cuántas partes tiene el código
(1 = "1 ACTIVO", 2 = "1.1 ACTIVO CORRIENTE", 3 = "1.1.01 Caja y bancos"...)
y el vínculo con el padre es `cuenta_padre_id`.

Decisiones tomadas por el usuario el 02/10/2026:
- Se carga solo Hoja2.
- Las 29 cuentas que venían sin código se numeran en orden bajo su grupo.
- `tipo_auxiliar` va en las cuentas **imputables**, no en los grupos.
- Si una cuenta no dice si es imputable, se marca imputable SI no tiene
  subcuentas colgando.

El script es idempotente: se puede volver a correr las veces que quieras sin
duplicar nada (el código es único y se usa INSERT ... ON DUPLICATE KEY UPDATE).

Uso:
    python -X utf8 migrar_plan_cuentas.py --ver     <- solo muestra, NO escribe
    python -X utf8 migrar_plan_cuentas.py           <- crea y carga
"""

import argparse
import re

import openpyxl
from sqlalchemy import text

from app.database import engine

ARCHIVO_EXCEL = r"C:\estudio contable\plan de cuentas.xlsx"
HOJA = "Hoja2"

SQL_TABLA = """
CREATE TABLE IF NOT EXISTS plan_cuentas (
    id_cuenta        INT AUTO_INCREMENT PRIMARY KEY,
    codigo           VARCHAR(20)  NOT NULL UNIQUE,
    nombre           VARCHAR(150) NOT NULL,
    cuenta_padre_id  INT          NULL,
    nivel            INT          NOT NULL DEFAULT 1,
    naturaleza       VARCHAR(10)  NOT NULL DEFAULT 'BALANCE',
    deudora_acreadora VARCHAR(12)  NULL,
    imputable        BOOLEAN      NOT NULL DEFAULT FALSE,
    tipo_auxiliar    VARCHAR(30)  NULL,
    activa           BOOLEAN      NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_plan_cuentas_padre
        FOREIGN KEY (cuenta_padre_id) REFERENCES plan_cuentas(id_cuenta)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    INDEX ix_plan_cuentas_padre     (cuenta_padre_id),
    INDEX ix_plan_cuentas_codigo    (codigo),
    INDEX ix_plan_cuentas_imputable (imputable)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# "1.1.01 Caja y bancos" -> ("1.1.01", "Caja y bancos")
RE_CODIGO_EN_NOMBRE = re.compile(r"^(\d+(?:[.,]\d+)*)[.\s]+(.+)$")

# Texto que NO es una cuenta sino un separador o encabezado del Excel.
NO_ES_CUENTA = {"ctas contables", "plan de cuentas — estructura rt 54"}


def _texto(v):
    return "" if v is None else str(v).strip()


def leer_excel(ruta=ARCHIVO_EXCEL):
    """Devuelve las cuentas en el orden del Excel, con el código ya normalizado.

    Cada cuenta es un dict: codigo, nombre, imputable_del_excel, padre, nivel.

    Las cuentas que vienen sin código se cuelgan de la cuenta **inmediatamente
    anterior** en la hoja (que es siempre el grupo al que pertenecen), y se
    numeran correlativas: "Proveedores" va debajo de "2.1.01 Deudas comerciales"
    y se convierte en 2.1.01.01.
    """
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hoja = wb[HOJA]

    cuentas = []
    anterior = None      # código de la última cuenta leída
    siguiente = {}       # {"2.1.01": 0, ...} para numerar las huérfanas

    for fila in hoja.iter_rows(values_only=True):
        codigo_crudo = _texto(fila[0] if len(fila) > 0 else None)
        nombre_crudo = _texto(fila[1] if len(fila) > 1 else None)
        imputable_txt = _texto(fila[2] if len(fila) > 2 else None).lower()

        if not nombre_crudo and not codigo_crudo:
            continue

        # El código puede venir en su columna o embebido en el nombre.
        codigo = codigo_crudo.replace(",", ".")
        nombre = nombre_crudo
        m = RE_CODIGO_EN_NOMBRE.match(nombre_crudo)
        if m:
            codigo = m.group(1).replace(",", ".")
            nombre = m.group(2).strip()

        nombre = nombre.strip()
        bajo = nombre.lower()
        if not nombre or bajo in NO_ES_CUENTA:
            continue

        # Fila de encabezado de columnas del Excel ("codigo | ... | imputable").
        if codigo.lower() == "codigo" or bajo.startswith("las cuentas integradores"):
            continue

        # --- código ausente: se cuelga de la cuenta anterior ---
        sin_codigo = False
        if not codigo:
            sin_codigo = True
            if anterior is None:
                raise SystemExit(
                    f"'{nombre}' no tiene código y no hay una cuenta anterior "
                    "de la cual colgarla"
                )
            siguiente[anterior] = siguiente.get(anterior, 0) + 1
            codigo = f"{anterior}.{siguiente[anterior]:02d}"
        else:
            # Solo una cuenta que trae código del Excel pasa a ser el grupo
            # al que se cuelgan las siguientes huérfanas. Si no, cada huérfana
            # se colgaría de la huérfana anterior y el código se alarga sin fin.
            anterior = codigo

        nivel = len(codigo.split("."))
        padre = codigo.rsplit(".", 1)[0] if nivel > 1 else None

        cuentas.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "imputable_excel": imputable_txt in ("si", "sí", "s"),
                "tiene_marca_imputable": imputable_txt in ("si", "sí", "s", "no"),
                "nivel": nivel,
                "padre": padre,
                "sin_codigo": sin_codigo,
            }
        )

    return cuentas


def completar(cuentas):
    """Calcula `imputable`, `tipo_auxiliar`, `naturaleza` y `deudora_acreadora`.

    - imputable: el Excel manda si lo dice. Si no lo dice, es imputable SI no
      tiene ninguna subcuenta colgando.
    - tipo_auxiliar: solo en las cuentas imputables.
    - naturaleza: sale del grupo de nivel 1 (1-3 = BALANCE, 4-7 = RESULTADO).
    - deudora_acreadora: solo en las imputables. Activo/Costos/Gastos =
      DEUDORA; Pasivo/PN/Ingresos = ACREEDORA. En el grupo 7 (resultados
      financieros) sale del nombre: "ganados"/"positivas" son acreedoras y
      "perdidos"/"negativas" deudoras.
    """
    codigos = {c["codigo"] for c in cuentas}
    # Mapa código -> cuenta, para poder mirar el nombre del grupo.
    por_codigo = {c["codigo"]: c for c in cuentas}

    for c in cuentas:
        # ¿Alguien cuelga de esta cuenta?
        prefijo = c["codigo"] + "."
        tiene_hijos = any(otro.startswith(prefijo) for otro in codigos)

        if c["tiene_marca_imputable"]:
            # El Excel dice imputable=SÍ, pero si tiene subcuentas es un grupo.
            c["imputable"] = c["imputable_excel"] and not tiene_hijos
        else:
            # No dice nada: si no tiene hijos, es una cuenta para asentar.
            c["imputable"] = not tiene_hijos

        c["tiene_hijos"] = tiene_hijos
        c["tipo_auxiliar"] = (
            tipo_auxiliar_de(c, por_codigo) if c["imputable"] else None
        )

        grupo = c["codigo"].split(".")[0]
        c["naturaleza"] = "BALANCE" if grupo in ("1", "2", "3") else "RESULTADO"
        c["deudora_acreadora"] = (
            deudora_de(c, grupo) if c["imputable"] else None
        )

    return cuentas


def deudora_de(cuenta, grupo: str) -> str:
    """DEUDORA (suma en el Debe) o ACREEDORA (suma en el Haber)."""
    # El grupo 7 (resultados financieros) viene mezclado: se decide por el
    # nombre de la cuenta.
    if grupo == "7":
        nombre = cuenta["nombre"].lower()
        if "ganado" in nombre or "positiv" in nombre:
            return "ACREEDORA"
        return "DEUDORA"

    # Activo, costos y gastos suman en el Debe; pasivo, patrimonio neto e
    # ingresos suman en el Haber.
    if grupo in ("1", "5", "6"):
        return "DEUDORA"
    return "ACREEDORA"


def tipo_auxiliar_de(cuenta, por_codigo):
    """Devuelve CLIENTE / PROVEEDOR / BANCO / NINGUNO.

    Se decide mirando el nombre del grupo (el padre) y el de la cuenta, para
    no depender de una lista de nombres written a mano.
    """
    nombre = cuenta["nombre"].lower()
    padre = cuenta["padre"]
    nombre_padre = por_codigo[padre]["nombre"].lower() if padre in por_codigo else ""
    nombre_abuelo = ""
    if padre:
        abuelo = padre.rsplit(".", 1)[0]
        if abuelo in por_codigo:
            nombre_abuelo = por_codigo[abuelo]["nombre"].lower()

    # --- CLIENTE: lo que está bajo "Cuentas por cobrar a clientes" ---
    if "por cobrar a clientes" in nombre_padre or "por cobrar a clientes" in nombre_abuelo:
        return "CLIENTE"

    # --- PROVEEDOR ---
    if nombre.startswith("anticipos a proveedores"):
        return "PROVEEDOR"
    if "deudas comerciales" in nombre_padre and nombre.startswith("proveedores"):
        return "PROVEEDOR"

    # --- BANCO: las cuentas bancarias que cuelgan de "Caja y bancos" ---
    # Ojo con el plural: el Excel dice "Otras cuentas bancarias" y "Fondos en
    # plataformas de cobro", así que se buscan los fragmentos en singular.
    if "caja y bancos" in nombre_padre or "caja y bancos" in nombre_abuelo:
        if (
            nombre.startswith("banco")
            or "cuenta bancaria" in nombre
            or "cuentas bancarias" in nombre
            or "billetera" in nombre
            or "plataforma de cobro" in nombre
            or "plataformas de cobro" in nombre
            or "valores a depositar" in nombre
        ):
            return "BANCO"

    return "NINGUNO"


def resumen(cuentas):
    return {
        "total": len(cuentas),
        "imputables": sum(1 for c in cuentas if c["imputable"]),
        "grupos": sum(1 for c in cuentas if c["tiene_hijos"]),
        "sin_codigo": [c for c in cuentas if c["sin_codigo"]],
        "por_ta": {},
        "por_nivel": {},
    }


def mostrar(cuentas):
    print("=" * 78)
    print("LO QUE SE VA A CARGAR (nada se escribió todavía)")
    print("=" * 78)

    from collections import Counter

    ta = Counter(c["tipo_auxiliar"] for c in cuentas if c["tipo_auxiliar"])
    niveles = Counter(c["nivel"] for c in cuentas)

    print(f"\nTotal de cuentas: {len(cuentas)}")
    print(f"  Grupos (imputable = FALSO): {sum(1 for c in cuentas if c['tiene_hijos'])}")
    print(f"  Cuentas imputables: {sum(1 for c in cuentas if c['imputable'])}")
    print("  Por nivel: " + ", ".join(f"{k}={v}" for k, v in sorted(niveles.items())))
    print("  tipo_auxiliar: " + ", ".join(f"{k}={v}" for k, v in sorted(ta.items())))

    print("\n--- Los 29 códigos que se completan (no venían en el Excel) ---")
    for c in cuentas:
        if c["sin_codigo"]:
            print(f"  {c['codigo']:<16} {c['nombre']}")

    print("\n--- Cuentas con tipo_auxiliar distinto de NINGUNO ---")
    for c in cuentas:
        if c["tipo_auxiliar"] and c["tipo_auxiliar"] != "NINGUNO":
            print(f"  {c['codigo']:<16} {c['nombre']:<45} {c['tipo_auxiliar']}")

    print("\n--- Los 7 grupos de nivel 1 ---")
    for c in cuentas:
        if c["nivel"] == 1:
            imp = "imputable" if c["imputable"] else "grupo"
            print(f"  {c['codigo']:<6} {c['nombre']:<40} {imp}")

    print("\n--- Chequeo de integrity ---")
    problemas = []
    codigos_vistos = set()
    for c in cuentas:
        if c["codigo"] in codigos_vistos:
            problemas.append(f"código repetido: {c['codigo']}")
        codigos_vistos.add(c["codigo"])
        if c["padre"] and c["padre"] not in codigos_vistos:
            problemas.append(
                f"{c['codigo']} apunta a un padre inexistente: {c['padre']}"
            )
    largos = [c for c in cuentas if len(c["codigo"]) > 20]
    for c in largos:
        problemas.append(f"código muy largo para VARCHAR(20): {c['codigo']}")
    largos_nombre = [c for c in cuentas if len(c["nombre"]) > 150]
    for c in largos_nombre:
        problemas.append(f"nombre muy largo para VARCHAR(150): {c['nombre'][:40]}...")

    if problemas:
        for p in problemas:
            print("  PROBLEMA:", p)
    else:
        print("  Todo bien: no hay códigos repetidos, todos los padres existen,")
        print("  y ningún texto excede el tamaño de la columna.")

    print(f"\nNivel máximo: {max(c['nivel'] for c in cuentas)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ver",
        action="store_true",
        help="Solo muestra qué se va a cargar. No escribe nada.",
    )
    ap.add_argument("--excel", default=ARCHIVO_EXCEL, help="Ruta alterna del Excel")
    args = ap.parse_args()

    cuentas = completar(leer_excel(args.excel))

    if args.ver:
        mostrar(cuentas)
        return

    with engine.begin() as conn:
        conn.execute(text(SQL_TABLA))
        print("Tabla plan_cuentas lista")

        # Primero los padres, después las hijas: el orden del Excel ya viene
        # bien, pero por las dudas se ordena por nivel.
        ordenadas = sorted(cuentas, key=lambda c: (c["nivel"], c["codigo"]))

        # Mapa para resolver el id del padre a partir de su código.
        id_por_codigo: dict[str, int] = {}
        for r in conn.execute(text("SELECT codigo, id_cuenta FROM plan_cuentas")):
            id_por_codigo[r[0]] = r[1]

        # Nivel 1 primero (no tienen padre), y de ahí para abajo.
        #
        # El último nivel sale de los DATOS, no de un número fijo. Estaba escrito
        # `range(1, 5)` y eso descartaba en silencio toda cuenta de nivel 5 o
        # más: el script terminaba "con éxito" cargando 180 de las 185 cuentas
        # del Excel, sin decir nada. Cinco cuentas se perdían y la única forma de
        # enterarse era comparar los totales a mano.
        #
        # Por eso, además, hay un control antes: si queda alguna cuenta fuera del
        # rango, se frena y se las nombra. Perder datos en silencio es peor que
        # frenar.
        nivel_maximo = max(c["nivel"] for c in cuentas)
        fuera = [c for c in cuentas if not 1 <= c["nivel"] <= nivel_maximo]
        if fuera:
            raise SystemExit(
                "Hay cuentas con un nivel que no puedo insertar: "
                + ", ".join(f"{c['codigo']} (nivel {c['nivel']})" for c in fuera)
            )

        print(f"  Cargando niveles 1 a {nivel_maximo}")

        for nivel in range(1, nivel_maximo + 1):
            for c in [x for x in ordenadas if x["nivel"] == nivel]:
                padre_id = None
                if c["padre"]:
                    padre_id = id_por_codigo.get(c["padre"])
                    if padre_id is None:
                        raise SystemExit(
                            f"No encuentro el padre '{c['padre']}' de {c['codigo']}"
                        )
                conn.execute(
                    text(
                        """
                        INSERT INTO plan_cuentas
                            (codigo, nombre, cuenta_padre_id, nivel,
                             naturaleza, deudora_acreadora,
                             imputable, tipo_auxiliar, activa)
                        VALUES
                            (:codigo, :nombre, :padre_id, :nivel,
                             :naturaleza, :deudora_acreadora,
                             :imputable, :tipo_auxiliar, 1)
                        ON DUPLICATE KEY UPDATE
                            nombre             = VALUES(nombre),
                            cuenta_padre_id    = VALUES(cuenta_padre_id),
                            nivel              = VALUES(nivel),
                            naturaleza         = VALUES(naturaleza),
                            deudora_acreadora  = VALUES(deudora_acreadora),
                            imputable          = VALUES(imputable),
                            tipo_auxiliar      = VALUES(tipo_auxiliar)
                        """
                    ),
                    {
                        "codigo": c["codigo"],
                        "nombre": c["nombre"],
                        "padre_id": padre_id,
                        "nivel": c["nivel"],
                        "naturaleza": c["naturaleza"],
                        "deudora_acreadora": c["deudora_acreadora"],
                        "imputable": 1 if c["imputable"] else 0,
                        "tipo_auxiliar": c["tipo_auxiliar"],
                    },
                )
                # El id del insert: se recupera por el código, que es único.
                nuevo = conn.execute(
                    text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"),
                    {"c": c["codigo"]},
                ).scalar()
                id_por_codigo[c["codigo"]] = nuevo

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM plan_cuentas")).scalar()
        imp = conn.execute(
            text("SELECT COUNT(*) FROM plan_cuentas WHERE imputable = 1")
        ).scalar()
        print(f"\nCargadas {total} cuentas ({imp} imputables)")


if __name__ == "__main__":
    main()