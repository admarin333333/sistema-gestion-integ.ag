"""Borra los 4 asientos de DEMOSTRACION del informe de centros de costos.

Se crearon a mano para probar la pantalla (luz, personal, publicidad,
intereses). Son gastos inventados: no sirven para nada real y ensucian los
totales del informe.

    python limpiar_demo_centros.py          -> los borra
    python limpiar_demo_centros.py --ver    -> primero muestra cuáles son
"""

import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")

from sqlalchemy import text

from app.database import SessionLocal

CONCEPTO = "Gastos del mes"


def main():
    db = SessionLocal()

    filas = db.execute(
        text(
            "SELECT a.id_asiento, a.fecha, a.estado, a.concepto "
            "FROM asientos a "
            "WHERE a.concepto = :c AND NOT EXISTS ("
            "  SELECT 1 FROM asiento_origen o WHERE o.id_asiento = a.id_asiento"
            ")"
        ),
        {"c": CONCEPTO},
    ).all()

    if not filas:
        print("no hay asientos de demostración")
        db.close()
        return

    print("asientos de demostración que se van a borrar:")
    for f in filas:
        print(f"  {f[0]}  {f[1]}  {f[2]}  {f[3]}")
    print()

    if "--ver" in sys.argv:
        print("nada se borró (estabas mirando). Sacá --ver para borrar de verdad.")
        db.close()
        return

    # El comprobante se borra DESPUÉS del asiento: asientos.id_comprobante es
    # ON DELETE RESTRICT, al revés MySQL se niega.
    marcas = ",".join(str(f[0]) for f in filas)
    comps = [
        f[0]
        for f in db.execute(
            text(
                "SELECT id_comprobante FROM asientos WHERE id_asiento IN ("
                + marcas
                + ")"
            )
        ).all()
    ]
    db.execute(text("DELETE FROM asiento_origen WHERE id_asiento IN (" + marcas + ")"))
    db.execute(
        text("DELETE FROM asiento_detalle WHERE id_asiento IN (" + marcas + ")")
    )
    db.execute(text("DELETE FROM asientos WHERE id_asiento IN (" + marcas + ")"))
    if comps:
        db.execute(
            text(
                "DELETE FROM comprobantes_internos WHERE id_comprobante IN ("
                + ",".join(str(c) for c in comps)
                + ")"
            )
        )
    db.commit()
    print(f"borrados {len(filas)} asientos de demostración")
    db.close()


if __name__ == "__main__":
    main()
