"""Limpia por SQL lo que dejó `test_recibo_pagos.py`.

La API no alcanza: `asiento_origen.id_recibo` es ON DELETE RESTRICT, así que un
recibo que ya tiene asiento no se puede borrar por HTTP (da 409/500) aunque el
asiento esté anulado. Por eso los tests que arman recibos con asiento limpian con
SQL, y SOLO con el concepto de su prueba.

**Ojo con dos cosas que costó aprender:**

1. Los recibos NO tienen columna `concepto` (solo las facturas). La marca de
   prueba va en `recibo_pagos.detalle`, que sí existe: cada pago de estos
   recibos de prueba lleva `detalle = 'PRUEBA RECIBOS'`.
2. Antes se buscaban los recibos armando un JOIN con las facturas. Como la
   limpieza borra las facturas en la misma pasada, en la corrida siguiente el
   JOIN ya no encontraba nada: los recibos quedaban **sin asiento y sin
   factura**, huérfanos. Pasaron veinte recibos colgados en la base y el
   contador los veía como "recibos en efectivo" sin ningún movimiento en la
   cuenta. Por eso ahora se buscan por su propia marca, sin depender de que la
   factura siga existiendo: la limpieza es idempotente.

Orden (de la hoja a la raíz, por FK):
    asiento_detalle -> asiento_origen -> asientos -> comprobantes_internos
    recibo_pagos -> aplicaciones_recibo -> recibos
    notas de crédito -> facturas

Uso:  python limpiar_prueba_recibo_pagos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

CONCEPTO = "PRUEBA RECIBOS"


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


def _asientos_de(db, columna, valor):
    return [r[0] for r in db.execute(
        text(f"SELECT id_asiento FROM asiento_origen WHERE {columna} = :v"),
        {"v": valor},
    ).all()]


def main():
    db = SessionLocal()
    try:
        # Dos caminos, y juntos:
        #   (a) la MARCA en el detalle de los pagos — el camino principal.
        #   (b) estar aplicado a una factura de la prueba — el fallback para los
        #       recibos que dejó una versión del test anterior, que no ponía la
        #       marca. Se lee ANTES de borrar las facturas; si no, no encontraría
        #       nada y volverían a quedar huérfanos.
        por_marca = db.execute(
            text("SELECT DISTINCT recibo_id FROM recibo_pagos WHERE detalle = :c"),
            {"c": CONCEPTO},
        ).scalars().all()
        por_factura = db.execute(
            text(
                "SELECT DISTINCT a.recibo_id FROM aplicaciones_recibo a "
                " JOIN facturas f ON f.id = a.factura_id "
                " WHERE f.concepto = :c"
            ),
            {"c": CONCEPTO},
        ).scalars().all()
        recibos = sorted(set(por_marca) | set(por_factura))

        for rid in recibos:
            for aid in _asientos_de(db, "id_recibo", rid):
                _borrar_asiento(db, aid)
            db.execute(text("DELETE FROM recibo_pagos WHERE recibo_id = :r"), {"r": rid})
            db.execute(text("DELETE FROM aplicaciones_recibo WHERE recibo_id = :r"),
                       {"r": rid})
            db.execute(text("DELETE FROM recibos WHERE id = :r"), {"r": rid})

        # Las facturas se borren DESPUÉS, y también las notas de crédito, que
        # apuntan a la factura (`factura_relacionada_id`).
        for fid in db.execute(
            text("SELECT id FROM facturas WHERE concepto = :c"), {"c": CONCEPTO}
        ).scalars().all():
            for aid in _asientos_de(db, "id_factura", fid):
                _borrar_asiento(db, aid)
            db.execute(text("UPDATE facturas SET factura_relacionada_id = NULL "
                            "WHERE factura_relacionada_id = :f"), {"f": fid})
            db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})

        db.commit()
        print(f"limpiado: {len(recibos)} recibos y "
              f"{db.execute(text('SELECT COUNT(*) FROM facturas'), {}).scalar()} "
              f"facturas de prueba restantes")
    finally:
        db.close()


if __name__ == "__main__":
    main()