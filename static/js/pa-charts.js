/* Biểu đồ Chart.js theo pa-ui mục 7: màu lấy từ token CSS, không 3D, không gradient, không hiệu ứng.
   Dùng: <canvas data-pa-chart="id-của-json_script"> với JSON {type, labels, values, unit}. */
(function () {
  "use strict";

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof Chart === "undefined") return;
    document.querySelectorAll("canvas[data-pa-chart]").forEach(function (canvas) {
      var cfg = JSON.parse(document.getElementById(canvas.dataset.paChart).textContent);
      var grid = token("--pa-border");
      var series = [token("--pa-navy"), token("--pa-blue"), token("--pa-muted")];
      Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
      Chart.defaults.color = token("--pa-text");
      new Chart(canvas, {
        type: cfg.type || "bar",
        data: {
          labels: cfg.labels,
          datasets: [{ label: cfg.unit, data: cfg.values, backgroundColor: series[0], borderRadius: 0 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: grid }, border: { color: grid } },
            y: {
              beginAtZero: true,
              grid: { color: grid },
              border: { color: grid },
              title: { display: true, text: cfg.unit },
            },
          },
        },
      });
    });
  });
})();
