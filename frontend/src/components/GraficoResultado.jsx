import { useEffect, useRef } from "react";
import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";

/**
 * GRÁFICO DE INGRESOS Y GASTOS, MES A MES DEL EJERCICIO.
 *
 * Doce barras, una por cada mes del ejercicio (septiembre a agosto), con dos
 * series: lo que entró y lo que salió. La pregunta que responde es "¿cómo viene
 * el año?", y la forma de responderla es ver los meses uno al lado del otro: en
 * cuál se gastó más, cuál cerró en rojo.
 *
 * **Por qué barras y no torta**: doce porciones de torta son ilegibles — hay que
 * medir ángulos para compararlas. Con barras la comparación es directa, y el
 * número se ve al pasar el mouse.
 *
 * **De dónde salen los números**: todos del backend
 * (`/dashboard/resultado-por-periodo`), que los suma en SQL desde los asientos
 * contabilizados. Acá no se suma nada: si el navegador calculara los totales, el
 * gráfico y el informe de resultados podrían dar números distintos.
 *
 * **Por qué NO `import ... from "chart.js/auto"`**: esa forma registra TODOS los
 * tipos de gráfico (líneas, tortas, radar, geográfico...) y pesa 210 KB aunque
 * acá solo hay barras. Nombrando solo lo que se usa, el bundle baja a menos de
 * la mitad. Es la misma librería, es lo mismo que ande; nomás no se paga el resto.
 *
 * Chart.js se borra cuando el componente se desmonta (`chart.destroy()`). Sin
 * eso, cada vez que se vuelve al dashboard se apila un gráfico sobre el anterior
 * y el canvas queda sucio (se ve el dibujo duplicado y borroso).
 */
Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);
export default function GraficoResultado({ data }) {
  const refCanvas = useRef(null);
  const refGrafico = useRef(null);

  const items = data?.items || [];
  // Si los doce meses están en cero no hay nada que graficar: una rejilla vacía
  // parece una pantalla rota, y además Chart.js no escala bien un rango todo cero.
  const hayDatos = items.some((i) => i.ingresos !== 0 || i.gastos !== 0);

  useEffect(() => {
    if (!hayDatos) return;

    const ctx = refCanvas.current.getContext("2d");
    const grafico = new Chart(ctx, {
      type: "bar",
      data: {
        labels: items.map((i) => i.nombre.replace(" 20", " ")),
        datasets: [
          {
            label: "Ingresos",
            data: items.map((i) => i.ingresos),
            backgroundColor: "rgba(52, 211, 153, 0.75)",
            borderColor: "#34d399",
            borderWidth: 1,
          },
          {
            label: "Egresos",
            data: items.map((i) => i.gastos),
            backgroundColor: "rgba(248, 113, 113, 0.7)",
            borderColor: "#f87171",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: { color: "#cbd5e1", font: { size: 12 } },
          },
          tooltip: {
            callbacks: {
              // El importe con el mismo formato de pesos que el resto del sistema.
              label: (ctx) =>
                `${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString("es-AR", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              color: "#94a3b8",
              callback: (v) =>
                v >= 1000 ? `${Math.round(v / 1000)}k` : String(v),
            },
            grid: { color: "rgba(148, 163, 184, 0.15)" },
          },
          x: {
            ticks: { color: "#94a3b8", maxRotation: 60, minRotation: 45, font: { size: 10 } },
            grid: { display: false },
          },
        },
      },
    });

    refGrafico.current = grafico;
    return () => {
      grafico.destroy();
      refGrafico.current = null;
    };
  }, [hayDatos, items]);

  if (!items.length) return null;

  if (!hayDatos) {
    return (
      <div className="nota" style={{ padding: "1.2rem 0" }}>
        Todavía no hay ingresos ni gastos registrados en el ejercicio. El
        gráfico aparece solo cuando contables un asiento.
      </div>
    );
  }

  return (
    <>
      {/* El `alto` fijo + `position: relative` es lo que hace Chart.js ocupe el
          alto disponible en vez de crecer sin límite. */}
      <div style={{ position: "relative", height: "280px", marginTop: "0.5rem" }}>
        <canvas ref={refCanvas} aria-label="Ingresos y gastos por mes del ejercicio" />
      </div>
      <p className="nota" style={{ marginTop: "0.8rem" }}>
        Total del ejercicio: ingresos ${Math.round(data.total_ingresos).toLocaleString("es-AR")} ·
        egresos ${Math.round(data.total_gastos).toLocaleString("es-AR")} ·{" "}
        <b className={data.neto < 0 ? "vencida" : ""}>
          {data.neto < 0 ? "pérdida" : "ganancia"} ${Math.abs(Math.round(data.neto)).toLocaleString("es-AR")}
        </b>
        . Egresos = costos + gastos, el mismo número que el informe de
        resultados.
      </p>
    </>
  );
}