"""Reescribe el bloque de estilos de Vencimientos en styles.css.

El bloque anterior usaba colores claros (#fafafa, #fff) que en el tema oscuro
se veía como un parche blanco. Ahora usa las variables del tema
(--bg-2, --bg-3, --line).

Es un script y no el editor porque el archivo tiene acentos y PowerShell los
mangla al escribir.
"""

import io
import os
import re

RUTA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "src", "styles.css")
)

# El bloque arranca con un comentario de "===" que menciona Vencimientos. Como es
# lo último del archivo, se reemplaza desde ahí hasta el final.
RE_INI = re.compile(r"/\*\s*=+\s*\n\s*Vencimientos:")

NUEVO = """/* ================================================================
   Vencimientos: cascada año -> mes de Configuración
   ================================================================ */
.arbol-vencimientos {
  margin: 1.2rem 0 2rem;
  box-shadow: inset 0 0 0 1px var(--line);
}

/* Cada año es una fila que se abre y se cierra. */
.arbol-fila {
  display: flex;
  align-items: baseline;
  gap: 0.8rem;
  width: 100%;
  padding: 0.7rem 0.9rem;
  background: var(--bg-2);
  border: 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.arbol-fila:hover {
  background: var(--bg-3);
}
.arbol-fila.abierta {
  background: var(--bg-3);
  font-weight: 600;
}
.arbol-flecha {
  display: inline-block;
  width: 1rem;
  color: var(--muted, #7d8db0);
}

/* La fecha de última actualización va a la derecha, siempre visible. */
.arbol-fila .fecha-actualizacion {
  margin-left: auto;
  font-size: 0.78rem;
  white-space: nowrap;
  opacity: 0.85;
}

/* Al abrir un año aparece el menú del mes. */
.arbol-mes {
  padding: 1rem 1.2rem 0.4rem 2.4rem;
  background: var(--bg-3);
  border-bottom: 1px solid var(--line);
}
.arbol-mes .campo {
  max-width: 16rem;
}

/* La grilla del mes elegido. */
.arbol-grilla {
  padding: 0.4rem 0 0 0.6rem;
}
.arbol-grilla .panel {
  background: rgba(7, 11, 20, 0.55);
}

.arbol-nuevo-mes {
  display: flex;
  align-items: flex-end;
  gap: 0.8rem;
  padding: 0.9rem 1.2rem;
  border-top: 1px dashed var(--line);
  background: var(--bg-2);
}

/* Catálogo de conceptos */
.catalogo-concepts {
  margin-top: 2rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--line);
}
.catalogo-concepts h4 {
  margin: 0 0 0.3rem;
}
/* Fila de un concepto apagado: se ve más apagada, pero no desaparece. */
.catalogo-concepts tr.apagado {
  opacity: 0.55;
}

/* Aviso de guardado y contador de celdas (los usa la grilla) */
.aviso-guardado {
  padding: 0.6rem 0.8rem;
  margin: 0.6rem 0;
  border-left: 3px solid #2e7d32;
  background: rgba(46, 125, 50, 0.14);
  color: #a5d6a7;
}
.contador-celdas {
  margin-left: auto;
}

/* Aviso de CUIT con dígito verificador que no cierra: informa, no bloquea. */
.aviso-cuit {
  display: inline-block;
  margin-top: 0.2rem;
  padding: 0.15rem 0.45rem;
  border-radius: 3px;
  background: rgba(255, 193, 7, 0.16);
  box-shadow: inset 0 0 0 1px rgba(255, 193, 7, 0.45);
  color: #ffd54f;
  font-family: inherit;
  font-size: 0.78rem;
  line-height: 1.35;
}
"""


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    m = RE_INI.search(texto)
    if not m:
        raise SystemExit("No encontré el bloque de estilos de Vencimientos")
    i = m.start()

    texto = texto[:i] + NUEVO

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("styles.css: bloque de Vencimientos reescrito con el tema oscuro")


if __name__ == "__main__":
    main()