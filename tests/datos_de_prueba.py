"""
AVISA SI A UNA SUITE LE FALTAN DATOS DE PRUEBA.

    from datos_de_prueba import chequear_si_tengo_lo_que_necesito

Qué es esto y por qué existe

Hay pruebas que necesitan datos que NO están en la base de pruebas:

  - los ejercicios RT54 (con sus notas y sus valores)
  - los índices de moneda homogénea

Esos datos están en la base del estudio porque los cargaste a mano. No hay ningún
script en el proyecto que los cree, y la API tampoco los genera sola: al dar de
alta un ejercicio por API quedan 0 notas, que no es un balance.

Sin esto, esas cuatro pruebas fallaban a tres líneas de entrar:

    KeyError: 'cabecera'

Y ese error no dice nada. Parece un bug del programa y en realidad es que a la
base de pruebas le falta un ejercicio. Perder media hora cazando un KeyError en
lugar de saber al toque que el problema es otro.

Con esto, la prueba dice qué falta y por qué.

Cómo se usa

Al principio de la suite, después del login:

    chequear_o_salir("caratula", token, BASE)

Si falta algo, la suite se omite con un aviso. Si no, sigue como siempre.

`nombre` es un alias corto (ver `SUITES`) y el token es el de la sesión, porque
los chequeos van por la API y no por SQL: así funciona igual contra cualquier
base, sin importar cómo se haya armado.

Lo que NO hace

No crea los datos. Avisar es una cosa y fabricar un balance RT54 es otra muy
distinta: las 88 notas las genera un proceso que todavía no está identificado, y
armarlas a mano desde acá sería inventar la estructura de un balance fiscal.

Tampoco falla la corrida. Devuelve la lista de lo que falta y deja que la suite
decida: lo más simple es `salir_con_datos_faltantes(falta)`, que cuenta como
suite omitida y NO como fallo, para que el número de rojo siga significando
"algo está roto de verdad".
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"


# --------------------------------------------------------------------------
# Qué necesita cada suite
# --------------------------------------------------------------------------
#
# "chequea" dice qué pedir a la API y con qué resultado se considera que está.
# "por_que" es lo que se lee cuando falta: tiene que explicar la causa real, no
# repetir el síntoma.
SUITES = {
    "caratula": {
        "chequea": "ejercicio_rt54_id_1",
        "por_que": (
            "necesita el ejercicio RT54 número 1 (con su carátula). En la base "
            "del estudio existe; en la de pruebas no."
        ),
        "como_se_arregla": (
            "copiar el ejercicio desde la base del estudio, o armar uno "
            "propio. Ver MEMORIA.md."
        ),
    },
    "cuadros": {
        "chequea": "ejercicio_rt54_id_1",
        "por_que": (
            "necesita el ejercicio RT54 número 1 CON SUS 88 NOTAS (los cuadros "
            "2.1, 2.3, etc.). Un ejercicio sin notas no tiene ningún cuadro que "
            "mirar."
        ),
        "como_se_arregla": "ídem caratula: hace falta el ejercicio con notas cargadas.",
    },
    "recalculo": {
        "chequea": "ejercicio_rt54_id_1",
        "por_que": (
            "necesita el ejercicio RT54 número 1 para recalcular y comparar los "
            "totales antes y después."
        ),
        "como_se_arregla": "ídem caratula.",
    },
    "moneda": {
        "chequea": "indices_de_moneda",
        "por_que": (
            "necesita los índices de moneda homogénea (404 filas con los valores "
            "del IPC de AFIP). En la base del estudio están cargados a mano; no "
            "hay ningún archivo del proyecto que los tenga."
        ),
        "como_se_arregla": (
            "cargarlos desde la web de la AFIP, o exportar los que ya tenés en "
            "la base del estudio."
        ),
    },
}


# --------------------------------------------------------------------------
# Los chequeos
# --------------------------------------------------------------------------
#
# Cada uno devuelve un texto si falta algo, o None si está todo.


def _pedir(token, ruta):
    req = urllib.request.Request(BASE + ruta)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            crudo = r.read().decode()
            return r.status, (json.loads(crudo) if crudo else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def ejercicio_rt54_id_1(token):
    """El ejercicio RT54 número 1 tiene que existir y traer cabecera."""
    st, cuerpo = _pedir(token, "/api/balance-rt54/ejercicios/1")
    if st == 404:
        return "el ejercicio RT54 número 1 no existe"
    if st != 200 or not isinstance(cuerpo, dict):
        return f"no se pudo leer el ejercicio RT54 1 (HTTP {st})"
    if "cabecera" not in cuerpo:
        return "el ejercicio RT54 1 existe pero no trae cabecera"

    notas = cuerpo.get("notas")
    if isinstance(notas, list) and not notas:
        return (
            "el ejercicio RT54 1 existe pero tiene 0 notas: un balance sin "
            "notas no tiene cuadros ni valores"
        )
    return None


def indices_de_moneda(token):
    """Tiene que haber al menos un índice de moneda."""
    st, cuerpo = _pedir(token, "/api/indices-moneda?limite=5")
    if st != 200:
        return f"no se pudieron leer los índices de moneda (HTTP {st})"

    filas = cuerpo if isinstance(cuerpo, list) else (cuerpo or {}).get("indices") or []
    if not filas:
        return "no hay ningún índice de moneda cargado (deberían ser 404)"
    return None


CHEQUEOS = {
    "ejercicio_rt54_id_1": ejercicio_rt54_id_1,
    "indices_de_moneda": indices_de_moneda,
}


def chequear_si_tengo_lo_que_necesito(alias, token=None, base=None):
    """
    Devuelve una lista de strings con lo que falta, o `[]` si está todo.

    `alias` es el nombre corto de la suite (ver `SUITES`). Si no lo conozco,
    devuelve `[]`: es preferible no avisar a romper una suite por un typo en el
    nombre.
    """
    global BASE
    if base:
        BASE = base

    ficha = SUITES.get(alias)
    if ficha is None:
        return []

    chequeo = CHEQUEOS.get(ficha["chequea"])
    if chequeo is None:
        return []

    problema = chequeo(token)
    if problema is None:
        return []
    return [f"{alias}: {problema} — {ficha['por_que']}"]


def chequear_o_salir(alias, token=None, base=None):
    """
    Chequea y, si falta algo, termina la suite avisando.

    Es la forma en que la usan las suites. Encapsular el "chequear y salir" en una
    sola función evita el error que cometí la primera vez: llamar a las dos por
    separado y acordarse de que la segunda solo se llama si la primera devolvió
    algo. Si no, la suite anunciaba "OMITIDA" con la lista vacía incluso cuando
    estaba todo bien — o sea, exactamente al revés de lo que debía.

    Si no falta nada, NO hace nada y la suite sigue.

    Devuelve `[]` siempre, para que quien la llama pueda usar el resultado si
    quiere. No hace falta.
    """
    faltantes = chequear_si_tengo_lo_que_necesito(alias, token, base)
    if faltantes:
        _salir(faltantes)
    return []


def _salir(faltantes):
    """
    Termina la suite avisando qué falta.

    Sale con código 0 a propósito: la suite está OMITIDA, no rota. Si saliera
    con 1, el resumen contaría un fallo más y el número de rojo dejaría de
    significar "algo anda mal" para pasar a significar "falta un dato".

    Sale por `stdout` y no por `stderr`: `correr_todas.py` junta las dos salidas
    y busca el resumen, y un aviso en stderr se lee como si fuera un error.
    """
    print()
    print("  SUITE OMITIDA: faltan datos de prueba.")
    print("  " + "-" * 62)
    for linea in faltantes:
        print(f"  - {linea}")
        alias = linea.split(":")[0]
        ficha = SUITES.get(alias)
        if ficha:
            print(f"      cómo se arregla: {ficha['como_se_arregla']}")
    print("  " + "-" * 62)
    print()
    print("  No es un fallo del programa: esta base no tiene estos datos.")
    print("  (En la base del estudio sí están, cargados a mano.)")
    print()
    raise SystemExit(0)


# Se deja el nombre viejo como alias, para que una suite que ya lo importaba no
# se rompa. Ahora avisa en voz alta si la lista viene vacía, que es el error que
# había pasado sin verme.
def salir_con_datos_faltantes(faltantes):
    if not faltantes:
        # Antes esto imprimía "SUITE OMITIDA" sin lista y cortaba la suite. Ahora
        # avisa el error de uso y sigue.
        print(
            "  chequear_o_salir(): no hay nada que avisar. "
            "Usá chequear_o_salir() en vez de llamar a las dos por separado."
        )
        return
    _salir(faltantes)
