"""Envío de facturas por mail al cliente, con el PDF adjunto.

Nunca corta el proceso: si el mail no sale se devuelve el motivo para que la
pantalla lo muestre, pero las facturas ya guardadas se quedan igual.
"""

import smtplib
from datetime import datetime
from email.message import EmailMessage

from app.config import settings
from app.models.factura import Factura
from app.schemas.factura import ETIQUETAS_CONDICION, ETIQUETAS_TIPO
from app.services import factura_service
from app.services.formato import pesos


def enviar_factura(db, factura) -> str | None:
    """Manda UNA factura con el comprobante en PDF adjunto.

    Devuelve el motivo por el que NO se mandó, o None si salió bien.
    """
    if not settings.smtp_user or not settings.smtp_password:
        return "Falta completar SMTP_USER y SMTP_PASSWORD en el .env"

    cliente = factura.cliente
    destino = (cliente.email or "").strip() if cliente else ""
    if not destino:
        return f"{factura.cliente_nombre} no tiene email cargado"

    try:
        tipo = ETIQUETAS_TIPO[factura.tipo_comprobante]
        cuerpo = [
            f"Le hacemos llegar la {tipo} N° {factura.numero} del "
            f"{factura.fecha.strftime('%d/%m/%Y')} "
            f"por $ {pesos(float(factura.importe))}.",
            "",
            f"Cliente: {factura.cliente_nombre}",
        ]
        if factura.concepto:
            cuerpo.append(f"Concepto: {factura.concepto}")
        if factura.fecha_vencimiento:
            cuerpo.append(
                f"Vencimiento: {factura.fecha_vencimiento.strftime('%d/%m/%Y')}"
            )
        cuerpo += [
            f"Condición: {ETIQUETAS_CONDICION[factura.condicion_venta]}",
            "",
            "Quedamos a su disposición.",
            settings.nombre_estudio,
        ]

        mensaje = EmailMessage()
        mensaje["Subject"] = (
            f"{settings.nombre_estudio} - {tipo} "
            f"{factura.punto_venta}-{factura.numero}"
        )
        mensaje["From"] = settings.smtp_user
        mensaje["To"] = destino
        mensaje.set_content("\n".join(cuerpo))
        mensaje.add_attachment(
            factura_service.pdf(db, factura.id),
            maintype="application",
            subtype="pdf",
            filename="comprobante.pdf",
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as servidor:
            servidor.starttls()
            servidor.login(settings.smtp_user, settings.smtp_password)
            servidor.send_message(mensaje)
    except Exception as exc:  # noqa: BLE001 — una falla de mail no puede frenar nada
        return f"No se pudo enviar: {exc}"

    return None


def enviar_varias(db, ids: list[int]) -> tuple[int, list[str]]:
    """Manda varias facturas de una. Devuelve (las que salieron, los motivos
    por los que alguna no salió).

    Cada éxito anota fecha_envio, que es lo que la pantalla muestra en verde.
    """
    enviadas = 0
    avisos: list[str] = []

    for factura_id in ids:
        factura = db.get(Factura, factura_id)
        if factura is None:
            avisos.append(f"La factura n° {factura_id} no existe")
            continue

        motivo = enviar_factura(db, factura)
        if motivo:
            avisos.append(
                f"{ETIQUETAS_TIPO[factura.tipo_comprobante]} "
                f"{factura.punto_venta}-{factura.numero}: {motivo}"
            )
            continue

        factura.fecha_envio = datetime.utcnow()
        db.commit()
        enviadas += 1

    return enviadas, avisos
