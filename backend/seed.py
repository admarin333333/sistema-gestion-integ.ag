"""Crea las tablas y los datos iniciales si no existen.

Ejecutar desde la carpeta backend/:

    python seed.py
"""

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models.anticipo import Anticipo, AplicacionAnticipo
from app.models.cliente import Cliente
from app.models.factura import Factura
from app.models.localidad import Localidad
from app.models.recibo import Aplicacion, Recibo
from app.models.servicio import ClienteServicio, Servicio
from app.models.sugerencia import Sugerencia
from app.models.usuario import Usuario

USUARIOS_INICIALES = [
    {
        "usuario": "admin",
        "nombre": "Administrador",
        "email": "admin@estudio.local",
        "password": "admin123",
        "rol": "admin",
    },
    {
        "usuario": "operador",
        "nombre": "Operador",
        "email": "operador@estudio.local",
        "password": "operador123",
        "rol": "operador",
    },
]

# Catálogo fijo de servicios del estudio.
SERVICIOS = [
    "Impuestos",
    "Contabilidad",
    "Sueldos y cargas sociales",
    "Seguros",
    "Prevención de lavado de activos y financiamiento del terrorismo",
    "Cumplimiento Ley 27.742",
    "Trámite y documentación",
    "Automatización de tareas administrativas",
    "Peritaje",
    "Auditar",
]

# Localidades principales de Córdoba con su código postal.
# Fuentes (consultadas el 30/09/2026):
#   - codigo-postal.co (datos de Correo Argentino)
#   - worldpostalcode.com/argentina/cordoba
#   - Wikipedia (Almafuerte X5854, La Falda X5172, Villa Gral. Belgrano X5194,
#     Laboulaye X6120)
# Si falta alguna, se carga la localidad a mano en el cliente.
LOCALIDADES = [
    ("2400", "San Francisco"),
    ("2417", "Altos de Chipión"),
    ("2419", "Brinkmann"),
    ("2421", "Morteros"),
    ("2424", "Devoto"),
    ("2434", "Arroyito"),
    ("2550", "Bell Ville"),
    ("2553", "Justiniano Posse"),
    ("2557", "Idiázabal"),
    ("2559", "San Antonio de Litín"),
    ("2561", "Chilibroste"),
    ("2563", "Noetinger"),
    ("2580", "Marcos Juárez"),
    ("2587", "Inriville"),
    ("2592", "General Roca"),
    ("2650", "Canals"),
    ("2659", "Monte Maíz"),
    ("2662", "Alejo Ledesma"),
    ("2670", "La Carlota"),
    ("5000", "Córdoba"),
    ("5105", "Villa Allende"),
    ("5109", "Unquillo"),
    ("5111", "Río Ceballos"),
    ("5127", "Río Primero"),
    ("5133", "Santa Rosa de Río Primero"),
    ("5145", "Juárez Celman"),
    ("5151", "La Calera"),
    ("5152", "Villa Carlos Paz"),
    ("5158", "Bialet Massé"),
    ("5164", "Santa María de Punilla"),
    ("5166", "Cosquín"),
    ("5172", "La Falda"),
    ("5174", "Huerta Grande"),
    ("5176", "Villa Giardino"),
    ("5178", "La Cumbre"),
    ("5184", "Capilla del Monte"),
    ("5186", "Alta Gracia"),
    ("5189", "Anisacate"),
    ("5194", "Villa General Belgrano"),
    ("5200", "Deán Funes"),
    ("5214", "Quilino"),
    ("5220", "Jesús María"),
    ("5223", "Colonia Caroya"),
    ("5231", "Sebastián Elcano"),
    ("5270", "Serrezuela"),
    ("5280", "Cruz del Eje"),
    ("5284", "Villa de Soto"),
    ("5291", "San Carlos Minas"),
    ("5295", "Salsacate"),
    ("5800", "Río Cuarto"),
    ("5815", "Elena"),
    ("5817", "Berrotarán"),
    ("5833", "Achiras"),
    ("5837", "Chaján"),
    ("5843", "Adelia María"),
    ("5847", "Coronel Moldes"),
    ("5850", "Río Tercero"),
    ("5854", "Almafuerte"),
    ("5856", "Embalse"),
    ("5870", "Villa Dolores"),
    ("5875", "San Javier"),
    ("5889", "Mina Clavero"),
    ("5891", "Villa Cura Brochero"),
    ("5900", "Villa María"),
    ("5911", "La Playosa"),
    ("5921", "Las Perdices"),
    ("5923", "General Deheza"),
    ("5929", "Hernando"),
    ("5933", "Tancacha"),
    ("5945", "Sacanta"),
    ("5960", "Río Segundo"),
    ("5965", "Las Junturas"),
    ("5972", "Pilar"),
    ("5974", "Laguna Larga"),
    ("5980", "Oliva"),
    ("5984", "James Craik"),
    ("5986", "Oncativo"),
    ("5988", "Manfredi"),
    ("6120", "Laboulaye"),
    ("6140", "Vicuña Mackenna"),
    ("6270", "Huinca Renancó"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for datos in USUARIOS_INICIALES:
            existe = db.query(Usuario).filter(Usuario.usuario == datos["usuario"]).first()
            if existe:
                print(f"  = {datos['usuario']:10} ya existe, lo dejo igual")
                continue
            db.add(
                Usuario(
                    usuario=datos["usuario"],
                    nombre=datos["nombre"],
                    email=datos["email"],
                    password_hash=hash_password(datos["password"]),
                    rol=datos["rol"],
                    activo=True,
                )
            )
            print(f"  + {datos['usuario']:10} creado  (rol: {datos['rol']})")

        for posicion, nombre in enumerate(SERVICIOS, start=1):
            existe = db.query(Servicio).filter(Servicio.nombre == nombre).first()
            if existe:
                continue
            db.add(Servicio(nombre=nombre, orden=posicion))
            print(f"  + servicio    {nombre}")

        for cp, nombre in LOCALIDADES:
            existe = (
                db.query(Localidad).filter(Localidad.codigo_postal == cp).first()
            )
            if existe:
                continue
            db.add(Localidad(codigo_postal=cp, nombre=nombre, provincia="Córdoba"))
            print(f"  + localidad   {cp} {nombre}")

        db.commit()
        print("\nListo. Tablas, usuarios, servicios y localidades creados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
