import { useEffect, useRef, useState } from "react";
import { listarClientes } from "../api/clientes.js";
import {
  crearEjercicio,
  descargarMonedaHomogenea,
  eliminarEjercicio,
  emitirExcel,
  guardarBalance,
  listarEjercicios,
  monedaHomogenea,
  obtenerBalance,
  recalcularCuadros,
} from "../api/balanceRt54.js";
import BuscadorCliente from "../components/BuscadorCliente.jsx";
import { fecha, pesos, cuatro } from "../formato.js";

// Estilos para carátula: todos los inputs de la ficha deben tener la misma altura
  const inputStyle = {
    height: "38px", // altura fija para alinearse con los de tipo date
    boxSizing: "border-box",
  };

  const PESTANAS = [
  ["caratula", "Carátula"],
  ["esp", "Situación Patrimonial"],
  ["er", "Resultados"],
  ["eepn", "Patrimonio Neto"],
  ["notas", "Notas"],
  ["moneda", "Moneda homogénea"],
];

const TITULOS_GRUPO = {
  aportes: "APORTES DE LOS PROPIETARIOS",
  resultados: "RESULTADOS ACUMULADOS",
  totales: "TOTALES",
};

const nuevoVacio = () => {
  const anio = new Date().getFullYear();
  return {
    nombre: String(anio),
    anio_inicio: anio,
    anio_fin: anio,
  };
};

/** El intervalo que va a calcular el servidor, para mostrarlo antes de crear. */
const iso = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const intervaloDe = (anioInicio, anioFin, dia, mes) => {
  const dias = (a, m) => new Date(a, m, 0).getDate();
  const ai = Number(anioInicio);
  const af = Number(anioFin);
  if (!ai || !af || !dia || !mes || af < ai) return null;
  const d = Math.min(Number(dia), dias(af, Number(mes)));
  const fin = new Date(af, Number(mes) - 1, d);
  if (ai === af) return { inicio: iso(fin), fin: iso(fin) };
  const ini = new Date(af, Number(mes) - 1, d);
  ini.setFullYear(ai);
  ini.setDate(ini.getDate() + 1);
  return { inicio: iso(ini), fin: iso(fin) };
};

/** El comparativo termina un día antes de que empiece el ejercicio. */
const fechaComparativo = (isoInicio) => {
  const [a, m, d] = isoInicio.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d - 1)).toISOString().slice(0, 10);
};

const numero = (v) => Number(String(v ?? "").replace(",", ".")) || 0;

/** Todo lo que se editó, en la lista de valores que espera el backend. */
const armarValores = (b) => {
  const valores = [];
  ["activo", "pasivo"].forEach((lado) => {
    (b.esp[lado] || []).forEach((f) => {
      if (f.tipo === "rubro") {
        valores.push({
          seccion: "esp",
          clave: f.clave,
          valor_actual: numero(f.actual),
          valor_anterior: numero(f.anterior),
        });
      }
    });
  });
  (b.er || []).forEach((f) => {
    if (f.tipo === "rubro") {
      valores.push({
        seccion: "er",
        clave: f.clave,
        valor_actual: numero(f.actual),
        valor_anterior: numero(f.anterior),
      });
    }
  });
  (b.eepn.filas || []).forEach((f) => {
    if (f.tipo !== "dato") return;
    b.eepn.columnas.forEach((c) => {
      if (c.calc) return;
      const celda = f.celdas[c.clave];
      valores.push({
        seccion: "eepn",
        clave: `${f.clave}:${c.clave}`,
        valor_actual: numero(celda.actual),
        valor_anterior: numero(celda.anterior),
      });
    });
  });
  return valores;
};

/** Las notas, en la lista que espera el backend (clave + texto). */
const armarNotas = (b) =>
  (b.notas || []).map(({ clave, texto }) => ({ clave, texto }));

/**
 * Los importes cargados a mano en los cuadros de las notas, con clave
 * "2.3:44:C" (nota:fila del Excel:columna). Las celdas vacías no se mandan:
 * significan "no cargadas".
 */
const armarCeldas = (b) => {
  const celdas = [];
  for (const n of b.notas || []) {
    if (!n.cuadro) continue;
    for (const f of n.cuadro.filas) {
      for (const col of n.cuadro.columnas) {
        const celda = f.celdas[col.letra];
        if (celda && !celda.calc && String(celda.valor ?? "").trim() !== "") {
          celdas.push({
            clave: `${n.clave}:${f.fila}:${col.letra}`,
            valor: numero(celda.valor),
          });
        }
      }
    }
  }
  return celdas;
};

export default function BalanceRT54() {
  const [clientes, setClientes] = useState([]);
  const [cliente, setCliente] = useState(null);
  const [ejercicios, setEjercicios] = useState([]);
  const [borrador, setBorrador] = useState(null); // lo último que devolvió el servidor
  const [pestana, setPestana] = useState("caratula");
  const [nuevo, setNuevo] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [sucio, setSucio] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [error, setError] = useState("");
  // Solapa "Moneda homogénea": el servidor calcula el coeficiente y actualiza.
  const [moneda, setMoneda] = useState(null);
  const [monedaCargando, setMonedaCargando] = useState(false);
  const [monedaError, setMonedaError] = useState("");
  // Para pedirle al servidor que recalcule los Subtotal/Total de los cuadros
  // apenas el usuario deja de escribir (la suma nunca la hace el navegador).
  const borradorRef = useRef(null);
  const timerCuadros = useRef(null);
  const seqCuadros = useRef(0);

  useEffect(() => {
    borradorRef.current = borrador;
  });

  /* Si se entra desde la ficha del cliente (`/balance-rt54?cliente=123`), se
   abre ese cliente solo. Sin esto habría que volver a elegirlo en el buscador,
   que es justo lo que el contador ya hizo.
   *
   * Se lee de la URL cuando llega la lista de clientes; si el id no existe (se
   * borró el cliente, o se copió el link mal) no se rompe nada: queda el
   * buscador vacío y el contador elige a mano. */
  const [idDeUrl, setIdDeUrl] = useState(null);
  useEffect(() => {
    const deUrl = new URLSearchParams(location.search).get("cliente");
    if (deUrl) setIdDeUrl(Number(deUrl));
  }, []);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => setClientes([]));
  }, []);

  // Cuando ya llegó la lista, si venía un id en la URL se elige ese cliente.
  // Va con `idDeUrl` como dependencia y después se limpia, así no vuelve a
  // elegir el mismo en cada cambio de la lista.
  useEffect(() => {
    if (!idDeUrl || !clientes.length) return;
    const encontrado = clientes.find((c) => c.id === idDeUrl);
    if (encontrado && !cliente) alElegirCliente(encontrado);
    setIdDeUrl(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idDeUrl, clientes]);

  // Al abrir la solapa, el servidor calcula el coeficiente y la actualización.
  useEffect(() => {
    if (pestana !== "moneda" || !borrador) return undefined;
    let vivo = true;
    setMonedaCargando(true);
    setMonedaError("");
    monedaHomogenea(borrador.cabecera.id)
      .then((d) => {
        if (vivo) setMoneda(d);
      })
      .catch((e) => {
        if (vivo) {
          setMoneda(null);
          setMonedaError(e.message);
        }
      })
      .finally(() => {
        if (vivo) setMonedaCargando(false);
      });
    return () => {
      vivo = false;
    };
  }, [pestana, borrador]);

  const cambiarSinGuardar = () =>
    !sucio || window.confirm("Hay cambios sin guardar. ¿Salir sin guardar?");

  const alElegirCliente = async (c) => {
    if (!cambiarSinGuardar()) return;
    setCliente(c);
    setBorrador(null);
    setEjercicios([]);
    setSucio(false);
    setGuardado(false);
    setError("");
    if (c) {
      try {
        setEjercicios(await listarEjercicios(c.id));
      } catch (e) {
        setError(e.message);
      }
    }
  };

  const abrirEjercicio = async (id) => {
    if (!cambiarSinGuardar()) return;
    try {
      const balance = await obtenerBalance(id);
      setBorrador(balance);
      setSucio(false);
      setGuardado(false);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };

  const crearNuevo = async (e) => {
    e.preventDefault();
    if (!cliente) return;
    setError("");
    try {
      const balance = await crearEjercicio({
        cliente_id: cliente.id,
        nombre: nuevo.nombre,
        anio_inicio: Number(nuevo.anio_inicio),
        anio_fin: Number(nuevo.anio_fin),
        // El día y mes de cierre los tiene el cliente; solo se mandan si el
        // cliente todavía no los tiene cargados.
        ...(nuevo.dia_mes_cierre && nuevo.mes_cierre
          ? {
              dia_mes_cierre: Number(nuevo.dia_mes_cierre),
              mes_cierre: Number(nuevo.mes_cierre),
            }
          : {}),
      });
      setNuevo(null);
      setBorrador(balance);
      setSucio(false);
      setGuardado(false);
      setPestana("caratula");
      setEjercicios(await listarEjercicios(cliente.id));
    } catch (e2) {
      setError(e2.message);
    }
  };

  const guardar = async () => {
    if (!borrador) return null;
    setGuardando(true);
    setError("");
    try {
      const respuesta = await guardarBalance(borrador.cabecera.id, {
        cabecera: borrador.cabecera,
        valores: armarValores(borrador),
        notas: armarNotas(borrador),
        celdas_nota: armarCeldas(borrador),
      });
      setBorrador(respuesta);
      setSucio(false);
      setGuardado(true);
      setEjercicios((lista) =>
        lista.map((e) => (e.id === respuesta.cabecera.id ? respuesta.cabecera : e))
      );
      return respuesta;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async () => {
    if (!borrador) return;
    const nombre = borrador.cabecera.nombre;
    if (!window.confirm(`¿Eliminar el ejercicio ${nombre}? Se borran sus importes.`)) return;
    try {
      await eliminarEjercicio(borrador.cabecera.id);
      setBorrador(null);
      setSucio(false);
      setGuardado(false);
      setEjercicios(await listarEjercicios(cliente.id));
    } catch (e) {
      setError(e.message);
    }
  };

  const emitir = async () => {
    if (!borrador) return;
    setError("");
    try {
      let paraEmitir = borrador;
      if (sucio) {
        // Antes de emitir, guardamos: el Excel sale con los últimos cambios.
        const guardadoAhora = await guardar();
        if (!guardadoAhora) return;
        paraEmitir = guardadoAhora;
      }
      await emitirExcel(paraEmitir.cabecera.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const marcarSucio = () => {
    setSucio(true);
    setGuardado(false);
  };

  const editarCab = (campo, valor) => {
    setBorrador((b) => ({ ...b, cabecera: { ...b.cabecera, [campo]: valor } }));
    marcarSucio();
  };

  const editarEsp = (lado, clave, campo, valor) => {
    setBorrador((b) => ({
      ...b,
      esp: {
        ...b.esp,
        [lado]: b.esp[lado].map((f) =>
          f.clave === clave ? { ...f, [campo]: valor } : f
        ),
      },
    }));
    marcarSucio();
  };

  const editarEr = (clave, campo, valor) => {
    setBorrador((b) => ({
      ...b,
      er: b.er.map((f) => (f.clave === clave ? { ...f, [campo]: valor } : f)),
    }));
    marcarSucio();
  };

  const editarEepn = (filaClave, colClave, campo, valor) => {
    setBorrador((b) => ({
      ...b,
      eepn: {
        ...b.eepn,
        filas: b.eepn.filas.map((f) =>
          f.clave === filaClave
            ? {
                ...f,
                celdas: {
                  ...f.celdas,
                  [colClave]: { ...f.celdas[colClave], [campo]: valor },
                },
              }
            : f
        ),
      },
    }));
    marcarSucio();
  };

  const editarNota = (clave, texto) => {
    setBorrador((b) => ({
      ...b,
      notas: (b.notas || []).map((n) => (n.clave === clave ? { ...n, texto } : n)),
    }));
    marcarSucio();
  };

  /**
   * Pide al servidor las sumatorias de los cuadros con los importes actuales,
   * sin guardar. Espera medio segundo a que el usuario deje de escribir y
   * descarta la respuesta si hubo una tecla posterior.
   */
  const programarRecalculoCuadros = () => {
    seqCuadros.current += 1;
    const seq = seqCuadros.current;
    clearTimeout(timerCuadros.current);
    timerCuadros.current = setTimeout(async () => {
      const b = borradorRef.current;
      if (!b) return;
      try {
        const cuadros = await recalcularCuadros(armarCeldas(b));
        if (seqCuadros.current !== seq) return; // siguió tipeando
        setBorrador((actual) => ({
          ...actual,
          notas: (actual.notas || []).map((n) =>
            cuadros[n.clave] ? { ...n, cuadro: cuadros[n.clave] } : n
          ),
        }));
      } catch {
        // sin respuesta: el total queda como estaba hasta el próximo Guardar
      }
    }, 500);
  };

  /** Un importe en una celda del cuadro de composición de una nota. */
  const editarCeldaNota = (claveNota, fila, letra, valor) => {
    setBorrador((b) => ({
      ...b,
      notas: (b.notas || []).map((n) =>
        n.clave !== claveNota || !n.cuadro
          ? n
          : {
              ...n,
              cuadro: {
                ...n.cuadro,
                filas: n.cuadro.filas.map((f) =>
                  f.fila !== fila
                    ? f
                    : {
                        ...f,
                        celdas: {
                          ...f.celdas,
                          [letra]: { ...f.celdas[letra], valor },
                        },
                      }
                ),
              },
            }
      ),
    }));
    marcarSucio();
    programarRecalculoCuadros();
  };

  const cab = borrador?.cabecera;
  const comp = cab ? fecha(fechaComparativo(cab.fecha_inicio)) : "";

  /** El cuadro de composición de una nota, como una planillita de Excel. */
  const renderCuadro = (n) => {
    const { columnas, filas } = n.cuadro;
    const conGrupo = columnas.some((c) => c.grupo);
    const grupos = [];
    columnas.forEach((c) => {
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.grupo === c.grupo) ultimo.cantidad += 1;
      else grupos.push({ grupo: c.grupo, cantidad: 1 });
    });
    return (
      <table className="eecc-cuadro">
        <thead>
          <tr>
            <th rowSpan={conGrupo ? 2 : 1}>Conceptos</th>
            {conGrupo
              ? grupos.map((g, i) => (
                  <th key={i} colSpan={g.cantidad}>{g.grupo}</th>
                ))
              : columnas.map((c) => <th key={c.letra}>{c.etiqueta}</th>)}
          </tr>
          {conGrupo && (
            <tr>
              {columnas.map((c) => (
                <th key={c.letra}>{c.etiqueta}</th>
              ))}
            </tr>
          )}
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr
              key={f.fila}
              className={
                f.tipo === "dato" || f.tipo === "prevision" ? "" : "eecc-cuadro-total"
              }
            >
              <th scope="row">{f.rotulo}</th>
              {columnas.map((c) => {
                const celda = f.celdas[c.letra];
                if (celda.calc) {
                  return (
                    <td key={c.letra} className="mono derecha">
                      {pesos(celda.valor)}
                    </td>
                  );
                }
                return (
                  <td key={c.letra}>
                    <input
                      type="number"
                      step="0.01"
                      value={celda.valor ?? ""}
                      onChange={(e) =>
                        editarCeldaNota(n.clave, f.fila, c.letra, e.target.value)
                      }
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const renderMoneda = () => {
    if (monedaCargando && !moneda) {
      return <p className="nota">Calculando el coeficiente…</p>;
    }
    if (monedaError) {
      return (
        <div className="panel">
          <p className="error">{monedaError}</p>
          <p className="nota">
            El índice se carga en Configuración → "Índice de moneda homogénea
            (FACPCE)".
          </p>
        </div>
      );
    }
    if (!moneda) return null;
    const d = moneda;

    const tabla = (titulo, filas) => (
      <table className="eecc-cuadro" key={titulo}>
        <thead>
          <tr>
            <th>{titulo}</th>
            <th className="derecha">Saldo al {fecha(d.fecha_fin)}</th>
            <th className="derecha">Actualizado al {fecha(d.proxima_fecha_cierre)}</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) =>
            f.tipo === "titulo" ? (
              <tr key={f.clave} className="eecc-titulo">
                <td colSpan="3">{f.etiqueta}</td>
              </tr>
            ) : (
              <tr key={f.clave} className={f.tipo === "total" ? "eecc-cuadro-total" : ""}>
                <th scope="row">{f.etiqueta}</th>
                <td className="mono derecha">{pesos(f.actual)}</td>
                <td className="mono derecha">{pesos(f.actualizado)}</td>
              </tr>
            )
          )}
        </tbody>
      </table>
    );

    return (
      <>
        <p className="eecc-nota">
          El servidor multiplica cada saldo por el coeficiente (índice del
          próximo cierre ÷ índice de este cierre), calculado con4 decimales.
          No se guarda nada: es para ver y para bajar el Excel.
        </p>
        <div className="panel">
          <dl className="detalle">
            <div>
              <dt>Cliente</dt>
              <dd>{d.cliente}</dd>
            </div>
            <div>
              <dt>Ejercicio</dt>
              <dd>{d.ejercicio}</dd>
            </div>
            <div>
              <dt>Fecha de inicio</dt>
              <dd className="mono">{fecha(d.fecha_inicio)}</dd>
            </div>
            <div>
              <dt>Fecha de cierre</dt>
              <dd className="mono">{fecha(d.fecha_fin)}</dd>
            </div>
            <div>
              <dt>Próxima fecha de cierre</dt>
              <dd className="mono">{fecha(d.proxima_fecha_cierre)}</dd>
            </div>
            <div>
              <dt>Índice fecha de cierre anterior</dt>
              <dd className="mono">{cuatro(d.indice_anterior.valor)}</dd>
            </div>
            <div>
              <dt>Índice fecha de cierre nuevo</dt>
              <dd className="mono">{cuatro(d.indice_nuevo.valor)}</dd>
            </div>
            <div>
              <dt>Coeficiente (nuevo ÷ anterior)</dt>
              <dd className="mono">{cuatro(d.coeficiente)}</dd>
            </div>
          </dl>
        </div>
        {tabla("ACTIVO", d.esp.activo)}
        {tabla("PASIVO", d.esp.pasivo)}
        {tabla("ESTADO DE RESULTADOS", d.er)}
        <div className="form-acciones">
          <button
            className="btn"
            type="button"
            onClick={() => descargarMonedaHomogenea(borrador.cabecera.id)}
          >
            Descargar Excel
          </button>
        </div>
      </>
    );
  };

  const renderNotas = () => {
    const secciones = [];
    (borrador.notas || []).forEach((n) => {
      let s = secciones.find((x) => x.clave === n.seccion);
      if (!s) {
        s = { clave: n.seccion, titulo: n.seccion_titulo, notas: [] };
        secciones.push(s);
      }
      s.notas.push(n);
    });
    return (
      <div className="eecc-notas">
        <p className="eecc-nota">
          Texto de cada nota tal cual querés que salga en el Excel. Si no tocás
          nada, se emite el texto del modelo. Los Subtotal y Total de los
          cuadros los calcula el sistema.
        </p>
        {secciones.map((s) => (
          <details key={s.clave} className="eecc-notas-seccion">
            <summary>{s.titulo}</summary>
            {s.notas.map((n) => (
              <div key={n.clave} className="eecc-nota-bloque">
                <label className="campo eecc-notas-nota">
                  <span>
                    {n.clave} · {n.titulo}
                  </span>
                  <textarea
                    rows={n.texto ? Math.min(10, n.texto.split("\n").length + 2) : 3}
                    value={n.texto}
                    onChange={(e) => editarNota(n.clave, e.target.value)}
                  />
                </label>
                {n.cuadro && renderCuadro(n)}
              </div>
            ))}
          </details>
        ))}
      </div>
    );
  };

  const renderCaratula = () => (
    <>
      <div className="buscador">
        <label className="campo">
          <span>Nombre del ejercicio</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.nombre} onChange={(e) => editarCab("nombre", e.target.value)} />
        </label>
        <label className="campo">
          <span>Fecha de inicio</span>
          <input style={{height: "38px", boxSizing: "border-box"}} type="date" value={cab.fecha_inicio} onChange={(e) => editarCab("fecha_inicio", e.target.value)} />
        </label>
        <label className="campo">
          <span>Fecha de cierre</span>
          <input style={{height: "38px", boxSizing: "border-box"}} type="date" value={cab.fecha_fin} onChange={(e) => editarCab("fecha_fin", e.target.value)} />
        </label>
      </div>
      <div className="buscador">
        <label className="campo">
          <span>Nombre de la entidad</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.entidad || ""} onChange={(e) => editarCab("entidad", e.target.value)} />
        </label>
        <label className="campo">
          <span>CUIT</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.cuit || ""} onChange={(e) => editarCab("cuit", e.target.value)} />
        </label>
      </div>
      <div className="buscador">
        <label className="campo">
          <span>Domicilio legal</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.domicilio || ""} onChange={(e) => editarCab("domicilio", e.target.value)} />
        </label>
        <label className="campo">
          <span>Actividad principal</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.actividad || ""} onChange={(e) => editarCab("actividad", e.target.value)} />
        </label>
        <label className="campo">
          <span>Actividad secundaria</span>
          <input style={{height: "38px", boxSizing: "border-box"}} value={cab.actividad_secundaria || ""} onChange={(e) => editarCab("actividad_secundaria", e.target.value)} />
        </label>
      </div>
      <p className="eecc-nota">
        Registro Público de Comercio y sociedad controlante. Lo que quede vacío
        no se toca: la celda del Excel queda como viene el modelo.
      </p>
      <div className="buscador">
        <label className="campo">
          <span>Fecha de inscripción en el RPC</span>
          <input
            type="date"
            value={cab.fecha_inscripcion_rpc || ""}
            onChange={(e) => editarCab("fecha_inscripcion_rpc", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Fecha del estatuto o contrato social</span>
          <input
            type="date"
            value={cab.fecha_estatuto || ""}
            onChange={(e) => editarCab("fecha_estatuto", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Última modificación del estatuto</span>
          <input
            type="date"
            value={cab.fecha_modificacion_estatuto || ""}
            onChange={(e) =>
              editarCab("fecha_modificacion_estatuto", e.target.value)
            }
          />
        </label>
        <label className="campo">
          <span>Fecha de vencimiento de la entidad</span>
          <input
            type="date"
            value={cab.fecha_vencimiento_entidad || ""}
            onChange={(e) =>
              editarCab("fecha_vencimiento_entidad", e.target.value)
            }
          />
        </label>
        <label className="campo">
          <span>Matrícula N°</span>
          <input
            value={cab.matricula_rpc || ""}
            onChange={(e) => editarCab("matricula_rpc", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Identificación del RPC</span>
          <input
            value={cab.identificacion_rpc || ""}
            onChange={(e) => editarCab("identificacion_rpc", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Duración de la entidad (años)</span>
          <input
            type="number"
            step="1"
            value={cab.duracion_entidad ?? ""}
            onChange={(e) => editarCab("duracion_entidad", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Unidad de medida de los EECC</span>
          <input
            value={cab.unidad_medida || ""}
            onChange={(e) => editarCab("unidad_medida", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Sociedad controlante</span>
          <input
            value={cab.controlante_denominacion || ""}
            onChange={(e) =>
              editarCab("controlante_denominacion", e.target.value)
            }
          />
        </label>
        <label className="campo">
          <span>Domicilio legal de la controlante</span>
          <input
            value={cab.controlante_domicilio || ""}
            onChange={(e) => editarCab("controlante_domicilio", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Actividad principal de la controlante</span>
          <input
            value={cab.controlante_actividad || ""}
            onChange={(e) => editarCab("controlante_actividad", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Participación en el patrimonio</span>
          <input
            value={cab.controlante_participacion || ""}
            onChange={(e) =>
              editarCab("controlante_participacion", e.target.value)
            }
          />
        </label>
        <label className="campo">
          <span>Porcentaje de votos de la controlante</span>
          <input
            value={cab.controlante_votos || ""}
            onChange={(e) => editarCab("controlante_votos", e.target.value)}
          />
        </label>
        <label className="campo">
          <span>Entes controlados en nota N°</span>
          <input
            value={cab.entes_nota || ""}
            onChange={(e) => editarCab("entes_nota", e.target.value)}
          />
        </label>
      </div>
      <p className="eecc-nota">
        Composición del capital: un renglón por tabla, igual que el modelo.
      </p>
      {[
        ["cap_circ", "Acciones / Cuotas Sociales en circulación"],
        ["cap_cart", "Acciones / Cuotas Sociales en cartera"],
      ].map(([p, titulo]) => (
        <table className="eecc-cuadro eecc-capital" key={p}>
          <thead>
            <tr>
              <th colSpan="3">{titulo}</th>
              <th colSpan="2">Capital</th>
            </tr>
            <tr>
              <th>Cantidad</th>
              <th>Tipo</th>
              <th>Votos que otorga c/u</th>
              <th>Suscrito</th>
              <th>Integrado</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <input
                  type="number"
                  step="1"
                  value={cab[`${p}_cantidad`] ?? ""}
                  onChange={(e) => editarCab(`${p}_cantidad`, e.target.value)}
                />
              </td>
              <td>
                <input
                  type="text"
                  value={cab[`${p}_tipo`] || ""}
                  onChange={(e) => editarCab(`${p}_tipo`, e.target.value)}
                />
              </td>
              <td>
                <input
                  type="number"
                  step="1"
                  value={cab[`${p}_votos`] ?? ""}
                  onChange={(e) => editarCab(`${p}_votos`, e.target.value)}
                />
              </td>
              <td>
                <input
                  type="number"
                  step="0.01"
                  value={cab[`${p}_suscripto`] ?? ""}
                  onChange={(e) => editarCab(`${p}_suscripto`, e.target.value)}
                />
              </td>
              <td>
                <input
                  type="number"
                  step="0.01"
                  value={cab[`${p}_integrado`] ?? ""}
                  onChange={(e) => editarCab(`${p}_integrado`, e.target.value)}
                />
              </td>
            </tr>
          </tbody>
        </table>
      ))}
      <p className="nota">
        Estos datos van a la Carátula del Excel. Las fechas se pueden cambiar cuando
        quieras: cada cliente tiene su propio cierre.
      </p>
    </>
  );

  const renderEsp = () => (
    <div className="eecc-par">
      {[["activo", "ACTIVO"], ["pasivo", "PASIVO"]].map(([lado, titulo]) => (
        <table className="tabla eecc-tabla" key={lado}>
          <thead>
            <tr>
              <th>{titulo}</th>
              <th className="derecha">{fecha(cab.fecha_fin)}</th>
              <th className="derecha">{comp}</th>
            </tr>
          </thead>
          <tbody>
            {borrador.esp[lado].map((f) => {
              if (f.tipo === "titulo") {
                return (
                  <tr key={f.clave} className="eecc-titulo">
                    <td colSpan="3">{f.etiqueta}</td>
                  </tr>
                );
              }
              if (f.tipo === "total") {
                return (
                  <tr key={f.clave} className="eecc-total">
                    <td>{f.etiqueta}</td>
                    <td className="mono derecha">{pesos(f.actual)}</td>
                    <td className="mono derecha">{pesos(f.anterior)}</td>
                  </tr>
                );
              }
              return (
                <tr key={f.clave}>
                  <td>
                    {f.etiqueta}{" "}
                    {f.nota && <small className="eecc-nota">({f.nota})</small>}
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={f.actual}
                      onChange={(e) => editarEsp(lado, f.clave, "actual", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={f.anterior}
                      onChange={(e) => editarEsp(lado, f.clave, "anterior", e.target.value)}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ))}
    </div>
  );

  const renderEr = () => (
    <>
      <p className="nota">
        Como en el modelo, la ganancia bruta resta el costo y el resultado suma lo que
        sigue: los gastos que reducen el resultado se cargan con signo negativo.
      </p>
      <div className="tabla-envoltura eecc-scroll">
        <table className="tabla eecc-tabla">
          <thead>
            <tr>
              <th>Estado de Resultados</th>
              <th>Nota</th>
              <th className="derecha">{fecha(cab.fecha_fin)}</th>
              <th className="derecha">{comp}</th>
            </tr>
          </thead>
          <tbody>
            {borrador.er.map((f) => (
              <tr key={f.clave} className={f.tipo === "calc" ? "eecc-total" : undefined}>
                <td>{f.etiqueta}</td>
                <td className="eecc-nota">{f.nota || ""}</td>
                {f.tipo === "rubro" ? (
                  <>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        value={f.actual}
                        onChange={(e) => editarEr(f.clave, "actual", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        value={f.anterior}
                        onChange={(e) => editarEr(f.clave, "anterior", e.target.value)}
                      />
                    </td>
                  </>
                ) : (
                  <>
                    <td className="mono derecha">{pesos(f.actual)}</td>
                    <td className="mono derecha">{pesos(f.anterior)}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );

  const renderEepn = (campo, titulo) => {
    const cols = borrador.eepn.columnas;
    const grupos = [];
    cols.forEach((c) => {
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.grupo === c.grupo) ultimo.n += 1;
      else grupos.push({ grupo: c.grupo, n: 1 });
    });
    return (
      <>
        <p className="kicker eecc-subtitulo">{titulo}</p>
        <div className="tabla-envoltura eecc-scroll">
          <table className="tabla eecc-tabla eecc-eepn">
            <thead>
              <tr>
                <th rowSpan="2">Concepto</th>
                {grupos.map((g) => (
                  <th key={g.grupo} colSpan={g.n}>
                    {TITULOS_GRUPO[g.grupo]}
                  </th>
                ))}
              </tr>
              <tr>
                {cols.map((c) => (
                  <th key={c.clave}>{c.etiqueta}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {borrador.eepn.filas.map((f) => {
                if (f.tipo === "titulo") {
                  return (
                    <tr key={f.clave} className="eecc-titulo">
                      <td colSpan={cols.length + 1}>{f.etiqueta}</td>
                    </tr>
                  );
                }
                return (
                  <tr key={f.clave} className={f.tipo === "calc" ? "eecc-total" : undefined}>
                    <td>
                      {f.etiqueta}
                      {f.clave === "ganancia" && (
                        <small className="eecc-nota"> (la misma del Estado de Resultados)</small>
                      )}
                    </td>
                    {cols.map((c) => (
                      <td key={c.clave} className={c.calc ? "mono derecha" : undefined}>
                        {f.tipo === "dato" && !c.calc ? (
                          <input
                            type="number"
                            step="0.01"
                            value={f.celdas[c.clave][campo]}
                            onChange={(e) =>
                              editarEepn(f.clave, c.clave, campo, e.target.value)
                            }
                          />
                        ) : (
                          pesos(f.celdas[c.clave][campo])
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </>
    );
  };

  // Día y mes de cierre del cliente (de su ficha). El año no importa: es un
  // cierre que se repite todos los años.
  const cierreCliente = (() => {
    const f = cliente?.fecha_cierre_ejercicio;
    if (!f) return null;
    const [a, m, d] = String(f).split("-").map(Number);
    if (!d || !m) return null;
    return { dia: d, mes: m, anio: a };
  })();
  // El intervalo que se verá al crear (solo para mostrarlo antes de guardar).
  const intervaloNuevo = nuevo
    ? intervaloDe(
        nuevo.anio_inicio,
        nuevo.anio_fin,
        nuevo.dia_mes_cierre || cierreCliente?.dia,
        nuevo.mes_cierre || cierreCliente?.mes
      )
    : null;

  return (
    <section>
      {/* El kicker dice "del cliente" y no "Estados contables": este balance es
          el de un cliente, no el del estudio. El menú lo pone bajo
          "Contabilidad del cliente" justamente por eso, y acá se repite para
          que quede claro al leer la pantalla sola. */}
      <span className="kicker">Contabilidad del cliente</span>
      <h1>Balance general (RT54)</h1>
      <p className="lead">
        Elegí un cliente, creá un ejercicio y cargá los importes del modelo RT54. Los
        totales los calcula el servidor; al terminar, emití el Excel.
      </p>
      {cliente && (
        <p className="nota">
          Estás viendo el balance de <b>{cliente.nombre_completo}</b>. El balance
          del estudio es otra cosa: es el de los mayor generales.
        </p>
      )}

      <div className="buscador">
        <BuscadorCliente
          clientes={clientes}
          seleccion={cliente}
          onElegir={alElegirCliente}
        />
        {cliente && (
          <button className="btn btn-sm" type="button" onClick={() => setNuevo(nuevoVacio())}>
            Nuevo ejercicio
          </button>
        )}
        {borrador && (
          <>
            <button
              className="btn btn-sm"
              type="button"
              onClick={guardar}
              disabled={!sucio || guardando}
            >
              {guardando ? "Guardando…" : "Guardar"}
            </button>
            <button
              className="btn btn-sm fantasma"
              type="button"
              onClick={emitir}
              disabled={guardando}
              title={sucio ? "Se guardan los cambios antes de emitir" : "Descarga el Excel del modelo"}
            >
              Emitir Excel
            </button>
            <button className="btn btn-sm fantasma" type="button" onClick={eliminar}>
              Eliminar
            </button>
          </>
        )}
        {sucio && <span className="eecc-estado">Cambios sin guardar</span>}
        {guardado && !sucio && <span className="eecc-estado ok">Guardado ✓</span>}
      </div>

      {error && <p className="error">{error}</p>}

      {nuevo && cliente && (
        <form className="panel" onSubmit={crearNuevo}>
          <h3>Nuevo ejercicio de {cliente.nombre_completo}</h3>
          <div className="buscador">
            <label className="campo">
              <span>Ejercicio (nombre)</span>
              <input
                value={nuevo.nombre}
                onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
                required
              />
            </label>
            <label className="campo">
              <span>Año de inicio</span>
              <input
                type="number"
                min="1900"
                max="2999"
                step="1"
                value={nuevo.anio_inicio}
                onChange={(e) => setNuevo({ ...nuevo, anio_inicio: e.target.value })}
                required
              />
            </label>
            <label className="campo">
              <span>Año de cierre</span>
              <input
                type="number"
                min="1900"
                max="2999"
                step="1"
                value={nuevo.anio_fin}
                onChange={(e) => setNuevo({ ...nuevo, anio_fin: e.target.value })}
                required
              />
            </label>
            <button className="btn btn-sm" type="submit">
              Crear
            </button>
            <button className="btn btn-sm fantasma" type="button" onClick={() => setNuevo(null)}>
              Cancelar
            </button>
          </div>
          {cierreCliente ? (
            <p className="nota">
              Este cliente cierra el <b>{String(cierreCliente.dia).padStart(2, "0")}/{String(cierreCliente.mes).padStart(2, "0")}</b>{" "}
              todos los años. {intervaloNuevo
                ? <>El ejercicio va del <b>{fecha(intervaloNuevo.inicio)}</b> al <b>{fecha(intervaloNuevo.fin)}</b>.</>
                : <>Elegí el año de cierre para ver el intervalo.</>}
            </p>
          ) : (
            <p className="nota">
              Este cliente no tiene cargado el día y mes de cierre. Cargalo en su
              ficha (pestaña Datos) y el intervalo se arma solo; si querés, también
              podés elegirlo acá.
              <span className="eecc-nota" />
            </p>
          )}
          {!cierreCliente && (
            <div className="buscador">
              <label className="campo">
                <span>Día de cierre</span>
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={nuevo.dia_mes_cierre || ""}
                  onChange={(e) => setNuevo({ ...nuevo, dia_mes_cierre: e.target.value })}
                />
              </label>
              <label className="campo">
                <span>Mes de cierre</span>
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={nuevo.mes_cierre || ""}
                  onChange={(e) => setNuevo({ ...nuevo, mes_cierre: e.target.value })}
                />
              </label>
            </div>
          )}
          <p className="nota">
            La carátula se llena sola con los datos de la ficha del cliente; después
            podés corregirla.
          </p>
        </form>
      )}

      {cliente && (
        <>
          <p className="kicker">
            Balances guardados de {cliente.nombre_completo}
          </p>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Ejercicio</th>
                  <th>Fecha de inicio</th>
                  <th>Fecha de cierre</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {ejercicios.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="vacio">
                      Todavía no hay balances para este cliente. Creá el primero con
                      «Nuevo ejercicio».
                    </td>
                  </tr>
                ) : (
                  ejercicios.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <b>{e.nombre}</b>
                        {borrador?.cabecera.id === e.id && (
                          <small className="eecc-nota"> (abierto)</small>
                        )}
                      </td>
                      <td className="mono">{fecha(e.fecha_inicio)}</td>
                      <td className="mono">{fecha(e.fecha_fin)}</td>
                      <td className="derecha">
                        <button
                          className="btn btn-sm fantasma"
                          onClick={() => abrirEjercicio(e.id)}
                          disabled={guardando}
                        >
                          {borrador?.cabecera.id === e.id ? "Recargar" : "Modificar"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {borrador && (
            <>
              <div className="pestanas">
                {PESTANAS.map(([clave, etiqueta]) => (
                  <button
                    key={clave}
                    className={`pestana${pestana === clave ? " activa" : ""}`}
                    onClick={() => setPestana(clave)}
                    type="button"
                  >
                    {etiqueta}
                  </button>
                ))}
              </div>

              {pestana === "caratula" && renderCaratula()}
              {pestana === "esp" && renderEsp()}
              {pestana === "er" && renderEr()}
              {pestana === "eepn" &&
                renderEepn("actual", `Ejercicio finalizado el ${fecha(cab.fecha_fin)}`)}
              {pestana === "eepn" &&
                renderEepn("anterior", `Ejercicio anterior — finalizado el ${comp}`)}
              {pestana === "notas" && renderNotas()}
              {pestana === "moneda" && renderMoneda()}
            </>
          )}
        </>
      )}

      {!cliente && (
        <div className="panel">
          <p className="lista-vacia">
            Elegí un cliente para ver, crear o modificar sus balances RT54.
          </p>
        </div>
      )}
    </section>
  );
}
