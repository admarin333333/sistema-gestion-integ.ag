"""Arregla la codificación de un archivo de texto.

A veces un archivo UTF-8 se lee y se vuelve a guardar con la codificación
equivocada y los acentos quedan convertidos en `Ã¡`, `Ã©`, `â€`. Es cosa de
PowerShell (`Get-Content` + `Set-Content`), que interpreta los bytes con la
codificación del sistema en vez de UTF-8.

Acá el problema se agravó porque la conversión pasó **dos veces**: cada pasada
duplica el daño (`ó` → `Ã³` → `ÃƒÂ³`). Por eso el script repite el arreglo
hasta que el texto deja de cambiar.

El truco es al revés: el texto roto, codificado de vuelta a latin-1, da los
bytes UTF-8 originales, que al decodificarlos dan el texto correcto.

Uso:  python -X utf8 arreglar_codificacion.py tests/test_ejercicio.py
"""

import sys

# Caracteres que SÍ están rotos. Con alguno de estos se sabe que hay que
# arreglar; sin ninguno, el archivo está bien y no se toca (que es lo que
# importa: arreglar un archivo sano lo arruina).
ROTOS = ("Ã¡", "Ã©", "Ã­", "Ã³", "Ãº", "Ã±", "Ã ", "â€", "â†", "Â¿", "Ã§",
         "Ã¨", "Ã¼", "Ã—", "Ã‰")


def una_pasada(texto: str) -> str | None:
    """Una vuelta del arreglo. Devuelve None si no pudo.

    No se puede hacer `texto.encode("latin-1")` de una: el archivo tiene
    caracteres que no salen de latin-1 (PowerShell los dejó mal al leer) y eso
    revienta la operación entera. Por eso va carácter por carácter:

      - si el carácter representa un byte UTF-8 válido (0xC0 a 0xFF), se junta
        con los que siguen hasta armar la secuencia y se decodifica;
      - si no, se deja tal cual — puede ser un acento que ya estaba bien, y
        tocarlo lo arruinaría.

    Es la misma idea que un decodificador de texto, pero al revés: en vez de
    bytes → caracteres, caracteres → bytes → caracteres.
    """
    salida: list[str] = []
    buffer: list[int] = []
    esperados = 0  # cuántos bytes le faltan a la secuencia en curso

    def vaciar() -> None:
        nonlocal esperados
        if not buffer:
            esperados = 0
            return
        try:
            salida.append(bytes(buffer).decode("utf-8"))
        except UnicodeDecodeError:
            # Secuencia incompleta o inválida: se devuelve cada byte como
            # estaba, sin cambiar nada.
            salida.extend(bytes(buffer).decode("latin-1"))
        buffer.clear()
        esperados = 0

    for ch in texto:
        punto = ord(ch)
        if 0x80 <= punto <= 0xFF:
            if not buffer:
                # Byte inicial: de él depende cuántos siguen.
                # 0xC0-0xDF → 2 bytes · 0xE0-0xEF → 3 · 0xF0-0xF7 → 4
                if 0xC0 <= punto <= 0xDF:
                    esperados = 2
                elif 0xE0 <= punto <= 0xEF:
                    esperados = 3
                elif 0xF0 <= punto <= 0xF7:
                    esperados = 4
                else:
                    # Byte suelto que no inicia nada: se deja como estaba.
                    salida.append(ch)
                    continue
            buffer.append(punto)
            if len(buffer) >= esperados:
                vaciar()
            continue
        vaciar()
        salida.append(ch)
    vaciar()
    return "".join(salida)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    for ruta in sys.argv[1:]:
        with open(ruta, "rb") as f:
            crudo = f.read()

        # El BOM UTF-8 se saca: Python lo pone solo al escribir, y si queda
        # aparece un carácter raro al principio de la primera línea.
        if crudo.startswith(b"\xef\xbb\xbf"):
            crudo = crudo[3:]

        texto = crudo.decode("utf-8", errors="replace")
        if not any(m in texto for m in ROTOS):
            print(f"  = {ruta}: ya estaba bien")
            continue

        original = texto
        for _ in range(4):  # con dos pasadas alcanza; 4 es margen
            nuevo = una_pasada(texto)
            if nuevo is None or nuevo == texto:
                break
            texto = nuevo

        if texto == original:
            print(f"  ! {ruta}: tiene marcas raras pero no se pudo arreglar")
            continue

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"  + {ruta}: codificación arreglada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())