"""Limpia los recibos HUÉRFANOS que dejaron las corridas de prueba viejas.

**El problema que dejó:** entre corridas, recibos de prueba a los que se les
borró el asiento pero NO el recibo. Quedaron en el listado como "recibo en
efectivo" sin ningún movimiento en la cuenta, y el contador los veía como cobros
que nunca entraron a los libros.

Se los reconoce por dos señales, juntas:
  1. tienen pagos (la tabla `recibo_pagos` es nueva: los recibos cargados antes
     del rediseño no tienen), y
  2. **no tienen asiento**, que es lo que un recibo de prueba siempre termina
     teniendo después de que la limpieza le borró el asiento.

Un recibo real sin asentar NO se toca: es un cobro que el contador Todavía no
quiso llevar a los libros, y es un estado legítimo.

Lo que SÍ se borran, en cambio, son los recibos cuyo cliente es de prueba
(los que usan CUIT/DNI de la lista de `limpiar_clientes_prueba.py`), porque esos
clientes no son de nadie.

Uso:  python limpiar_recibos_huerfanos.py [--ver]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

# Los mismos que usa `limpiar_clientes_prueba.py`.
CONCEPTOS_PRUEBA = ("PRUEBA", "RECIBOS, ANA", "RECIBOS, BRUNO")


def _borrar_asiento(db, asiento_id):
    comprobante = db.execute(
        text("SELECT id_comprobante FROM asientos WHERE id_asiento = :a"),
        {"a": asiento_id},
    ).scalar()
    db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": asiento_id})
    db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": asiento_id})
    db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": asiento_id})
    if comprobante:
        db.execute(text("DELETE FROM comprobantes_internos WHERE id_comprobante = :c"),
                   {"c": comprobante})


def _asientos_de(db, valor):
    return [r[0] for r in db.execute(
        text("SELECT id_asiento FROM asiento_origen "
             "WHERE origen = 'RECIBO' AND id_recibo = :v"), {"v": valor},
    ).all()]


def huerfanos(db):
    """Recibos con pagos, sin asiento, de cliente de prueba."""
    return db.execute(
        text(
            """
            SELECT r.id, r.numero, r.fecha, r.importe,
                   CONCAT(p.nombre, ' ', p.apellido) AS cliente
              FROM recibos r
              JOIN clientes cl ON cl.id = r.cliente_id
              JOIN personas p ON p.id = cl.persona_id
             WHERE EXISTS (SELECT 1 FROM recibo_pagos pg WHERE pg.recibo_id = r.id)
               AND NOT EXISTS (SELECT 1 FROM asiento_origen o
                                WHERE o.origen = 'RECIBO' AND o.id_recibo = r.id)
               AND (UPPER(p.nombre) LIKE '%PRUEBA%'
                 OR UPPER(p.nombre) LIKE '%RECI%BO%'
                 OR UPPER(p.apellido) LIKE '%PRUEBA%')
            """
        )
    ).mappings().all()


def main():
    solo_ver = "--ver" in sys.argv
    db = SessionLocal()
    try:
        filas = huerfanos(db)
        print(f"recibos huérfanos de prueba: {len(filas)}")
        for f in filas:
            pagos = db.execute(
                text("SELECT forma_pago, cuenta_id, importe FROM recibo_pagos "
                     "WHERE recibo_id = :r"),
                {"r": f["id"]},
            ).all()
            detalle = ", ".join(f"{p.forma_pago} {p.importe}" for p in pagos)
            print(f"  #{f['id']:<5} {f['numero']} {f['fecha']} "
                  f"{f['importe']:>12}  [{detalle}]")
        if solo_ver:
            print("\n(--ver: no se borró nada)")
            return
        if not filas:
            print("no hay nada que limpiar")
            return

        for f in filas:
            rid = f["id"]
            for aid in _asientos_de(db, rid):
                _borrar_asiento(db, aid)
            db.execute(text("DELETE FROM recibo_pagos WHERE recibo_id = :r"), {"r": rid})
            db.execute(text("DELETE FROM aplicaciones_recibo WHERE recibo_id = :r"),
                       {"r": rid})
            db.execute(text("DELETE FROM recibos WHERE id = :r"), {"r": rid})
        db.commit()
        print(f"\nborrados {len(filas)} recibos huérfanos")
    finally:
        db.close()


if __name__ == "__main__":
    main()