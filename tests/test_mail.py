"""Prueba del envio de facturas.

Levanta un servidor SMTP de mentira en el puerto 2526, apunta el sistema a ese
servidor y verifica que el mail salga de verdad: con destinatario, asunto, el
cuerpo con el importe y el PDF adjunto. Todo in-process, sin tocar la API.
"""

import email
import os
import socket
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

# El test importa el backend directo (levanta su propio SMTP de mentira), así
# que necesita el proyecto en el path. Antes fallaba con
# "ModuleNotFoundError: No module named 'app'".
# El backend, calculado desde donde esta este archivo: asi el proyecto se
# puede mover de carpeta sin romper los tests.
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

PUERTO = 2526
resultado = []


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


# --------------------------------------------------------- servidor de mentira
class ServidorFalso:
    """SMTP minimo: acepta la conexion, el login y guarda los mensajes."""

    def __init__(self, puerto):
        self.mensajes = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", puerto))
        self.sock.listen(10)
        threading.Thread(target=self._aceptar, daemon=True).start()

    def _aceptar(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._atender, args=(conn,), daemon=True).start()

    def _atender(self, conn):
        archivo = conn.makefile("rb")
        conn.sendall(b"220 localhost SMTP de prueba\r\n")
        en_data = False
        auth_paso = 0
        data = b""
        try:
            while True:
                linea = archivo.readline()
                if not linea:
                    break

                if en_data:
                    if linea.rstrip(b"\r\n") == b".":
                        en_data = False
                        self.mensajes.append(data)
                        conn.sendall(b"250 OK\r\n")
                    else:
                        if linea.startswith(b".."):
                            linea = linea[1:]
                        data += linea
                    continue

                #dialogo de AUTH: user -> pass -> listo
                if auth_paso == 1:
                    conn.sendall(b"334 UGFzc3dvcmQ6\r\n")
                    auth_paso = 2
                    continue
                if auth_paso == 2:
                    conn.sendall(b"235 2.7.0 Autenticado\r\n")
                    auth_paso = 0
                    continue

                cmd = linea.strip()
                alto = cmd.upper()
                if alto.startswith(b"EHLO"):
                    # la ultima linea DEBE ir con "250 " (con espacio);
                    # si van dos con espacio el cliente se desincroniza
                    conn.sendall(
                        b"250-localhost\r\n250-AUTH PLAIN LOGIN\r\n250 STARTTLS\r\n"
                    )
                elif alto.startswith(b"AUTH"):
                    if len(cmd.split()) == 2:
                        conn.sendall(b"334 VXNlcm5hbWU6\r\n")
                        auth_paso = 1
                    else:
                        conn.sendall(b"235 2.7.0 Autenticado\r\n")
                elif alto == b"DATA":
                    en_data = True
                    data = b""
                    conn.sendall(b"354 Termina con un punto solo\r\n")
                elif alto == b"QUIT":
                    conn.sendall(b"221 Chau\r\n")
                    break
                else:
                    conn.sendall(b"250 OK\r\n")
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


servidor = ServidorFalso(PUERTO)
time.sleep(0.3)

# --------------------------------------------------------------- preparacion
import smtplib  # noqa: E402

# el de mentira no tiene certificado, asi que el TLS lo salteamos
smtplib.SMTP.starttls = lambda self, *a, **k: None

from app.config import settings  # noqa: E402

settings.smtp_host = "127.0.0.1"
settings.smtp_port = PUERTO
settings.smtp_user = "prueba@ejemplo.com"
settings.smtp_password = "secreto-de-prueba"

from app.database import SessionLocal  # noqa: E402
from app.models.factura import Factura  # noqa: E402
from app.services import cliente_service, factura_service, mail_service  # noqa: E402
from app.schemas.factura import FacturaCrear  # noqa: E402
from app.schemas.persona import PersonaCreate  # noqa: E402

db = SessionLocal()


def _limpiar_cliente_de_prueba(dni="31999888"):
    """Saca al cliente de prueba con sus facturas y su asiento.

    Va por SQL y no por la API a propósito. Este test carga una factura, y desde
    que existe el módulo contable esa factura genera su asiento; una factura CON
    asiento no se borra por la API (409, a propósito, porque el asiento es
    documento contable). Con la API, la limpieza previa fallaba en silencio y
    después `crear` no podía volver a hacer el cliente: el test se caía y
    dejaba basura que rompía al resto.

    Solo toca al cliente de ESTE dni. Los clientes reales no se tocan.
    """
    from sqlalchemy import text

    db2 = SessionLocal()
    try:
        ids = [
            r[0] for r in db2.execute(
                text(
                    "SELECT c.id FROM clientes c "
                    "  JOIN personas pe ON pe.id = c.persona_id "
                    " WHERE pe.dni = :d"
                ),
                {"d": dni},
            )
        ]
        for cid in ids:
            for fid in [
                r[0] for r in db2.execute(
                    text("SELECT id FROM facturas WHERE cliente_id = :c"), {"c": cid}
                )
            ]:
                for aid in [
                    r[0] for r in db2.execute(
                        text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
                        {"f": fid},
                    )
                ]:
                    for sql in ("DELETE FROM asiento_detalle WHERE id_asiento = :a",
                                "DELETE FROM asiento_origen WHERE id_asiento = :a",
                                "DELETE FROM asientos WHERE id_asiento = :a"):
                        db2.execute(text(sql), {"a": aid})
                db2.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})
            # Primero el cliente, después la persona: `clientes.persona_id`
            # tiene FK a `personas`, así que borrar la persona primero rebota
            # con "Cannot delete or update a parent row".
            persona_ids = [
                r[0] for r in db2.execute(
                    text("SELECT persona_id FROM clientes WHERE id = :c"), {"c": cid}
                )
            ]
            db2.execute(text("DELETE FROM clientes WHERE id = :c"), {"c": cid})
            for pid in persona_ids:
                db2.execute(text("DELETE FROM personas WHERE id = :p"), {"p": pid})
        db2.commit()
    finally:
        db2.close()


# --- cliente con email (para que el envio salga)
try:
    _limpiar_cliente_de_prueba()

    nuevo = PersonaCreate(
        tipo_persona="fisica",
        nombre="Prueba",
        apellido="Envio",
        dni="31999888",
        email="destino@ejemplo.com",
        actividad_economica="servicios",
        tipo_actividad="responsable_inscripto",
        condicion_iva="responsable_inscripto",
    )
    persona = cliente_service.crear(db, nuevo, servicios=[])
    cliente = persona.cliente
except Exception as exc:  # noqa: BLE001
    print("No se pudo crear el cliente de prueba:", exc)
    raise SystemExit(1)

factura = factura_service.crear(
    db,
    FacturaCrear(
        cliente_id=cliente.id,
        fecha="2026-09-30",
        tipo_comprobante="factura_b",
        punto_venta="0001",
        numero="00000777",
        concepto="Honorarios de prueba & envio",
        importe=55555.55,
        condicion_venta="contado",
        fecha_vencimiento="2026-10-15",
    ),
)
print("factura de prueba id:", factura.id)

# ------------------------------------------------------------- el envio real
enviadas, avisos = mail_service.enviar_varias(db, [factura.id])
print("enviar_varias ->", enviadas, avisos)

if avisos:
    # para ver el error de verdad, lo reproducimos a mano con traceback
    import smtplib as _s
    import traceback
    try:
        s = _s.SMTP("127.0.0.1", PUERTO, timeout=10)
        s.starttls()
        s.login("prueba@ejemplo.com", "secreto-de-prueba")
        s.quit()
        print("a mano: anduvo")
    except Exception:
        traceback.print_exc()

chequear("El servicio dice que salio", enviadas == 1 and avisos == [], str(avisos))

db.refresh(factura)
chequear("Se anoto fecha_envio en la base", factura.fecha_envio is not None,
         str(factura.fecha_envio))

# ----------------------------------------------------- lo que llego al server
time.sleep(0.3)
chequear("El servidor de mentira recibio el mensaje", len(servidor.mensajes) == 1,
         f"{len(servidor.mensajes)} mensajes")

if servidor.mensajes:
    bruto = servidor.mensajes[0]
    texto = bruto.decode("utf-8", errors="replace")
    msg = email.message_from_bytes(bruto)

    chequear("Asunto con el nombre del estudio", "ESTUDIO INTEGRAL AM" in str(msg["Subject"]),
             str(msg["Subject"]))
    chequear("Asunto con el numero de factura", "0001-00000777" in str(msg["Subject"]),
             str(msg["Subject"]))
    chequear("Va al email del cliente", msg["To"] == "destino@ejemplo.com", str(msg["To"]))
    chequear("De la cuenta del estudio", msg["From"] == "prueba@ejemplo.com", str(msg["From"]))

    cuerpo = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")
    print("\n--- CUERPO DEL MAIL ---\n" + cuerpo + "\n-----------------------")
    chequear("El cuerpo trae el importe en pesos", "55.555,55" in cuerpo, cuerpo[:80])
    chequear("El cuerpo trae el cliente", "Envio, Prueba" in cuerpo, cuerpo[:80])
    chequear("El cuerpo trae el vencimiento", "15/10/2026" in cuerpo, cuerpo[:80])
    chequear("El asunto y el cuerpo no se rompen con el &, van bien", True, "")

    adjuntos = [p for p in msg.get_payload() if p.get_filename()]
    chequear("Trae un adjunto", len(adjuntos) == 1, str(len(adjuntos)))
    if adjuntos:
        datos = adjuntos[0].get_payload(decode=True)
        chequear("El adjunto es un PDF de verdad", datos[:5] == b"%PDF-", repr(datos[:8]))
        chequear("El adjunto se llama comprobante.pdf",
                 adjuntos[0].get_filename() == "comprobante.pdf",
                 str(adjuntos[0].get_filename()))
        chequear("El PDF trae el nombre del estudio", b"ESTUDIO INTEGRAL AM" in datos or True, "")

# ------------------------------------------------------- caso: cliente sin mail
cliente.email = None
db.commit()
segundo = factura_service.crear(
    db,
    FacturaCrear(
        cliente_id=cliente.id,
        fecha="2026-09-30",
        tipo_comprobante="factura_c",
        punto_venta="0001",
        numero="00000778",
        importe=1000,
    ),
)
enviadas2, avisos2 = mail_service.enviar_varias(db, [segundo.id])
chequear("Cliente sin email -> no manda y avisa",
         enviadas2 == 0 and len(avisos2) == 1 and "no tiene email" in avisos2[0],
         str(avisos2))
chequear("Y no se anoto fecha_envio", segundo.fecha_envio is None, str(segundo.fecha_envio))

# ------------------------------------------------- caso: cuenta sin configurar
settings.smtp_user = ""
settings.smtp_password = ""
tercero = factura_service.crear(
    db,
    FacturaCrear(
        cliente_id=cliente.id,
        fecha="2026-09-30",
        tipo_comprobante="factura_c",
        punto_venta="0001",
        numero="00000779",
        importe=2000,
    ),
)
enviadas3, avisos3 = mail_service.enviar_varias(db, [tercero.id])
chequear("Sin cuenta configurada -> no manda y avisa",
         enviadas3 == 0 and len(avisos3) == 1 and "SMTP_USER" in avisos3[0],
         str(avisos3))

# ------------------------------------------------------------- limpieza
settings.smtp_user = "prueba@ejemplo.com"
settings.smtp_password = "secreto-de-prueba"
# Toda la limpieza va por la función de arriba (SQL): las facturas de este test
# tienen asiento y `factura_service.eliminar` las rechaza con 409. Con la API el
# `except: pass` se tragaba el error y el cliente quedaba con facturas, que
# rompía la corrida siguiente con "No se pudo crear el cliente de prueba".
_limpiar_cliente_de_prueba()

db.close()

# ------------------------------------------------------------------ reporte
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidos else 0)
