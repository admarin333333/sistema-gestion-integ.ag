"""
Migración: separar la tabla `clientes` en `personas` + `clientes` + `proveedores`.

Estrategia:
1. Renombrar tabla vieja `clientes` a `clientes_vieja`
2. Crear tablas nuevas (personas, clientes, proveedores)
3. Migrar datos
4. Verificar
5. Eliminar tabla vieja
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def migrar():
    with engine.begin() as conn:
        # 0. Renombrar tabla vieja si existe (si ya fue renombrada, ignorar)
        try:
            conn.execute(text("ALTER TABLE clientes RENAME TO clientes_vieja"))
            print("Tabla vieja renombrada a clientes_vieja")
        except Exception:
            print("Tabla clientes_vieja ya existe o ya fue renombrada")

        # 1. Crear tabla personas si no existe
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS personas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tipo_persona ENUM('fisica', 'juridica') NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                apellido VARCHAR(100),
                cuit VARCHAR(13),
                dni VARCHAR(10),
                email VARCHAR(120),
                cod_area VARCHAR(5),
                telefono VARCHAR(20),
                calle VARCHAR(30),
                numero_calle VARCHAR(10),
                locality VARCHAR(100),
                codigo_postal VARCHAR(4),
                provincia VARCHAR(100),
                actividad_economica ENUM('profesional', 'comercio', 'industria', 'cabanas', 'inmobiliaria', 'servicios') NOT NULL,
                tipo_actividad ENUM('monotributista', 'responsable_inscripto', 'autonomo', 'cooperativa', 'asociacion_civil') NOT NULL,
                condicion_iva ENUM('consumidor_final', 'monotributista', 'responsable_inscripto') NOT NULL,
                alicuota_iva_id INT,
                observaciones TEXT,
                fecha_cierre_ejercicio DATE,
                presenta_eecc BOOLEAN NOT NULL DEFAULT TRUE,
                fecha_alta DATE NOT NULL,
                creado DATETIME NOT NULL,
                actualizado DATETIME,
                INDEX idx_persona_cuit (cuit),
                INDEX idx_persona_dni (dni),
                UNIQUE KEY uq_persona_cuit (cuit),
                UNIQUE KEY uq_persona_dni (dni),
                FOREIGN KEY (alicuota_iva_id) REFERENCES alicuotas_iva(id)
            )
        """))
        print("Tabla personas creada")

        # 2. Crear tabla clientes si no existe
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                persona_id INT NOT NULL,
                nro_cuenta INT AUTO_INCREMENT,
                UNIQUE KEY uq_cliente_persona (persona_id),
                UNIQUE KEY uq_cliente_nro_cuenta (nro_cuenta),
                FOREIGN KEY (persona_id) REFERENCES personas(id)
            )
        """))
        print("Tabla clientes creada")

        # 3. Crear tabla proveedores si no existe
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS proveedores (
                id INT AUTO_INCREMENT PRIMARY KEY,
                persona_id INT NOT NULL,
                nro_cuenta INT AUTO_INCREMENT,
                UNIQUE KEY uq_proveedor_persona (persona_id),
                UNIQUE KEY uq_proveedor_nro_cuenta (nro_cuenta),
                FOREIGN KEY (persona_id) REFERENCES personas(id)
            )
        """))
        print("Tabla proveedores creada")

        # 4. Migrar datos: insertar en personas desde clientes_vieja (si hay datos)
        result = conn.execute(text("SELECT COUNT(*) FROM clientes_vieja"))
        count_vieja = result.scalar()
        if count_vieja > 0:
            # Usar INSERT IGNORE para saltar registros con CUIT/DNI duplicados
            conn.execute(text("""
                INSERT IGNORE INTO personas (
                    tipo_persona, nombre, apellido, cuit, dni, email, cod_area, telefono,
                    calle, numero_calle, locality, codigo_postal, provincia,
                    actividad_economica, tipo_actividad, condicion_iva, alicuota_iva_id,
                    observaciones, fecha_cierre_ejercicio, presenta_eecc, fecha_alta, creado, actualizado
                )
                SELECT
                    tipo_persona, nombre, apellido, cuit, dni, email, cod_area, telefono,
                    calle, numero_calle, domicilio, codigo_postal, provincia,
                    actividad_economica, tipo_actividad, condicion_iva, alicuota_iva_id,
                    observaciones, fecha_cierre_ejercicio, TRUE, fecha_alta, creado, actualizado
                FROM clientes_vieja
            """))
            print(f"Datos migrados a personas ({count_vieja} registros en origen)")
        else:
            print("No hay datos en clientes_vieja para migrar")

        # 5. Crear registros en clientes/proveedores según el tipo (si hay datos)
        if count_vieja > 0:
            conn.execute(text("""
                INSERT IGNORE INTO clientes (persona_id, nro_cuenta)
                SELECT p.id, vieja.nro_cuenta
                FROM personas p
                INNER JOIN clientes_vieja vieja ON vieja.tipo_persona = p.tipo_persona
                    AND vieja.nombre = p.nombre
                    AND vieja.cuit = p.cuit
                    AND vieja.dni = p.dni
                WHERE vieja.tipo = 'cliente'
            """))
            print("Clientes migrados")

            conn.execute(text("""
                INSERT IGNORE INTO proveedores (persona_id, nro_cuenta)
                SELECT p.id, vieja.nro_cuenta
                FROM personas p
                INNER JOIN clientes_vieja vieja ON vieja.tipo_persona = p.tipo_persona
                    AND vieja.nombre = p.nombre
                    AND vieja.cuit = p.cuit
                    AND vieja.dni = p.dni
                WHERE vieja.tipo = 'proveedor'
            """))
            print("Proveedores migrados")

        # 6. Verificar migración
        result = conn.execute(text("SELECT COUNT(*) FROM personas"))
        count_personas = result.scalar()
        print(f"Total personas: {count_personas}")

        result = conn.execute(text("SELECT COUNT(*) FROM clientes"))
        count_clientes = result.scalar()
        print(f"Total clientes: {count_clientes}")

        result = conn.execute(text("SELECT COUNT(*) FROM proveedores"))
        count_proveedores = result.scalar()
        print(f"Total proveedores: {count_proveedores}")

        # 7. Migrar sugerencias: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE sugerencias DROP FOREIGN KEY sugerencias_ibfk_1"))
            print("FK vieja de sugerencias eliminada")
        except Exception:
            print("FK vieja de sugerencias no existe o ya fue eliminada")

        # Migrar datos de sugerencias
        conn.execute(text("""
            UPDATE sugerencias s
            INNER JOIN clientes_vieja cv ON s.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET s.cliente_id = c.id
        """))
        print("Sugerencias migradas")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE sugerencias
                ADD CONSTRAINT sugerencias_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de sugerencias creada")
        except Exception:
            print("FK nueva de sugerencias ya existe")

        # 8. Migrar cliente_servicio: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE cliente_servicio DROP FOREIGN KEY cliente_servicio_ibfk_1"))
            print("FK vieja de cliente_servicio eliminada")
        except Exception:
            print("FK vieja de cliente_servicio no existe o ya fue eliminada")

        # Migrar datos de cliente_servicio
        conn.execute(text("""
            UPDATE cliente_servicio cs
            INNER JOIN clientes_vieja cv ON cs.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET cs.cliente_id = c.id
        """))
        print("Cliente_servicio migrado")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE cliente_servicio
                ADD CONSTRAINT cliente_servicio_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de cliente_servicio creada")
        except Exception:
            print("FK nueva de cliente_servicio ya existe")

        # 9. Migrar anticipos: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE anticipos DROP FOREIGN KEY anticipos_ibfk_1"))
            print("FK vieja de anticipos eliminada")
        except Exception:
            print("FK vieja de anticipos no existe o ya fue eliminada")

        # Migrar datos de anticipos
        conn.execute(text("""
            UPDATE anticipos a
            INNER JOIN clientes_vieja cv ON a.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET a.cliente_id = c.id
        """))
        print("Anticipos migrados")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE anticipos
                ADD CONSTRAINT anticipos_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de anticipos creada")
        except Exception:
            print("FK nueva de anticipos ya existe")

        # 10. Migrar facturas: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE facturas DROP FOREIGN KEY facturas_ibfk_1"))
            print("FK vieja de facturas eliminada")
        except Exception:
            print("FK vieja de facturas no existe o ya fue eliminada")

        # Migrar datos de facturas
        conn.execute(text("""
            UPDATE facturas f
            INNER JOIN clientes_vieja cv ON f.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET f.cliente_id = c.id
        """))
        print("Facturas migradas")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE facturas
                ADD CONSTRAINT facturas_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de facturas creada")
        except Exception:
            print("FK nueva de facturas ya existe")

        # 11. Migrar recibos: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE recibos DROP FOREIGN KEY recibos_ibfk_1"))
            print("FK vieja de recibos eliminada")
        except Exception:
            print("FK vieja de recibos no existe o ya fue eliminada")

        # Migrar datos de recibos
        conn.execute(text("""
            UPDATE recibos r
            INNER JOIN clientes_vieja cv ON r.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET r.cliente_id = c.id
        """))
        print("Recibos migrados")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE recibos
                ADD CONSTRAINT recibos_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de recibos creada")
        except Exception:
            print("FK nueva de recibos ya existe")

        # 12. Migrar compras: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE compras DROP FOREIGN KEY compras_ibfk_1"))
            print("FK vieja de compras eliminada")
        except Exception:
            print("FK vieja de compras no existe o ya fue eliminada")

        # Migrar datos de compras
        conn.execute(text("""
            UPDATE compras co
            INNER JOIN clientes_vieja cv ON co.proveedor_id = cv.id
            INNER JOIN proveedores p ON p.persona_id = cv.id
            SET co.proveedor_id = p.id
        """))
        print("Compras migradas")

        # Recrear FK apuntando a la nueva tabla proveedores
        try:
            conn.execute(text("""
                ALTER TABLE compras
                ADD CONSTRAINT compras_ibfk_1
                FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
            """))
            print("FK nueva de compras creada")
        except Exception:
            print("FK nueva de compras ya existe")

        # 13. Migrar bal_rt54_ejercicios: cambiar FK de clientes_vieja a clientes
        try:
            conn.execute(text("ALTER TABLE bal_rt54_ejercicios DROP FOREIGN KEY bal_rt54_ejercicios_ibfk_1"))
            print("FK vieja de bal_rt54_ejercicios eliminada")
        except Exception:
            print("FK vieja de bal_rt54_ejercicios no existe o ya fue eliminada")

        # Migrar datos de bal_rt54_ejercicios
        conn.execute(text("""
            UPDATE bal_rt54_ejercicios b
            INNER JOIN clientes_vieja cv ON b.cliente_id = cv.id
            INNER JOIN clientes c ON c.nro_cuenta = cv.nro_cuenta
            SET b.cliente_id = c.id
        """))
        print("Bal_rt54_ejercicios migrados")

        # Recrear FK apuntando a la nueva tabla clientes
        try:
            conn.execute(text("""
                ALTER TABLE bal_rt54_ejercicios
                ADD CONSTRAINT bal_rt54_ejercicios_ibfk_1
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            """))
            print("FK nueva de bal_rt54_ejercicios creada")
        except Exception:
            print("FK nueva de bal_rt54_ejercicios ya existe")

        # 14. Eliminar tabla vieja
        try:
            conn.execute(text("DROP TABLE clientes_vieja"))
            print("Tabla clientes_vieja eliminada")
        except Exception as e:
            print(f"No se pudo eliminar clientes_vieja: {e}")

    print("\nMigración completada con éxito")


if __name__ == "__main__":
    migrar()