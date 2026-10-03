/**
 * Selector de período contable: "Mes y año" completa desde/hasta solo,
 * "Fechas" deja los dos campos libres (como siempre).
 * Los valores modo/mes/anio viajan en el mismo objeto filtros de la página;
 * al limpiar (volver a vacío) vuelve a mostrar "Fechas".
 */
const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

const HOY = new Date();
const pad = (n) => String(n).padStart(2, "0");

export default function Periodo({ filtros, setFiltros }) {
  const modo = filtros.modo || "custom";
  const mes = filtros.mes || pad(HOY.getMonth() + 1);
  const anio = filtros.anio || String(HOY.getFullYear());
  const anios = [
    HOY.getFullYear() + 1,
    HOY.getFullYear(),
    HOY.getFullYear() - 1,
    HOY.getFullYear() - 2,
    HOY.getFullYear() - 3,
  ];

  const aplicar = (m, a) => {
    const ultimo = new Date(Number(a), Number(m), 0).getDate();
    setFiltros({
      ...filtros,
      modo: "mes",
      mes: m,
      anio: a,
      desde: `${a}-${m}-01`,
      hasta: `${a}-${m}-${pad(ultimo)}`,
    });
  };

  const cambiarModo = (valor) => {
    if (valor === "mes") aplicar(mes, anio);
    else setFiltros({ ...filtros, modo: "custom" });
  };

  return (
    <>
      <label className="campo">
        <span>Período</span>
        <select value={modo} onChange={(e) => cambiarModo(e.target.value)}>
          <option value="mes">Mes y año</option>
          <option value="custom">Fechas</option>
        </select>
      </label>

      {modo === "mes" ? (
        <>
          <label className="campo">
            <span>Año</span>
            <select value={anio} onChange={(e) => aplicar(mes, e.target.value)}>
              {anios.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="campo">
            <span>Mes</span>
            <select value={mes} onChange={(e) => aplicar(e.target.value, anio)}>
              {MESES.map((nombre, i) => (
                <option key={nombre} value={pad(i + 1)}>
                  {nombre}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : (
        <>
          <label className="campo">
            <span>Desde</span>
            <input
              type="date"
              value={filtros.desde || ""}
              onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })}
            />
          </label>
          <label className="campo">
            <span>Hasta</span>
            <input
              type="date"
              value={filtros.hasta || ""}
              onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })}
            />
          </label>
        </>
      )}
    </>
  );
}
