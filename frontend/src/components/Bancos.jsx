import { useEffect, useState } from "react";
import { listarBancos, renombrarBanco } from "../api/ctasBancarias.js";

/**
 * CATÁLOGO DE BANCOS.
 *
 * El catálogo **arranca vacío** y se llena solo: cuando el contador pega el CBU
 * de un cliente, el sistema lee los primeros 8 dígitos y crea el banco con un
 * nombre provisorio ("Banco 28505909").
 *
 * Los códigos de banco **no se inventan**: son los que salen del CBU, que a su
 * vez son los del Banco Central. Por eso esta pantalla no tiene un botón de
 * "agregar banco con el código que yo quiera": el código viene del CBU, y el
 * nombre es lo único que escribe la persona.
 *
 * Sirve para dos cosas:
 *
 * 1. **Ponerle el nombre** a los bancos que quedaron provisorios. El contador
 *    entra una vez por banco y listo.
 * 2. **Ver cuáles están cargados** y cuántas cuentas de clientes tiene cada uno,
 *    que es lo que sirve para saber si un banco está mal cargado.
 *
 * El código no se edita: es la clave primaria y viene del CBU. Si se pudiera
 * cambiar, las cuentas que apuntan al viejo quedarían huérfanas.
 */
export default function Bancos() {
  const [bancos, setBancos] = useState([]);
  const [editando, setEditando] = useState(null);
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = async () => {
    try {
      setBancos(await listarBancos());
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError("");
    try {
      await renombrarBanco(editando, nombre);
      setAviso("Banco actualizado.");
      setEditando(null);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  /** Un banco quedó provisorio si su nombre es el código con la palabra "Banco". */
  const provisorio = (b) => b.nombre === `Banco ${b.codigo}`;

  return (
    <div className="panel">
      <h3>Bancos</h3>
      <p className="nota">
        El catálogo se llena solo con los CBU que cargás en las fichas de los
        clientes. Los códigos salen del CBU, no se escriben a mano. Lo único que
        falta es ponerles el nombre a los que quedaron provisorios.
      </p>

      {error && <p className="error">{error}</p>}
      {aviso && <p className="nota">{aviso}</p>}

      {cargando && <p className="nota">Cargando…</p>}

      {!cargando && bancos.length === 0 && (
        <p className="nota">
          Todavía no hay ningún banco. Cuando cargues el primer CBU en la ficha de
          un cliente, el banco aparece acá solo.
        </p>
      )}

      {!cargando && bancos.length > 0 && (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bancos.map((b) => (
                <tr key={b.codigo} className={provisorio(b) ? "fila-vencida" : ""}>
                  <td className="mono">{b.codigo}</td>
                  <td>
                    {editando === b.codigo ? (
                      <form
                        onSubmit={guardar}
                        style={{ display: "flex", gap: "0.5rem" }}
                      >
                        <input
                          value={nombre}
                          onChange={(e) => setNombre(e.target.value)}
                          autoFocus
                          placeholder="Ej: Banco de Galicia"
                          aria-label={`Nombre del banco ${b.codigo}`}
                        />
                        <button className="btn btn-sm" type="submit" disabled={guardando}>
                          Guardar
                        </button>
                        <button
                          className="btn btn-sm fantasma"
                          type="button"
                          onClick={() => setEditando(null)}
                        >
                          Cancelar
                        </button>
                      </form>
                    ) : (
                      <>
                        {b.nombre}
                        {provisorio(b) && (
                          <small className="nota"> · falta poner el nombre</small>
                        )}
                      </>
                    )}
                  </td>
                  <td className="acciones">
                    {editando !== b.codigo && (
                      <button
                        className="btn btn-sm fantasma"
                        onClick={() => {
                          setEditando(b.codigo);
                          setNombre(
                            provisorio(b) ? "" : b.nombre
                          );
                        }}
                        title="Ponerle o corregir el nombre"
                      >
                        {provisorio(b) ? "Completar" : "Renombrar"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}