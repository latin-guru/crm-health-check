// Draws every chart on the page from the JSON spec written by src/chc/report.py.
// Each <canvas data-chart="id"> has a matching <script type="application/json" id="chart-id">.
(function () {
  "use strict";
  if (!window.Chart) return; // Chart.js failed to load: the tables next to each chart still work.

  const css = getComputedStyle(document.documentElement);
  const color = (role) => css.getPropertyValue("--" + role).trim();
  const money = (value) => "$" + Math.round(value).toLocaleString("en-US");

  Chart.defaults.animation = false;
  Chart.defaults.color = color("text-secondary");
  Chart.defaults.borderColor = color("grid");
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  document.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
    const spec = JSON.parse(document.getElementById("chart-" + canvas.dataset.chart).textContent);
    const format = spec.money ? money : (value) => value.toLocaleString("en-US");
    const valueAxis = spec.horizontal ? "x" : "y";

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: spec.labels,
        datasets: spec.series.map((series) => ({
          label: series.name,
          data: series.values,
          backgroundColor: series.colors ? series.colors.map(color) : color(series.color),
          borderRadius: 4,
          borderSkipped: spec.floating ? false : "start",
          maxBarThickness: 36,
        })),
      },
      options: {
        indexAxis: spec.horizontal ? "y" : "x",
        maintainAspectRatio: false,
        plugins: {
          legend: { display: spec.series.length > 1, position: "top", align: "start" },
          tooltip: {
            callbacks: {
              label: (item) => {
                const raw = item.raw;
                if (Array.isArray(raw) && raw[0] === 0) return item.label + ": " + money(raw[1]);
                if (Array.isArray(raw)) {
                  return item.label + ": " + money(raw[1]) + " (" + (raw[1] >= raw[0] ? "+" : "") + money(raw[1] - raw[0]) + ")";
                }
                return item.dataset.label + ": " + format(raw);
              },
            },
          },
        },
        scales: {
          [valueAxis]: {
            // A waterfall starts its axis near the totals (see waterfall_axis_min in report.py).
            beginAtZero: spec.min === undefined,
            min: spec.min,
            ticks: { callback: (value) => format(value) },
          },
          [spec.horizontal ? "y" : "x"]: { grid: { display: false } },
        },
      },
    });
  });
})();
