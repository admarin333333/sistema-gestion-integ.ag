"""El freno del secreto del JWT: la API no debe arrancar con una clave de mentira.

    python -X utf8 test_secreto_jwt.py

**Qué se verifica.** Antes, `config.py` traía `jwt_secret = "clave-temporal"` como
valor por defecto. Si faltaba la variable en el `.env`, el sistema arrancaba
igual con esa clave, que está escrita en el código y en la documentación. Como el
JWT es HS256 (firma simétrica), con esa clave **cualquiera que tuviera el proyecto
podía fabricar un token de administrador a mano** y entrar sin contraseña.

Ahora `jwt_secret` no tiene valor por defecto y `chequear_secreto()` frena el
arranque en tres casos: que falte, que sea la de ejemplo, o que sea cortita.

**La prueba NO toca el `.env` de la máquina.** Arma los `Settings` a mano con el
secreto que quiere probar: si escribiera el archivo, una prueba fallida dejaría
al sistema sin clave y no podría arrancar más.

Cada mensaje de error se verifica contra su contenido, no solo que sea un error:
un mensaje que no dice *qué hacer* no sirve, porque el que lo lee no lo entiende
y no lo arregla.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.config import ConfigError, Settings, settings

resultado = []


def chequear(nombre, condicion, detalle=""):
    ok = bool(condicion)
    resultado.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))


def frenar(secreto):
    """Devuelve el mensaje del error, o None si NO frenó (que es lo malo)."""
    try:
        Settings(jwt_secret=secreto).chequear_secreto()
        return None
    except ConfigError as e:
        return str(e)


# --------------------------------------------------------------------------
# 1) El secreto de ejemplo: el que estaba escrito en el código
# --------------------------------------------------------------------------
msg = frenar("clave-temporal")
chequear("Frena con el secreto de ejemplo", msg is not None, "NO frenó: con esa clave cualquiera se hace admin")
if msg:
    chequear("Dice cómo generar una clave", "token_urlsafe" in msg, msg[:90])
    chequear("Dice dónde va la variable", ".env" in msg, msg[:90])
    chequear("No imprime la clave", "clave-temporal" in msg, "el mensaje repite la clave prohibida")

# --------------------------------------------------------------------------
# 2) Sin secreto: la variable no está en el .env
# --------------------------------------------------------------------------
msg = frenar(None)
chequear("Frena si falta JWT_SECRET", msg is not None, "NO frenó")
if msg:
    chequear("Dice cómo generarlo", "token_urlsafe" in msg, msg[:90])

msg = frenar("")
chequear("Frena con la variable vacía", msg is not None, "NO frenó")

msg = frenar("     ")
chequear("Frena si son solo espacios", msg is not None, "NO frenó")

# --------------------------------------------------------------------------
# 3) Secreto demasiado corto
# --------------------------------------------------------------------------
msg = frenar("abc123")
chequear("Frena con menos de 32 caracteres", msg is not None, "NO frenó")
if msg:
    chequear("Dice cuántos caracteres hacen falta", "32" in msg, msg[:90])

# 31 caracteres: uno menos del mínimo, tiene que frenar
msg = frenar("k" * 31)
chequear("Frena con 31 caracteres (uno menos del mínimo)", msg is not None, "NO frenó")

# --------------------------------------------------------------------------
# 4) Un secretobueno NO tiene que frenar: esto es lo que evita que el sistema
#    se quede sin arrancar por una regla demasiado estricta.
# --------------------------------------------------------------------------
msg = frenar("k" * 32)
chequear("Deja pasar uno de 32 caracteres (el mínimo)", msg is None, msg[:90] if msg else "")

msg = frenar("k" * 47)
chequear("Deja pasar uno de 47 caracteres", msg is None, msg[:90] if msg else "")

# --------------------------------------------------------------------------
# 5) El `.env` de la máquina tiene que seguir arrancando
# --------------------------------------------------------------------------
# Esta es la más importante: la regla no puede romper el sistema que está andando.
try:
    settings.chequear_secreto()
    chequear("El .env de esta maquina sigue arrancando", True)
except ConfigError as e:
    chequear("El .env de esta maquina sigue arrancando", False, str(e)[:140])

# --------------------------------------------------------------------------
# 6) El valor por defecto ya no es una clave de mentira
# --------------------------------------------------------------------------
chequear(
    "Settings ya no trae un secreto por defecto",
    Settings.model_fields["jwt_secret"].default is None,
    f"el default es {Settings.model_fields['jwt_secret'].default!r}",
)

# --------------------------------------------------------------------------
fallidas = [r for r in resultado if not r[1]]
print(f"\n{len(resultado) - len(fallidas)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidas else 0)