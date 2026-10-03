"""Agrega los estilos del Plan de Cuentas a styles.css.

Usa un script (y no el editor) porque el archivo tiene acentos y PowerShell los
mangla al escribir. Los estilos se cuelgan al final del archivo.
"""

import io
import os

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "src", "styles.css")
)

MARCADOR = "/* ================================================================\n   Plan de cuentas: árbol"

NUEVO = """
/* ================================================================
   Plan de cuentas: árbol
   ================================================================ */
.pc-arbol {
  margin: 1rem 0;
  box-shadow: inset 0 0 0 1px var(--line);
}

/* Una cuenta = una fila. */
.pc-fila {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.35rem 0.7rem 0.35rem 0;
  border-bottom: 1px solid var(--line);
}
/* Imputable = hoja, la que recibe movimientos. */
.pc-fila.imputable {
  background: rgba(255, 255, 255, 0.03);
}
/* Agrupador: sin movimientos propios, solo agrupa. */
.pc-fila.grupo {
  background: var(--bg-3);
}
.pc-fila.apagada {
  opacity: 0.5;
}
.pc-fila:hover {
  background: rgba(79, 140, 255, 0.08);
}

.pc-flecha {
  flex: 0 0 auto;
  width: 1.6rem;
  border: 0;
  background: none;
  color: var(--muted, #7d8db0);
  font: inherit;
  cursor: pointer;
}
.pc-flecha:disabled {
  color: #45506b;
  cursor: default;
}

.pc-codigo {
  flex: 0 0 6.2rem;
  font-size: 0.82rem;
  color: #8fb4ff;
}
.pc-fila.grupo .pc-codigo {
  font-weight: 700;
  color: #cfe0ff;
}

.pc-nombre {
  flex: 1 1 auto;
  min-width: 0;
}

/* La D / A de Deudora-Acreedora. */
.pc-dh {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 3px;
  font-style: normal;
  font-size: 0.72rem;
  font-weight: 700;
}
.pc-dh.deudora {
  background: rgba(79, 140, 255, 0.2);
  box-shadow: inset 0 0 0 1px rgba(79, 140, 255, 0.5);
  color: #9dc0ff;
}
.pc-dh.acreedora {
  background: rgba(46, 125, 50, 0.22);
  box-shadow: inset 0 0 0 1px rgba(76, 175, 80, 0.5);
  color: #a5d6a7;
}

.pc-aux {
  flex: 0 0 7.5rem;
  font-size: 0.75rem;
}

/* El formulario de "subcuenta nueva". */
.pc-alta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.6rem 0.9rem;
  background: var(--bg-2);
  border-bottom: 1px solid var(--line);
}
.pc-alta input[type="text"] {
  flex: 1 1 16rem;
}

/* La explicación de arriba de qué es naturaleza y qué es deudora/acreedora. */
.pc-leyenda {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin: 0.8rem 0 0.2rem;
  padding: 0.7rem 0.9rem;
  background: var(--bg-2);
  box-shadow: inset 0 0 0 1px var(--line);
  font-size: 0.82rem;
  line-height: 1.5;
  color: #b6c4de;
}
.pc-leyenda .pc-dh {
  vertical-align: -3px;
  margin: 0 0.1rem;
}
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if MARCADOR in texto:
        print("Los estilos del Plan de Cuentas ya están: no se toca nada")
        return

    texto = texto.rstrip() + "\n" + NUEVO

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("styles.css: agregados los estilos del Plan de Cuentas")


if __name__ == "__main__":
    main()